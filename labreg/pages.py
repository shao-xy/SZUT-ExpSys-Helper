"""页面解析：把站点 HTML 转换为结构化数据。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlparse

from lxml import html as lhtml

# 站点页面地址（相对站点根）
PAGE_COURSE_LIST = "admin/kebiao/kbjxlist2.aspx"
PAGE_TASK_LIST = "admin/kebiao/kbjxlist.aspx"
PAGE_CONFIRM = "admin/kebiao/jskclist.aspx"
PAGE_GROUP = "admin/kebiao/jsfzlist.aspx"
PAGE_GROUP_FORM = "admin/kebiao/xsteam.aspx"
PAGE_SCHEDULE = "admin/kebiao/fzKeBiao.aspx"
PAGE_BATCH_SCHEDULE = "admin/kebiao/plkb2.aspx"
PAGE_SCHEDULE_VIEW = "admin/kebiao/JsKeBiaoView.aspx"


def parse(html_text: str):
    """将 HTML 文本解析为 DOM。

    显式指定 UTF-8 编码：lxml 在页面缺少 meta 声明时可能按 latin-1 解析，
    导致中文乱码，进而使名称匹配与时间解析失效。
    """
    parser = lhtml.HTMLParser(encoding="utf-8")
    return lhtml.fromstring(html_text.encode("utf-8"), parser=parser)


def text_of(node) -> str:
    return " ".join(node.text_content().split())


def options(tree, select_id: str) -> list[tuple[str, str]]:
    """读取下拉框的 (value, 文本) 列表。"""
    found = tree.xpath(f"//select[@id='{select_id}']/option")
    return [(o.get("value") or "", text_of(o)) for o in found]


def option_map(tree, select_id: str) -> dict[str, str]:
    return dict(options(tree, select_id))


def hidden(tree, element_id: str) -> str:
    values = tree.xpath(f"//input[@id='{element_id}']/@value")
    return values[0] if values else ""


@dataclass
class CourseRow:
    """班级课程行（制订课表页面的一行）。"""

    name: str          # 示例课程-0001A
    course_code: str   # 00000000
    course_name: str   # 示例课程
    project_name: str  # 示例实验项目 [00000000001]
    selected_students: str
    confirm_url: str
    group_url: str
    schedule_url: str
    scheduled_count: str

    @property
    def params(self) -> dict[str, str]:
        """从任意一个任务链接中取出 coursecode / kxh / rwid / xmid。"""
        raw = self.schedule_url or self.confirm_url or self.group_url
        return {k: v for k, v in parse_qsl(urlparse(raw).query)}


@dataclass
class ClassRow:
    """课程列表页的一行（一个教学班）。"""

    name: str          # 示例课程-0001A
    course_code: str   # 00000000
    course_name: str   # 示例课程
    task_url: str      # kbjxlist.aspx?...&coursecode=..&kxh=..

    @property
    def params(self) -> dict[str, str]:
        return {k: v for k, v in parse_qsl(urlparse(self.task_url).query)}


@dataclass
class ConfirmState:
    """确认学生页状态。"""

    confirmed: int
    matched: int
    quote_button: str  # 引用按钮的 input name


def parse_class_rows(tree) -> list[ClassRow]:
    """解析 kbjxlist2 的班级表格（课程名称 / 课序号 / 制定课表）。"""
    rows: list[ClassRow] = []
    for tr in _data_rows(tree, "gvUser"):
        cells = tr.xpath("./td")
        if len(cells) < 3:
            continue
        links = cells[2].xpath(".//a/@href")
        course_cell = text_of(cells[0])
        code_match = re.search(r"\[([^\]]+)\]", course_cell)
        rows.append(
            ClassRow(
                name=text_of(cells[1]),
                course_code=code_match.group(1) if code_match else "",
                course_name=re.sub(r"\s*\[[^\]]+\]\s*$", "", course_cell).strip(),
                task_url=links[0] if links else "",
            )
        )
    return rows


def _data_rows(tree, table_id: str):
    """取出表格中的数据行（含 td 的行），跳过表头。

    比 tr[position()>1] 更稳健：页面有无表头都能正确处理。
    """
    for tr in tree.xpath(f"//table[@id='{table_id}']/tr"):
        if tr.xpath("./td"):
            yield tr


def parse_course_rows(tree) -> list[CourseRow]:
    """解析 kbjxlist 的任务表格。"""
    rows: list[CourseRow] = []
    for tr in _data_rows(tree, "gvUser"):
        cells = tr.xpath("./td")
        if len(cells) < 9:
            continue
        links = cells[8].xpath(".//a/@href")
        confirm_links = cells[5].xpath(".//a/@href")
        group_links = cells[6].xpath(".//a/@href")
        course_cell = text_of(cells[1])
        code_match = re.search(r"\[([^\]]+)\]", course_cell)
        project_cell = text_of(cells[3])
        rows.append(
            CourseRow(
                name=text_of(cells[2]),
                course_code=code_match.group(1) if code_match else "",
                course_name=re.sub(r"\s*\[[^\]]+\]\s*$", "", course_cell).strip(),
                project_name=project_cell,
                selected_students=text_of(cells[4]),
                confirm_url=confirm_links[0] if confirm_links else "",
                group_url=group_links[0] if group_links else "",
                schedule_url=links[0] if links else "",
                scheduled_count=text_of(cells[7]),
            )
        )
    return rows


def parse_confirm_state(tree) -> ConfirmState:
    """解析确认学生页。"""
    count = tree.xpath("//span[@id='qrxscount']/text()")
    confirmed = int(count[0].strip()) if count and count[0].strip().isdigit() else 0

    matched = 0
    for tr in _data_rows(tree, "gridview"):
        cells = tr.xpath("./td")
        if len(cells) >= 2:
            digits = re.findall(r"\d+", text_of(cells[1]))
            if digits:
                matched = int(digits[0])
            break

    buttons = tree.xpath("//input[@value='引用']/@name")
    return ConfirmState(confirmed=confirmed, matched=matched,
                         quote_button=buttons[0] if buttons else "")


def parse_pending_students(tree) -> list[str]:
    """待分批学生复选框的 name 列表。"""
    return tree.xpath("//input[starts-with(@name,'skxyid$')]/@name")


def parse_batch_summaries(tree) -> list[str]:
    """已有分批的概要文本，形如 “第 1 批(47人)”。"""
    summaries = []
    for row in tree.xpath("//table[@id='DataList_fxqk']/tr"):
        text = text_of(row)
        m = re.search(r"第\s*\d+\s*批\s*[（(]\s*\d+\s*人\s*[)）]", text)
        if m:
            summaries.append(m.group(0).replace(" ", ""))
    return summaries


def parse_room_options(tree) -> dict[str, str]:
    """ddlfj 下拉的 (value, 文本)。"""
    return option_map(tree, "ddlfj")


def parse_lab_options(tree) -> dict[str, str]:
    """ddllab 下拉的 (value, 文本)，即实验室别名。"""
    return option_map(tree, "ddllab")


def parse_experiment_options(tree) -> dict[str, str]:
    """ddlxm 下拉的 (value, 文本)，即实验项目。"""
    return option_map(tree, "ddlxm")


def parse_batch_options(tree) -> list[tuple[str, str]]:
    """cblxs 学生批次复选组，返回 [(复选框 name, 批次 ID)]。"""
    result = []
    for span in tree.xpath("//table[@id='cblxs']//span[@alt]"):
        boxes = span.xpath(".//input[@type='checkbox']/@name")
        if boxes:
            result.append((boxes[0], span.get("alt")))
    return result


def parse_weekday_options(tree) -> list[tuple[str, str]]:
    """cblweek 星期复选组，返回 [(复选框 name, 星期序号)]。"""
    result = []
    for span in tree.xpath("//table[@id='cblweek']//span[@alt]"):
        boxes = span.xpath(".//input[@type='checkbox']/@name")
        if boxes:
            result.append((boxes[0], span.get("alt")))
    return result


def parse_schedule_rows(tree) -> list[dict[str, Any]]:
    """解析排课页上方已排课表格。"""
    rows = []
    for tr in tree.xpath("//table[contains(@class,'table')]/tr[td]"):
        cells = tr.xpath("./td")
        if len(cells) < 4:
            continue
        delete = tr.xpath(".//a[contains(@id,'lbdel')]/@id")
        rows.append({
            "classes": text_of(cells[0]),
            "teachers": text_of(cells[1]),
            "time": text_of(cells[2]),
            "place": text_of(cells[3]),
            "delete_id": delete[0] if delete else "",
        })
    return rows


def parse_weeks_of_row(time_text: str) -> list[int]:
    """从“第1周 [星期四] 3-4节”中提取周次列表。"""
    return [int(m) for m in re.findall(r"第\s*(\d+)\s*周", time_text)]


@dataclass
class RowTime:
    """已排课记录中的时间信息。"""

    week: int
    weekday: str
    start_period: int
    end_period: int
    clock: str      # 如 09:50-11:25


def parse_row_time(time_text: str) -> RowTime | None:
    """解析“第3周 [星期四] 3-4节”形式的上课时间。"""
    week_match = re.search(r"第\s*(\d+)\s*周", time_text)
    weekday_match = re.search(r"\[([^\]]+)\]", time_text)
    period_match = re.search(r"(\d+)\s*-\s*(\d+)\s*节", time_text)
    if not (week_match and period_match):
        return None
    clock = ""
    clock_match = re.search(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})", time_text)
    if clock_match:
        clock = f"{clock_match.group(1)}-{clock_match.group(2)}"
    return RowTime(
        week=int(week_match.group(1)),
        weekday=weekday_match.group(1) if weekday_match else "",
        start_period=int(period_match.group(1)),
        end_period=int(period_match.group(2)),
        clock=clock,
    )


def parse_grade_info(tree) -> str:
    """读取页面提示信息（成功或失败）。"""
    for xpath in ("//*[@id='lblMessage']/text()", "//div[@class='alert']//text()"):
        texts = [" ".join(t.split()) for t in tree.xpath(xpath) if t and t.strip()]
        if texts:
            return "；".join(texts)
    return ""
