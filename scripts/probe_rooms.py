"""探测脚本：遍历全部实验室别名，输出 别名→机房编号 映射。

用法：
    $env:LABREG_COURSE='00000000'
    $env:LABREG_CLASS='示例课程-0001A'
    $env:LABREG_RWID='72732'
    $env:LABREG_XMID='37514'
    python scripts/probe_rooms.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _common import make_client, require_env, task_query  # noqa: E402
from labreg import pages  # noqa: E402


def main() -> int:
    client = make_client()
    course = require_env("LABREG_COURSE")
    class_name = require_env("LABREG_CLASS")
    rwid = require_env("LABREG_RWID")
    xmid = require_env("LABREG_XMID")

    query = task_query(client, course, class_name, rwid, xmid)
    url = f"{pages.PAGE_BATCH_SCHEDULE}?{query}"

    tree = client.tree(url)
    labs = pages.parse_lab_options(tree)

    print(f"{'别名ID':<8}{'别名':<20}机房")
    print("-" * 78)
    for value, label in labs.items():
        if value == "0":
            continue
        resp = client.post(url, data={
            "__EVENTTARGET": "ddllab",
            "ddllab": value,
            "ddlxm": xmid,
        })
        tree = pages.parse(resp.text)
        rooms = pages.parse_room_options(tree)
        if not rooms:
            print(f"{value:<8}{label:<20}(无)")
        for room_id, room_text in rooms.items():
            if room_id == "0":
                continue
            print(f"{value:<8}{label:<20}{room_id:<8}{room_text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
