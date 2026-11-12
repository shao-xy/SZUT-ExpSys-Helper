"""配置层与输出层的回归测试。

不联网，只用临时文件验证计划解析与覆盖规则。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from labreg.config import load_course_plans, normalize_parity  # noqa: E402

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

PARITY_SAMPLE = """
courses:
  - name: 测试课程
    course_code: "00000000"
    classes:
      - name: 测试课程-0002A
        weekday: 星期二
        start_period: 1
        end_period: 2
        room: N0000
        parity: 单周
        experiments:
          - project: Gamma
            weeks: [9, 9]
          - project: Delta
            weeks: [10, 12]
            parity: 双周
          - project: Epsilon
            weeks: [1, 4]
            parity: 每周
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


def test_parity_defaults_to_every_week(tmp_path: Path) -> None:
    plans = load_course_plans(write_sample(tmp_path))
    cls = plans[0].classes[0]
    assert cls.parity == ""
    assert cls.slot_for(cls.experiments[0]).parity == ""


def test_parity_inherited_from_class(tmp_path: Path) -> None:
    path = tmp_path / "courses.yaml"
    path.write_text(PARITY_SAMPLE, encoding="utf-8")
    cls = load_course_plans(path)[0].classes[0]
    assert cls.parity == "单周"
    assert cls.slot_for(cls.experiments[0]).parity == "单周"


def test_parity_overridden_by_experiment(tmp_path: Path) -> None:
    path = tmp_path / "courses.yaml"
    path.write_text(PARITY_SAMPLE, encoding="utf-8")
    cls = load_course_plans(path)[0].classes[0]
    assert cls.slot_for(cls.experiments[1]).parity == "双周"
    # 「每周」应被规范化为空值，即站点上的留空
    assert cls.slot_for(cls.experiments[2]).parity == ""


def test_parity_appears_in_describe(tmp_path: Path) -> None:
    path = tmp_path / "courses.yaml"
    path.write_text(PARITY_SAMPLE, encoding="utf-8")
    cls = load_course_plans(path)[0].classes[0]
    assert cls.slot_for(cls.experiments[0]).describe == "第9-9周 星期二 1-2节 @N0000 单周"


def test_normalize_parity_accepts_aliases() -> None:
    assert normalize_parity("") == ""
    assert normalize_parity("每周") == ""
    assert normalize_parity("all") == ""
    assert normalize_parity("单周") == "单周"
    assert normalize_parity(" 双周 ") == "双周"


def test_normalize_parity_rejects_invalid() -> None:
    try:
        normalize_parity("隔周", "某班")
    except ValueError as exc:
        assert "隔周" in str(exc)
        return
    raise AssertionError("非法 parity 应抛出 ValueError")
