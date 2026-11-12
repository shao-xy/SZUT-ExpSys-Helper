"""单点排课验证：为一个实验项目排一个时间位置，并回读结果。

用法：
    $env:LABREG_COURSE='00000000'
    $env:LABREG_CLASS='示例课程-0001A'
    $env:LABREG_RWID='72732'
    $env:LABREG_XMID='37514'
    python scripts/test_one_slot.py <起始周> <结束周> <起始节> <结束节> <机房>
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _common import make_client, require_env, task_query  # noqa: E402
from labreg import pages  # noqa: E402
from labreg.workflow import Scheduler, Slot  # noqa: E402


def main() -> int:
    if len(sys.argv) != 6:
        print(__doc__)
        return 1
    w1, w2 = int(sys.argv[1]), int(sys.argv[2])
    p1, p2 = int(sys.argv[3]), int(sys.argv[4])
    room = sys.argv[5]

    client = make_client()
    course = require_env("LABREG_COURSE")
    class_name = require_env("LABREG_CLASS")
    rwid = require_env("LABREG_RWID")
    xmid = require_env("LABREG_XMID")

    query = task_query(client, course, class_name, rwid, xmid)
    before = pages.parse_schedule_rows(client.tree(f"{pages.PAGE_BATCH_SCHEDULE}?{query}"))
    print(f"排课前 {len(before)} 条")
    for item in before:
        print(f"   {item['time']} @ {item['place']}")

    slot = Slot(start_week=w1, end_week=w2, weekday="星期四",
                start_period=p1, end_period=p2, room=room)
    print("计划：", slot.describe)

    result = Scheduler(client).schedule(course, class_name, rwid, xmid, slot)
    print("结果：", result.ok, result.message)

    after = pages.parse_schedule_rows(client.tree(f"{pages.PAGE_BATCH_SCHEDULE}?{query}"))
    print(f"排课后 {len(after)} 条")
    for item in after:
        print(f"   {item['time']} @ {item['place']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
