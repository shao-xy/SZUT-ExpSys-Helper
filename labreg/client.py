"""站点 HTTP 客户端。

系统为 ASP.NET WebForms，全部表单提交都依赖 __VIEWSTATE / __VIEWSTATEGENERATOR /
__EVENTVALIDATION 隐藏域，因此每次响应后都要重新提取并覆盖。
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse

import requests
from lxml import html as lhtml

from . import pages
from .crypto import encrypt_password

logger = logging.getLogger(__name__)

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

VIEWSTATE_KEYS = ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION")


class SiteError(RuntimeError):
    """站点交互异常。"""


@dataclass
class LoginResult:
    ok: bool
    message: str
    location: str = ""


class SiteClient:
    """封装登录态、隐藏域管理与页面抓取。"""

    def __init__(self, base_url: str, username: str = "", password: str = "",
                 timeout: int = 30, verify_ssl: bool = True) -> None:
        self.base_url = base_url if base_url.endswith("/") else base_url + "/"
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(BASE_HEADERS)
        self.session.verify = verify_ssl
        self.common_params: dict[str, str] = {}
        self.hidden_fields: dict[str, str] = {}
        self.last_url = ""
        self.logged_in = False

    # ---------- 基础请求 ----------

    def _abs(self, url: str) -> str:
        return urljoin(self.base_url, url)

    def _with_common_params(self, url: str) -> str:
        """把 sid / screen / roles 追加到查询串。"""
        if not self.common_params:
            return url
        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query))
        query.update(self.common_params)
        return parsed._replace(query=urlencode(query)).geturl()

    def _absorb(self, resp: requests.Response) -> requests.Response:
        """提取隐藏域并更新公共参数。"""
        resp.encoding = resp.apparent_encoding or "utf-8"
        self.last_url = resp.url
        if resp.text:
            tree = None
            try:
                tree = lhtml.fromstring(resp.text.encode("utf-8"))
            except (ValueError, lhtml.etree.ParserError):
                tree = None
            if tree is not None:
                found = {
                    el.get("name"): el.get("value") or ""
                    for el in tree.xpath("//input[@type='hidden'][@name]")
                }
                # 只有真正的页面才更新隐藏域。
                # 冲突检查等接口返回的是纯文本，用 lxml 解析后没有 form，
                # 若在此清空隐藏域，后续表单提交就会丢失 __VIEWSTATE 而被站点拒绝。
                is_page = bool(found) or bool(tree.xpath("//form"))
                if is_page:
                    self.hidden_fields = found
                    # 页面没有 __EVENTVALIDATION 时必须清掉旧值，否则回发校验失败
                    for key in VIEWSTATE_KEYS:
                        if key not in found:
                            self.hidden_fields.pop(key, None)
            for key in ("sid", "screen", "roles"):
                m = re.search(rf"[?&]{key}=([^&\"']+)", resp.url)
                if m:
                    self.common_params[key] = m.group(1)
        return resp

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        url = self._with_common_params(self._abs(url))
        headers = dict(kwargs.pop("headers", {}) or {})
        headers.setdefault("Referer", self.last_url or self.base_url)
        resp = self.session.get(url, timeout=self.timeout, headers=headers, **kwargs)
        return self._absorb(resp)

    def post(self, url: str, data: dict[str, str] | None = None,
             files: dict | None = None, **kwargs: Any) -> requests.Response:
        """提交表单；隐藏域以最近一次响应为准，调用方未指定时自动补齐。"""
        payload = dict(data or {})
        for key, value in self.hidden_fields.items():
            payload.setdefault(key, value)
        url = self._with_common_params(self._abs(url))
        headers = dict(kwargs.pop("headers", {}) or {})
        headers.setdefault("Referer", self.last_url or self.base_url)
        if files:
            resp = self.session.post(url, data=payload, files=files,
                                     timeout=self.timeout, headers=headers, **kwargs)
        else:
            resp = self.session.post(url, data=payload,
                                     timeout=self.timeout, headers=headers, **kwargs)
        return self._absorb(resp)

    def tree(self, url: str, **kwargs: Any):
        """抓取页面并返回解析后的 DOM。"""
        resp = self.get(url, **kwargs)
        return pages.parse(resp.text)

    def text(self, url: str, **kwargs: Any) -> str:
        return self.get(url, **kwargs).text

    # ---------- 登录 ----------

    def fetch_captcha(self) -> tuple[bytes, str]:
        """下载验证码图片并返回 (图片字节, 识别文本)。"""
        url = self._abs(f"GenerateIdentifyingCode.aspx?t={int(time.time() * 1000)}")
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        try:
            import ddddocr
        except ImportError as exc:  # pragma: no cover
            raise SiteError("缺少 ddddocr，无法自动识别验证码") from exc
        ocr = ddddocr.DdddOcr(show_ad=False)
        return resp.content, ocr.classification(resp.content)

    def login(self, captcha: str | None = None, retries: int = 3) -> LoginResult:
        """登录站点。captcha 为 None 时自动识别验证码。"""
        if self.logged_in:
            return LoginResult(True, "已处于登录态")
        self.get("index2.aspx")
        last_msg = ""
        for attempt in range(retries):
            if captcha:
                code, captcha = captcha, None
            else:
                _, code = self.fetch_captcha()
            data = {
                "UserId": self.username,
                "Password": encrypt_password(self.password),
                "IdentifyingCode": code,
                "btnLogin": "登录",
            }
            resp = self.post("index2.aspx", data=data, allow_redirects=False)
            if resp.status_code in (301, 302):
                location = resp.headers.get("Location", "")
                for key in ("sid", "screen", "roles"):
                    m = re.search(rf"[?&]{key}=([^&\"']+)", location)
                    if m:
                        self.common_params[key] = m.group(1)
                if not self.common_params.get("sid"):
                    self.get(location)
                self.logged_in = True
                logger.info("登录成功：%s", location)
                return LoginResult(True, "登录成功", location)
            last_msg = self._login_failure_text(resp)
            logger.warning("第 %d 次登录失败：%s", attempt + 1, last_msg)
        return LoginResult(False, last_msg or "登录失败")

    @staticmethod
    def _login_failure_text(resp: requests.Response) -> str:
        """从返回页面中提取失败原因。"""
        text = resp.text
        patterns = [
            r"alert\(['\"](.+?)['\"]\)",
            r"(?:验证码|密码|账号|用户名)[^<]{0,20}(?:错误|不正确|有误|为空|不存在)",
            r"id=\"(?:msg|lblMessage|tip)[^\"]*\"[^>]*>([^<]{2,80})<",
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if not m:
                continue
            if m.groups():
                return " ".join(m.group(1).split())
            # 无捕获组的模式直接返回匹配到的片段
            return " ".join(m.group(0).split())
        return f"HTTP {resp.status_code}"
