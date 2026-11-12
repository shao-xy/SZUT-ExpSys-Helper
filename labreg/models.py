"""领域模型说明。

排课相关的数据结构集中在 config.py（计划）与 workflow.py（执行过程），
本模块仅保留供外部调用的轻量结果类型。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TaskSummary:
    """站点上的一个实验任务行摘要。"""

    class_name: str
    course_name: str
    project_name: str
    confirmed: int
    matched: int
    pending_group: int
    scheduled: int
