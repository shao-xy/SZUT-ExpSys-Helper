"""前置条件检查：在动手排课前确认环境与站点状态。

本模块只做「读取与检查」，不写入任何站点数据。
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from urllib.parse import urlparse

from .client import SiteClient, SiteError
from .workflow import Scheduler

# 站点「制订课表（整班排课）」页面无内容时的标准提示。
# 这两项属于教师职责，必须由教师本人在系统中手工完成。
TASK_BOOK_HINT = (
    "站点「制订课表（整班排课）」页面没有内容，通常表示尚未提交任务书。\n"
    "  请教师本人在系统中手工完成以下两步后，再重新运行本工具：\n"
    "    1) 安排并提交本门课程的课程大纲\n"
    "    2) 提交该课程的实验任务书（须包含各实验项目与周次）\n"
    "  本工具不代做、不代填上述两步，请勿要求 Agent 代劳。"
)


@dataclass
class Check:
    """单项检查结果。"""

    name: str
    ok: bool
    detail: str = ""
    hint: str = ""
    blocking: bool = True


@dataclass
class PreflightReport:
    """前置检查汇总。"""

    checks: list[Check] = field(default_factory=list)

    def add(self, check: Check) -> None:
        self.checks.append(check)

    @property
    def passed(self) -> bool:
        return not any(c.blocking and not c.ok for c in self.checks)

    @property
    def blocking_failures(self) -> list[Check]:
        return [c for c in self.checks if c.blocking and not c.ok]

    def render(self) -> str:
        lines = []
        for c in self.checks:
            mark = "通过" if c.ok else ("阻断" if c.blocking else "提醒")
            lines.append(f"[{mark}] {c.name}：{c.detail}")
            if not c.ok and c.hint:
                for hl in c.hint.splitlines():
                    lines.append(f"        {hl}")
        lines.append("")
        lines.append("前置检查通过，可以继续排课。" if self.passed
                     else "前置检查未通过，请先处理上述阻断项。")
        return "\n".join(lines)


def check_connectivity(base_url: str, timeout: int = 5) -> Check:
    """检查站点是否可达。不通通常意味着未连接校园网或 VPN。"""
    parsed = urlparse(base_url if "://" in base_url else f"http://{base_url}")
    host = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if not host:
        return Check("网络连通性", False, "BASE_URL 无法解析出主机名",
                     "请检查 .env 中的 BASE_URL。")
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return Check("网络连通性", True, f"{host}:{port} 可达")
    except OSError as exc:
        return Check(
            "网络连通性", False, f"{host}:{port} 不可达（{exc}）",
            "实验系统位于校园网内，不在校内请先连接学校 VPN。",
        )


def check_login(client: SiteClient) -> tuple[Check, Scheduler | None]:
    """检查登录态。"""
    try:
        result = client.login()
    except SiteError as exc:
        return Check("登录", False, str(exc),
                     "请检查 .env 中的 USERNAME / PASSWORD，并确认账号可正常登录站点。"), None
    except Exception as exc:  # noqa: BLE001
        return Check("登录", False, f"登录请求失败：{exc}",
                     "请检查网络与站点可用性。"), None
    if not result.ok:
        return Check("登录", False, result.message,
                     "请确认账号密码正确；验证码由脚本自动识别，"
                     "若持续失败可手动在浏览器登录一次以排除验证码干扰。"), None
    return Check("登录", True, "成功"), Scheduler(client)


def check_task_book(scheduler: Scheduler) -> Check:
    """检查课程是否已出现在「制订课表」列表中。

    列表为空 = 任务书尚未提交，这是必须由教师手工完成的前置条件。
    """
    try:
        rows = scheduler.list_classes()
    except Exception as exc:  # noqa: BLE001
        return Check("任务书状态", False, f"读取课程列表失败：{exc}",
                     "请检查站点状态，稍后重试。")
    if not rows:
        return Check("任务书状态", False, "站点未列出任何课程", TASK_BOOK_HINT)
    names = "、".join(f"{r.name}[{r.course_code}]" for r in rows[:6])
    more = f" 等 {len(rows)} 个班级" if len(rows) > 6 else ""
    return Check("任务书状态", True, f"已列出 {names}{more}")


def check_plan(scheduler: Scheduler, plans) -> Check:
    """核对计划中的班级与实验项目是否都能在站点上找到。"""
    if not plans:
        return Check("排课计划", False, "排课计划为空",
                     "请在 configs/courses.yaml 中填写课程与班级。")
    try:
        site_rows = scheduler.list_classes()
    except Exception as exc:  # noqa: BLE001
        return Check("排课计划", False, f"读取站点班级失败：{exc}")

    site_names = {r.name for r in site_rows}
    problems: list[str] = []
    for course in plans:
        for cls in course.classes:
            if cls.name not in site_names:
                problems.append(f"班级「{cls.name}」不在站点列表中")
                continue
            site_row = next(r for r in site_rows if r.name == cls.name)
            try:
                tasks = scheduler.list_task_rows(site_row.course_code, cls.name)
            except Exception as exc:  # noqa: BLE001
                problems.append(f"读取「{cls.name}」任务表失败：{exc}")
                continue
            for exp in cls.experiments:
                if not any(exp.project in t.project_name for t in tasks):
                    problems.append(
                        f"「{cls.name}」未找到实验项目「{exp.project}」")
    if problems:
        return Check("排课计划", False, "；".join(problems[:5]),
                     "请核对 courses.yaml 中的班级名与实验项目名，"
                     "可用 `labreg courses` 与 `labreg status` 查看站点上的实际名称。")
    return Check("排课计划", True, f"{len(plans)} 门课程的班级与实验项目均已匹配")


def run_preflight(client: SiteClient, plans=None, need_site: bool = True) -> PreflightReport:
    """执行完整前置检查。

    need_site 为 False 时只做本地检查，完全不访问站点。
    """
    report = PreflightReport()
    if not need_site:
        report.add(Check("本地配置", True, "已跳过联网检查（--offline）"))
        return report

    report.add(check_connectivity(client.base_url, client.timeout))
    if not report.passed:
        return report

    login_check, scheduler = check_login(client)
    report.add(login_check)
    if scheduler is None:
        return report

    report.add(check_task_book(scheduler))
    if not report.passed:
        return report
    if plans is not None:
        report.add(check_plan(scheduler, plans))
    return report
