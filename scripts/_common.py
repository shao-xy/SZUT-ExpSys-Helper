"""探测脚本的公共支撑：凭据、站点与课程参数。

所有凭据一律从环境变量或 .env 读取，脚本内不出现任何口令。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from labreg.client import SiteClient  # noqa: E402
from labreg.config import load_settings  # noqa: E402


def make_client() -> SiteClient:
    """按 .env / 环境变量建立已登录的会话。"""
    settings = load_settings()
    client = SiteClient(settings.base_url, settings.username, settings.password)
    if not client.login().ok:
        raise SystemExit("登录失败，请检查 .env 中的账号密码，或先运行 labreg preflight")
    return client


def task_query(client: SiteClient, course_code: str, class_name: str,
               rwid: str, xmid: str) -> str:
    """构造课程任务页的公共查询串。"""
    params = {
        "coursecode": course_code,
        "kxh": quote(class_name),
        "rwid": rwid,
        "xmid": xmid,
    }
    params.update(client.common_params)
    from urllib.parse import urlencode
    return urlencode(params)


def require_env(name: str) -> str:
    """读取必需的环境变量。"""
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(
            f"缺少环境变量 {name}\n"
            f"用法示例：$env:{name}='...'; python scripts/<脚本>.py"
        )
    return value
