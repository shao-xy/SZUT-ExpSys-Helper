"""临时脚本：对单个 (班级, 实验项目) 做一次排课，用于验证单双周行为。

用法：
    $env:LABREG_COURSE='04300204'
    $env:LABREG_CLASS='操作系统-0002A'
    $env:LABREG_PROJECT='基于QEMU的内核启动与显示'
    $env:LABREG_WEEK='9'
    $env:LABREG_PARITY='单周'
    python scripts/test_one_slot.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _common import make_client, require_env  # noqa: E402
from labreg import pages  # noqa: E402
from labreg.workflow import Scheduler, Slot  # noqa: E402


def main() -> int:
    client = make_client()
    course = require_env("LABREG_COURSE")
    class_name = require_env("LABREG_CLASS")
    project = require_env("LABREG_PROJECT")
    week = int(require_env("LABREG_WEEK"))
    parity = require_env("LABREG_PARITY") if "LABREG_PARITY" in __import__("os").environ else ""

    scheduler = Scheduler(client)
    task = next(
        (t for t in scheduler.list_task_rows(course, class_name)
         if project in t.project_name),
        None,
    )
    if task is None:
        raise SystemExit(f"未找到实验项目 {project}")
    params = task.params
    rwid, xmid = params.get("rwid", ""), params.get("xmid", "")

    print(f"项目 {task.project_name}  rwid={rwid} xmid={xmid}")

    print("[确认]", scheduler.confirm_students(course, class_name, rwid, xmid).message)
    print("[分批]", scheduler.group_students(course, class_name, rwid, xmid, 1).message)

    slot = Slot(start_week=week, end_week=week, weekday="星期二",
                start_period=1, end_period=2, room="力行112", parity=parity)
    print(f"[排课] {slot.describe}")
    result = scheduler.schedule(course, class_name, rwid, xmid, slot)
    print("  →", result.message)

    print()
    print("当前已排课记录：")
    for row in scheduler.existing_rows(course, class_name, rwid, xmid):
        print(f"  {row['time']} @ {row['place']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
