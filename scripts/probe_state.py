"""状态探测：报告班级的确认学生、分批与已有排课状态。

用法：
    $env:LABREG_COURSE='00000000'
    $env:LABREG_CLASS='示例课程-0001A'
    $env:LABREG_RWID='72732'
    $env:LABREG_XMID='37514'
    python scripts/probe_state.py
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

    confirm = pages.parse_confirm_state(client.tree(f"{pages.PAGE_CONFIRM}?{query}"))
    print(f"已确认学生: {confirm.confirmed}/{confirm.matched}")
    print(f"引用按钮  : {confirm.quote_button}")

    group_tree = client.tree(f"{pages.PAGE_GROUP_FORM}?{query}")
    pending = pages.parse_pending_students(group_tree)
    summaries = pages.parse_batch_summaries(group_tree)
    print(f"待分批学生: {len(pending)}")
    print(f"已有分批  : {summaries or '无'}")

    schedule_tree = client.tree(f"{pages.PAGE_BATCH_SCHEDULE}?{query}")
    for item in pages.parse_schedule_rows(schedule_tree):
        print(f"已排课    : {item['time']} @ {item['place']}  ({item['classes']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
