"""配置加载：站点地址、登录凭据、课程排课计划。

配置查找顺序（先命中先用）：

1. 环境变量 ``LABREG_HOME`` 指定的目录
2. 当前工作目录
3. 源码仓库根目录（即本文件的上级目录）

这样无论是从源码目录运行、pip 安装后在任意目录运行，
还是用 ``labreg init`` 在新目录初始化，都能找到对应的配置。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PACKAGE_ROOT.parent


def _candidate_roots() -> list[Path]:
    roots: list[Path] = []
    override = os.getenv("LABREG_HOME", "").strip()
    if override:
        roots.append(Path(override).expanduser())
    roots.append(Path.cwd())
    roots.append(SOURCE_ROOT)
    seen: set[Path] = set()
    unique: list[Path] = []
    for root in roots:
        resolved = root.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def _find_root(relative: str) -> Path:
    """在候选目录中查找包含 relative 的第一个目录。"""
    roots = _candidate_roots()
    for root in roots:
        if (root / relative).exists():
            return root
    return roots[0]


PROJECT_ROOT = _find_root(".env")
ENV_FILE = PROJECT_ROOT / ".env"
CONFIG_DIR = PROJECT_ROOT / "configs"
VAR_DIR = PROJECT_ROOT / "var"


@dataclass(frozen=True)
class Settings:
    """运行期站点与凭据设置。"""

    base_url: str
    username: str = ""
    password: str = ""
    timeout: int = 30
    verify_ssl: bool = True


def load_settings(env_file: Path | None = None) -> Settings:
    """从 .env 读取站点设置；缺少 .env 时抛出明确错误。"""
    path = Path(env_file) if env_file else ENV_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"未找到环境配置文件：{path}\n"
            f"请复制 {PROJECT_ROOT / '.env.example'} 为 .env 并填写站点信息。"
        )
    load_dotenv(path, override=True)

    base_url = os.getenv("BASE_URL", "").strip().rstrip("/")
    if not base_url:
        raise ValueError(".env 中必须提供 BASE_URL")

    return Settings(
        base_url=base_url,
        username=os.getenv("USERNAME", "").strip(),
        password=os.getenv("PASSWORD", ""),
        timeout=int(os.getenv("TIMEOUT", "30") or 30),
        verify_ssl=os.getenv("VERIFY_SSL", "1") not in {"0", "false", "False"},
    )


@dataclass
class SlotPlan:
    """单个实验的时间位置。"""

    start_week: int
    end_week: int
    weekday: str
    start_period: int
    end_period: int
    room: str

    @property
    def describe(self) -> str:
        """人类可读描述，与计划文件中的写法一致。"""
        return (f"第{self.start_week}-{self.end_week}周 {self.weekday} "
                f"{self.start_period}-{self.end_period}节 @{self.room}")


@dataclass
class ExperimentPlan:
    """一个实验项目及其排课位置。"""

    project: str          # 项目名称关键字，用于匹配任务行
    slot: SlotPlan

    @property
    def describe(self) -> str:
        s = self.slot
        return (f"第{s.start_week}-{s.end_week}周 {s.weekday} "
                f"{s.start_period}-{s.end_period}节 @{s.room}")


@dataclass
class ClassPlan:
    """一个教学班的排课计划。"""

    name: str                   # 示例课程-0001A
    course_code: str = ""       # 留空则从站点列表匹配
    weekday: str = "星期四"
    start_period: int = 1
    end_period: int = 2
    room: str = ""
    experiments: list[ExperimentPlan] = field(default_factory=list)
    batches: int = 1

    def slot_for(self, experiment: ExperimentPlan) -> SlotPlan:
        """取该实验最终生效的时间位置。

        加载配置时已把实验级覆盖合并进 experiment.slot，
        因此这里直接返回，避免班级默认值盖掉实验级定制。
        """
        return experiment.slot


@dataclass
class CoursePlan:
    """一个课程的排课计划。"""

    name: str
    course_code: str = ""
    classes: list[ClassPlan] = field(default_factory=list)


def load_course_plans(config_path: Path) -> list[CoursePlan]:
    """读取课程排课计划 YAML。

    预期结构：
        courses:
          - name: 示例课程
            course_code: "00000000"
            classes:
              - name: 示例课程-0001A
                weekday: 星期四
                start_period: 3
                end_period: 4
                room: N0000
                experiments:
                  - project: Redis
                    weeks: [1, 3]
    """
    data = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    plans: list[CoursePlan] = []
    for course in data.get("courses", []) or []:
        classes: list[ClassPlan] = []
        for cls in course.get("classes", []) or []:
            experiments = []
            for exp in cls.get("experiments", []) or []:
                weeks = exp.get("weeks") or []
                if len(weeks) != 2:
                    raise ValueError(
                        f"{cls.get('name')} / {exp.get('project')} 的 weeks 需为 [起始周, 结束周]"
                    )
                experiments.append(
                    ExperimentPlan(
                        project=str(exp["project"]),
                        slot=SlotPlan(
                            start_week=int(weeks[0]),
                            end_week=int(weeks[1]),
                            weekday=str(exp.get("weekday", cls.get("weekday", "星期四"))),
                            start_period=int(exp.get("start_period",
                                                      cls.get("start_period", 1))),
                            end_period=int(exp.get("end_period", cls.get("end_period", 2))),
                            room=str(exp.get("room", cls.get("room", ""))),
                        ),
                    )
                )
            classes.append(
                ClassPlan(
                    name=str(cls["name"]),
                    course_code=str(cls.get("course_code", course.get("course_code", ""))),
                    weekday=str(cls.get("weekday", "星期四")),
                    start_period=int(cls.get("start_period", 1)),
                    end_period=int(cls.get("end_period", 2)),
                    room=str(cls.get("room", "")),
                    experiments=experiments,
                    batches=int(cls.get("batches", 1)),
                )
            )
        plans.append(
            CoursePlan(
                name=str(course["name"]),
                course_code=str(course.get("course_code", "")),
                classes=classes,
            )
        )
    return plans
