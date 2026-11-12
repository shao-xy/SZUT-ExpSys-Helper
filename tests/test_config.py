"""配置层与输出层的回归测试。

不联网，只用临时文件验证计划解析与覆盖规则。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from labreg.config import load_course_plans  # noqa: E402

SAMPLE = """
courses:
  - name: 测试课程
    course_code: "00000000"
    classes:
      - name: 测试课程-0001A
        weekday: 星期四
        start_period: 3
        end_period: 4
        room: N6101
        experiments:
          - project: Alpha
            weeks: [1, 3]
          - project: Beta
            weeks: [4, 7]
            weekday: 星期五
            start_period: 6
            end_period: 7
            room: N6111
"""


def write_sample(tmp: Path) -> Path:
    path = tmp / "courses.yaml"
    path.write_text(SAMPLE, encoding="utf-8")
    return path


def test_loads_class_and_experiments(tmp_path: Path) -> None:
    plans = load_course_plans(write_sample(tmp_path))
    assert len(plans) == 1
    course = plans[0]
    assert course.course_code == "00000000"
    assert len(course.classes) == 1

    cls = course.classes[0]
    assert cls.name == "测试课程-0001A"
    assert cls.weekday == "星期四"
    assert cls.room == "N6101"
    assert len(cls.experiments) == 2


def test_experiment_uses_class_defaults(tmp_path: Path) -> None:
    plans = load_course_plans(write_sample(tmp_path))
    cls = plans[0].classes[0]
    slot = cls.slot_for(cls.experiments[0])
    assert (slot.start_week, slot.end_week) == (1, 3)
    assert slot.weekday == "星期四"
    assert (slot.start_period, slot.end_period) == (3, 4)
    assert slot.room == "N6101"


def test_experiment_overrides_class_defaults(tmp_path: Path) -> None:
    plans = load_course_plans(write_sample(tmp_path))
    cls = plans[0].classes[0]
    slot = cls.slot_for(cls.experiments[1])
    assert (slot.start_week, slot.end_week) == (4, 7)
    assert slot.weekday == "星期五"
    assert (slot.start_period, slot.end_period) == (6, 7)
    assert slot.room == "N6111"


def test_slot_describe_is_readable(tmp_path: Path) -> None:
    plans = load_course_plans(write_sample(tmp_path))
    cls = plans[0].classes[0]
    slot = cls.slot_for(cls.experiments[0])
    assert slot.describe == "第1-3周 星期四 3-4节 @N6101"


def test_invalid_weeks_rejected(tmp_path: Path) -> None:
    path = tmp_path / "courses.yaml"
    path.write_text(
        "courses:\n  - name: X\n    classes:\n"
        "      - name: X-1\n        experiments:\n"
        "          - project: A\n            weeks: [1]\n",
        encoding="utf-8",
    )
    try:
        load_course_plans(path)
    except ValueError:
        return
    raise AssertionError("weeks 只有一个值时应抛出 ValueError")
