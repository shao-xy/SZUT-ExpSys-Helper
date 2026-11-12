"""排课流程编排。

一个“实验安排”包含三步：确认学生 → 学生分批 → 制定课表。
每一步都以 (班级, 实验项目) 为单位，因此同一课程的多个实验需各自走一遍。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from urllib.parse import urlencode

from . import pages
from .client import SiteClient

logger = logging.getLogger(__name__)

# 星期复选框的 alt 值，站点用它标识星期几
WEEKDAY_ALT = {
    "星期一": "1", "星期二": "2", "星期三": "3", "星期四": "4",
    "星期五": "5", "星期六": "6", "星期日": "7",
}


@dataclass
class Slot:
    """一个实验的时间位置。"""

    start_week: int
    end_week: int
    weekday: str          # 星期四
    start_period: int     # 3
    end_period: int       # 4
    room: str             # 教室名，如 N0000
    lab_alias: str = ""   # 实验室别名，如 算法设计实验室

    def __str__(self) -> str:
        return (f"第{self.start_week}-{self.end_week}周 {self.weekday} "
                f"{self.start_period}-{self.end_period}节 @{self.room}")

    @property
    def describe(self) -> str:
        """与计划文件中的写法一致的描述。"""
        return (f"第{self.start_week}-{self.end_week}周 {self.weekday} "
                f"{self.start_period}-{self.end_period}节 @{self.room}")


@dataclass
class SchedulePlan:
    """一个课程的完整排课计划。"""

    course_code: str                 # 00000000
    course_name: str                 # 示例课程
    class_name: str                  # 示例课程-0001A
    slots: list[Slot] = field(default_factory=list)

    @property
    def has_parity(self) -> bool:
        """单双周。站点只提供“单周/双周”选项，每周排课即不勾选。"""
        return False


@dataclass
class StepResult:
    ok: bool
    message: str


@dataclass
class SlotForm:
    """一次排课提交所需的表单数据与关联标识。"""

    data: dict[str, str]
    url: str
    room_id: str
    lab_id: str
    batch_ids: list[str]
    teacher_id: str
    time_text: str


class Scheduler:
    """封装站点排课相关的全部操作。"""

    def __init__(self, client: SiteClient) -> None:
        self.client = client

    # ---------- 公共查询串 ----------

    def build_query(self, course_code: str, class_name: str,
                    rwid: str, xmid: str) -> str:
        """构造课程任务页所需的公共查询串。"""
        params = {
            "coursecode": course_code,
            "kxh": class_name,
            "rwid": rwid,
            "xmid": xmid,
        }
        params.update(self.client.common_params)
        return urlencode(params)

    # ---------- 课程与任务列表 ----------

    def list_classes(self) -> list[pages.ClassRow]:
        """读取站点上可排课的全部班级。"""
        params = dict(self.client.common_params)
        tree = self.client.tree(f"{pages.PAGE_COURSE_LIST}?{urlencode(params)}")
        return pages.parse_class_rows(tree)

    def list_task_rows(self, course_code: str, class_name: str) -> list[pages.CourseRow]:
        """读取某班级下的全部实验任务行。"""
        params = {"coursecode": course_code, "kxh": class_name}
        params.update(self.client.common_params)
        tree = self.client.tree(f"{pages.PAGE_TASK_LIST}?{urlencode(params)}")
        return pages.parse_course_rows(tree)

    # ---------- 第一步：确认学生 ----------

    def confirm_students(self, course_code: str, class_name: str,
                         rwid: str, xmid: str) -> StepResult:
        """点击“引用”导入匹配班级的全部学生。"""
        query = self.build_query(course_code, class_name, rwid, xmid)
        tree = self.client.tree(f"{pages.PAGE_CONFIRM}?{query}")
        state = pages.parse_confirm_state(tree)

        if state.matched == 0:
            return StepResult(False, "未匹配到可引用的课程，请先提交任务书")
        if state.confirmed >= state.matched:
            return StepResult(True, f"学生已确认 {state.confirmed}/{state.matched}")
        if not state.quote_button:
            return StepResult(False, "未找到“引用”按钮")

        data = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": "",
            state.quote_button: "引用",
        }
        files = {"FileUpload1": ("", "")}
        self.client.post(f"{pages.PAGE_CONFIRM}?{query}", data=data, files=files)
        # 回发响应中的计数可能为提交前状态，需重新拉取页面确认
        after = pages.parse_confirm_state(self.client.tree(f"{pages.PAGE_CONFIRM}?{query}"))
        if after.matched and after.confirmed >= after.matched:
            return StepResult(True, f"已引用 {after.confirmed} 名学生")
        return StepResult(False, f"引用后学生数仍为 {after.confirmed}/{after.matched}")

    # ---------- 第二步：学生分批 ----------

    def group_students(self, course_code: str, class_name: str,
                       rwid: str, xmid: str, batches: int = 1) -> StepResult:
        """全选学生并一次性分为指定批数。"""
        query = self.build_query(course_code, class_name, rwid, xmid)
        tree = self.client.tree(f"{pages.PAGE_GROUP_FORM}?{query}")

        pending = pages.parse_pending_students(tree)
        if not pending:
            existing = pages.parse_batch_summaries(tree)
            if existing:
                return StepResult(True, f"已存在分批：{existing[0]}")
            return StepResult(False, "没有待分批学生（可能尚未确认学生）")

        data: dict[str, str] = {
            "ddlbj": "0",
            "fzs": str(batches),
            "Button_FZ": "确认分批",
            "CheckBox1": "on",
        }
        for name in pending:
            data[name] = "on"
        self.client.post(f"{pages.PAGE_GROUP_FORM}?{query}", data=data)
        # 回发响应可能仍是提交前状态，重新拉取页面确认
        tree = self.client.tree(f"{pages.PAGE_GROUP_FORM}?{query}")
        remaining = pages.parse_pending_students(tree)
        summaries = pages.parse_batch_summaries(tree)
        if not remaining and summaries:
            return StepResult(True, f"分批完成：{summaries[0]}")
        return StepResult(False, f"分批未完成，剩余 {len(remaining)} 人未分批")

    # ---------- 删除已有排课 ----------

    def delete_schedule(self, course_code: str, class_name: str, rwid: str,
                        xmid: str, delete_id: str) -> StepResult:
        """按表格中的删除控件 id 删除一条已有排课。

        delete_id 形如 Repeater1_ctl01_lbdel。
        """
        query = self.build_query(course_code, class_name, rwid, xmid)
        event_target = delete_id.replace("_", "$")
        before = len(pages.parse_schedule_rows(
            self.client.tree(f"{pages.PAGE_BATCH_SCHEDULE}?{query}")))
        self.client.post(
            f"{pages.PAGE_BATCH_SCHEDULE}?{query}",
            data={"__EVENTTARGET": event_target, "__EVENTARGUMENT": ""},
        )
        tree = self.client.tree(f"{pages.PAGE_BATCH_SCHEDULE}?{query}")
        after = len(pages.parse_schedule_rows(tree))
        if after < before:
            return StepResult(True, f"已删除 {delete_id}")
        return StepResult(False, f"删除 {delete_id} 未生效")

    # ---------- 冲突预检 ----------

    def check_conflicts(self, course_code: str, class_name: str, rwid: str,
                        xmid: str, slot: Slot, room_id: str,
                        batch_ids: list[str], teacher_id: str) -> list[str]:
        """调用站点的三个校验接口，返回冲突说明列表。

        站点在提交前会检查教师、学生、机房三类冲突。
        """
        weeks = f"{WEEKDAY_ALT.get(slot.weekday, '1')},"
        common = (f"kbid=&zc1={slot.start_week}&zc2={slot.end_week}"
                  f"&jie1={slot.start_period}&jie2={slot.end_period}"
                  f"&weeks={weeks}&coursecode={course_code}")
        xsteams = "".join(f"{bid}," for bid in batch_ids)

        checks = [
            (f"admin/ashx/checkjs.ashx?jsid={teacher_id}&{common}", "教师"),
            (f"admin/ashx/checkxs.ashx?xsteams={xsteams}&{common}", "学生"),
            (f"admin/ashx/checkfj.ashx?fjid={room_id}&{common}", "机房"),
        ]
        messages: list[str] = []
        for url, label in checks:
            text = self.client.text(f"{url}").strip()
            if text:
                messages.append(f"{label}：{' '.join(text.split())}")
        return messages

    # ---------- 第三步：制定课表 ----------

    def _room_mapping(self, course_code: str, class_name: str,
                      rwid: str, xmid: str) -> dict[str, tuple[str, str]]:
        """建立 教室名 → (实验室别名 id, 机房 id) 的映射。

        站点先选实验室别名，再由别名级联出具体机房，故需逐个别名探测。
        """
        query = self.build_query(course_code, class_name, rwid, xmid)
        url = f"{pages.PAGE_BATCH_SCHEDULE}?{query}"
        tree = self.client.tree(url)
        labs = pages.parse_lab_options(tree)

        mapping: dict[str, tuple[str, str]] = {}
        for lab_id, lab_name in labs.items():
            if lab_id == "0":
                continue
            resp = self.client.post(url, data={
                "__EVENTTARGET": "ddllab",
                "ddllab": lab_id,
                "ddlxm": xmid,
            })
            tree = pages.parse(resp.text)
            for room_id, room_text in pages.parse_room_options(tree).items():
                if room_id == "0":
                    continue
                # 房间文本形如 “N0000[校区-楼栋-房号]”，取方括号前的房号
                room_no = room_text.split("[")[0].strip()
                mapping.setdefault(room_no, (lab_id, room_id))
                mapping.setdefault(room_text, (lab_id, room_id))
        return mapping

    def find_room(self, course_code: str, class_name: str, rwid: str,
                  xmid: str, room: str) -> tuple[str, str] | None:
        """按教室名查找 (实验室别名 id, 机房 id)。"""
        mapping = self._room_mapping(course_code, class_name, rwid, xmid)
        if room in mapping:
            return mapping[room]
        # 容错：允许只写尾号，如 “101”
        for key, value in mapping.items():
            if key.endswith(room) or room in key:
                return value
        return None

    def _fill_slot(self, course_code: str, class_name: str, rwid: str,
                   xmid: str, slot: Slot) -> SlotForm | None:
        """按站点交互顺序填表。

        顺序为：选择实验室别名 → 选择起始节次 → 选择结束节次。
        每次选择都会触发回发，站点据此回填机房下拉与起止时间，因此必须逐步进行。
        """
        query = self.build_query(course_code, class_name, rwid, xmid)
        url = f"{pages.PAGE_BATCH_SCHEDULE}?{query}"

        room = self.find_room(course_code, class_name, rwid, xmid, slot.room)
        if room is None:
            logger.error("未找到教室 %s", slot.room)
            return None
        lab_id, room_id = room

        tree = self.client.tree(url)
        weekday_boxes = pages.parse_weekday_options(tree)
        batch_boxes = pages.parse_batch_options(tree)
        if not weekday_boxes:
            logger.error("排课页缺少星期复选框")
            return None
        if not batch_boxes:
            logger.error("排课页缺少学生批次，请先完成学生分批")
            return None

        target_alt = WEEKDAY_ALT.get(slot.weekday)
        if target_alt is None:
            logger.error("未知星期：%s", slot.weekday)
            return None

        base: dict[str, str] = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": "",
            "ddlxm": xmid,
            "ddlzc1": str(slot.start_week),
            "ddlzc2": str(slot.end_week),
            "ddldsz": "",            # 每周排课：不选单双周
            "ddljctype": "标准时间节次",
            "ddljie1": str(slot.start_period),
            "ddljie2": str(slot.end_period),
            "ddllab": lab_id,
            "ddlfj": room_id,
        }
        for box_name, alt in weekday_boxes:
            if alt == target_alt:
                base[box_name] = "on"
        for box_name, _ in batch_boxes[:1]:
            base[box_name] = "on"

        # 1) 选择实验室别名，触发机房级联
        resp = self.client.post(url, data={**base, "__EVENTTARGET": "ddllab"})
        tree = pages.parse(resp.text)
        if room_id not in pages.parse_room_options(tree):
            logger.warning("机房 %s 未出现在级联结果中，仍继续提交", room_id)

        # 2) 选择起始节次
        resp = self.client.post(url, data={**base, "__EVENTTARGET": "ddljie1"})
        tree = pages.parse(resp.text)

        # 3) 选择结束节次，站点在此回填起止时间
        resp = self.client.post(url, data={**base, "__EVENTTARGET": "ddljie2"})
        tree = pages.parse(resp.text)
        for field_name in ("tbshi", "tbfen", "tbshi2", "tbfen2"):
            value = pages.hidden(tree, field_name)
            if value:
                base[field_name] = value

        return SlotForm(
            data=base,
            url=url,
            room_id=room_id,
            lab_id=lab_id,
            batch_ids=[bid for _, bid in batch_boxes[:1]],
            teacher_id=pages.hidden(tree, "hiduid"),
            time_text=" ".join(
                f"{pages.hidden(tree, f)}" for f in ("tbshi", "tbfen", "tbshi2", "tbfen2")
            ),
        )

    def existing_rows(self, course_code: str, class_name: str,
                      rwid: str, xmid: str) -> list[dict]:
        """读取某实验项目当前的全部排课记录。"""
        query = self.build_query(course_code, class_name, rwid, xmid)
        tree = self.client.tree(f"{pages.PAGE_BATCH_SCHEDULE}?{query}")
        return pages.parse_schedule_rows(tree)

    def is_already_scheduled(self, rows: list[dict], slot: Slot) -> bool:
        """判断目标时间段是否已排课（按周次逐一比对）。

        站点每周生成一条记录，因此第1-3周会产生第1、2、3周共三条。
        """
        if not rows:
            return False
        expected = set(range(slot.start_week, slot.end_week + 1))
        matched: set[int] = set()
        for row in rows:
            parsed = pages.parse_row_time(row["time"])
            if parsed is None:
                continue
            if parsed.weekday != slot.weekday:
                continue
            if parsed.start_period != slot.start_period or parsed.end_period != slot.end_period:
                continue
            if slot.room and row["place"] and slot.room not in row["place"]:
                continue
            matched.add(parsed.week)
        return expected.issubset(matched)

    def schedule(self, course_code: str, class_name: str, rwid: str,
                 xmid: str, slot: Slot, force: bool = False,
                 skip_existing: bool = True) -> StepResult:
        """为某个实验项目的一个时间位置排课。

        force 为 True 时，即使存在冲突也继续提交。
        skip_existing 为 True 时，若目标时间段已排课则跳过。
        """
        query = self.build_query(course_code, class_name, rwid, xmid)
        before = self.client.tree(f"{pages.PAGE_BATCH_SCHEDULE}?{query}")
        before_rows = pages.parse_schedule_rows(before)

        if skip_existing and self.is_already_scheduled(before_rows, slot):
            return StepResult(True, f"已存在相同安排，跳过：{slot.describe}")

        form = self._fill_slot(course_code, class_name, rwid, xmid, slot)
        if form is None:
            return StepResult(False, f"排课失败：{slot.describe}")

        conflicts = self.check_conflicts(course_code, class_name, rwid, xmid,
                                         slot, form.room_id, form.batch_ids,
                                         form.teacher_id)
        if conflicts and not force:
            return StepResult(False, "存在冲突：" + "；".join(conflicts))
        if conflicts:
            logger.warning("强制排课，忽略冲突：%s", "；".join(conflicts))

        self.client.post(form.url, data={**form.data, "btnSubmit": "提 交"})

        after = self.client.tree(f"{pages.PAGE_BATCH_SCHEDULE}?{query}")
        after_rows = pages.parse_schedule_rows(after)
        if len(after_rows) > len(before_rows):
            latest = after_rows[0]
            return StepResult(True, f"排课成功：{latest['time']} @ {latest['place']}")
        return StepResult(False, f"排课未生效：{slot.describe}")
