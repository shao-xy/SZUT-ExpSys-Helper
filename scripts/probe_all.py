"""状态全量探测：列出某班级下各实验的确认学生 / 分批 / 排课状态。

用法：
    $env:LABREG_COURSE='00000000'
    $env:LABREG_CLASS='示例课程-0001A'
    $env:LABREG_RWID='72732'
    python scripts/probe_all.py
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

    print(f"班级 {class_name}")
    print("=" * 78)

    # 列出该班级的全部实验项目
    from labreg.workflow import Scheduler
    scheduler = Scheduler(client)
    for task in scheduler.list_task_rows(course, class_name):
        params = task.params
        query = task_query(client, course, class_name,
                           params.get("rwid", rwid), params.get("xmid", ""))
        confirm = pages.parse_confirm_state(client.tree(f"{pages.PAGE_CONFIRM}?{query}"))
        group_tree = client.tree(f"{pages.PAGE_GROUP_FORM}?{query}")
        pending = len(pages.parse_pending_students(group_tree))
        schedule_tree = client.tree(f"{pages.PAGE_BATCH_SCHEDULE}?{query}")
        scheduled = pages.parse_schedule_rows(schedule_tree)
        print(f"  {task.project_name}")
        print(f"      确认学生 {confirm.confirmed}/{confirm.matched}"
              f" | 待分批 {pending}"
              f" | 已排课 {len(scheduled)} 条")
        for item in scheduled:
            print(f"        {item['time']} @ {item['place']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
