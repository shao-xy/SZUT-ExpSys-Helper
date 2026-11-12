"""排课流程的纯逻辑测试。

覆盖幂等判定与冲突判定，这些决定了工具会不会重复排课或漏排。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from labreg.workflow import Scheduler, Slot  # noqa: E402


class FakeScheduler(Scheduler):
    """只借用纯逻辑方法，不触碰网络。"""

    def __init__(self) -> None:  # noqa: D107
        pass


def row(week: int, weekday: str = "星期四", start: int = 3, end: int = 4,
        place: str = "N6101") -> dict:
    return {
        "time": f"2026-09-24 09:50 - 11:25 第{week}周 [{weekday}] {start} -{end}节",
        "place": place,
        "classes": "",
        "teachers": "",
        "delete_id": "",
    }


def test_single_week_already_scheduled() -> None:
    s = FakeScheduler()
    slot = Slot(start_week=1, end_week=1, weekday="星期四",
                start_period=3, end_period=4, room="N6101")
    assert s.is_already_scheduled([row(1)], slot)


def test_multi_week_needs_every_week() -> None:
    s = FakeScheduler()
    slot = Slot(start_week=1, end_week=3, weekday="星期四",
                start_period=3, end_period=4, room="N6101")
    # 只有第 1、2 周，缺第 3 周
    assert not s.is_already_scheduled([row(1), row(2)], slot)
    assert s.is_already_scheduled([row(1), row(2), row(3)], slot)


def test_different_weekday_is_not_a_match() -> None:
    s = FakeScheduler()
    slot = Slot(start_week=1, end_week=1, weekday="星期四",
                start_period=3, end_period=4, room="N6101")
    assert not s.is_already_scheduled([row(1, weekday="星期五")], slot)


def test_different_period_is_not_a_match() -> None:
    s = FakeScheduler()
    slot = Slot(start_week=1, end_week=1, weekday="星期四",
                start_period=6, end_period=7, room="N6101")
    assert not s.is_already_scheduled([row(1, start=3, end=4)], slot)


def test_different_room_is_not_a_match() -> None:
    s = FakeScheduler()
    slot = Slot(start_week=1, end_week=1, weekday="星期四",
                start_period=3, end_period=4, room="N6111")
    assert not s.is_already_scheduled([row(1, place="N6101")], slot)


def test_empty_schedule_is_never_a_match() -> None:
    s = FakeScheduler()
    slot = Slot(start_week=1, end_week=1, weekday="星期四",
                start_period=3, end_period=4, room="N6101")
    assert not s.is_already_scheduled([], slot)


def test_slot_describe() -> None:
    slot = Slot(start_week=1, end_week=3, weekday="星期四",
                start_period=3, end_period=4, room="N6101")
    assert slot.describe == "第1-3周 星期四 3-4节 @N6101"
