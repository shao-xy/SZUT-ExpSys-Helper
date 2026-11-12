"""页面解析层的回归测试。

用构造的 HTML 片段验证表格、下拉、复选组与时间解析，
不依赖真实站点，避免协议变动时静默出错。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from labreg import pages  # noqa: E402

TASK_ROWS_HTML = """
<table id="gvUser">
  <tr>
    <td>1</td>
    <td>高级数据库技术[09300389]</td>
    <td>高级数据库技术-0001A</td>
    <td>键值对数据库Redis [09300389001]</td>
    <td>47人</td>
    <td><a href="jskclist.aspx?coursecode=09300389&amp;kxh=x&amp;rwid=72732&amp;xmid=37514">进入确认</a></td>
    <td><a href="jsfzlist.aspx?coursecode=09300389&amp;kxh=x&amp;rwid=72732&amp;xmid=37514">进入分批</a></td>
    <td>3</td>
    <td><a href="fzKeBiao.aspx?coursecode=09300389&amp;kxh=x&amp;rwid=72732&amp;xmid=37514">进入制定</a></td>
  </tr>
</table>
"""

CLASS_ROWS_HTML = """
<table id="gvUser">
  <tr>
    <td>高级数据库技术[09300389]</td>
    <td>高级数据库技术-0001A</td>
    <td><a href="kbjxlist.aspx?coursecode=09300389&amp;kxh=x">进入制定</a></td>
  </tr>
</table>
"""

WEEKDAY_HTML = """
<table id="cblweek">
  <tr><td><span alt="1"><input type="checkbox" name="cblweek$0" /></span>星期一</td></tr>
  <tr><td><span alt="4"><input type="checkbox" name="cblweek$3" /></span>星期四</td></tr>
</table>
"""

SCHEDULE_ROWS_HTML = """
<table class="table">
  <tr>
    <td>0931231(第1批)</td><td>邵新洋</td>
    <td>2026-09-24 09:50 - 11:25 第3周 [星期四] 3 -4节</td>
    <td>N6101</td>
    <td><a id="Repeater1_ctl01_lbdel" onclick="__doPostBack('Repeater1$ctl01$lbdel','')">删除</a></td>
  </tr>
</table>
"""


def test_parse_task_rows() -> None:
    tree = pages.parse(TASK_ROWS_HTML)
    rows = pages.parse_course_rows(tree)
    assert len(rows) == 1
    row = rows[0]
    assert row.name == "高级数据库技术-0001A"
    assert row.course_code == "09300389"
    assert row.course_name == "高级数据库技术"
    assert row.project_name == "键值对数据库Redis [09300389001]"
    assert row.scheduled_count == "3"
    assert row.params["rwid"] == "72732"
    assert row.params["xmid"] == "37514"


def test_parse_class_rows() -> None:
    tree = pages.parse(CLASS_ROWS_HTML)
    rows = pages.parse_class_rows(tree)
    assert len(rows) == 1
    assert rows[0].name == "高级数据库技术-0001A"
    assert rows[0].course_code == "09300389"
    assert rows[0].params["coursecode"] == "09300389"


def test_parse_weekday_options() -> None:
    tree = pages.parse(WEEKDAY_HTML)
    boxes = pages.parse_weekday_options(tree)
    assert ("cblweek$3", "4") in boxes


def test_parse_schedule_rows() -> None:
    tree = pages.parse(SCHEDULE_ROWS_HTML)
    rows = pages.parse_schedule_rows(tree)
    assert len(rows) == 1
    assert rows[0]["place"] == "N6101"
    assert rows[0]["delete_id"] == "Repeater1_ctl01_lbdel"
    assert "第3周" in rows[0]["time"]


def test_parse_row_time() -> None:
    parsed = pages.parse_row_time("2026-09-24 09:50 - 11:25 第3周 [星期四] 3 -4节")
    assert parsed is not None
    assert parsed.week == 3
    assert parsed.weekday == "星期四"
    assert (parsed.start_period, parsed.end_period) == (3, 4)
    assert parsed.clock == "09:50-11:25"


def test_parse_row_time_rejects_garbage() -> None:
    assert pages.parse_row_time("无") is None


def test_parse_weeks_of_row() -> None:
    text = "第1周 [星期四] 3-4节 / 第2周 [星期四] 3-4节"
    assert pages.parse_weeks_of_row(text) == [1, 2]
