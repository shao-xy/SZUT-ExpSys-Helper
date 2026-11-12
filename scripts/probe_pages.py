"""探测脚本：登录后抓取排课相关页面，保存到 var/pages/ 供离线分析。

用法：
    $env:LABREG_COURSE='00000000'
    $env:LABREG_CLASS='示例课程-0001A'
    $env:LABREG_RWID='72732'
    $env:LABREG_XMID='37514'
    python scripts/probe_pages.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _common import make_client, require_env, task_query  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "var" / "pages"


def main() -> int:
    client = make_client()
    course = require_env("LABREG_COURSE")
    class_name = require_env("LABREG_CLASS")
    rwid = require_env("LABREG_RWID")
    xmid = require_env("LABREG_XMID")

    OUT.mkdir(parents=True, exist_ok=True)
    query = task_query(client, course, class_name, rwid, xmid)

    for page in ("jskclist", "jsfzlist", "xsteam", "fzKeBiao", "plkb2"):
        content = client.text(f"admin/kebiao/{page}.aspx?{query}")
        path = OUT / f"probe_{page}.html"
        path.write_text(content, encoding="utf-8")
        print(f"{page}: {len(content)} 字符 -> {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
