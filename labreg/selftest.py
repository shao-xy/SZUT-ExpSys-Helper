"""自检：不接触站点，验证本地安装与配置是否可用。

供使用者在正式排课前快速确认环境无误。
"""

from __future__ import annotations

from dataclasses import dataclass

from . import config as config_mod
from .scaffold import skill_source_dir


@dataclass
class SelfTestItem:
    name: str
    ok: bool
    detail: str
    hint: str = ""


def run_selftest() -> list[SelfTestItem]:
    """执行本地自检，返回逐项结果。"""
    items: list[SelfTestItem] = []

    # 依赖
    missing = []
    for module, package in (("requests", "requests"), ("yaml", "PyYAML"),
                             ("dotenv", "python-dotenv"), ("lxml", "lxml"),
                             ("Crypto", "pycryptodome"), ("ddddocr", "ddddocr")):
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    items.append(SelfTestItem(
        "依赖包", not missing,
        "全部就绪" if not missing else f"缺少：{', '.join(missing)}",
        "执行 pip install -r requirements.txt",
    ))

    # 生效的工作区
    items.append(SelfTestItem(
        "工作区", True, str(config_mod.PROJECT_ROOT),
        "可用环境变量 LABREG_HOME 指定其他工作区",
    ))

    # 配置文件
    env_file = config_mod.ENV_FILE
    items.append(SelfTestItem(
        ".env", env_file.exists(), str(env_file),
        "执行 `labreg init` 生成模板，然后填写站点地址与账号密码",
    ))

    # 排课计划
    courses_file = config_mod.CONFIG_DIR / "courses.yaml"
    items.append(SelfTestItem(
        "排课计划", courses_file.exists(), str(courses_file),
        "执行 `labreg init` 生成模板，然后填写课程、班级与周次",
    ))

    # Skill
    skill_dir = skill_source_dir()
    items.append(SelfTestItem(
        "Agent Skill", (skill_dir / "SKILL.md").exists(), str(skill_dir),
        "包内缺少 SKILL.md，请重新安装本工具",
    ))

    # 配置解析
    if env_file.exists():
        try:
            settings = config_mod.load_settings()
            items.append(SelfTestItem(
                "配置解析", True,
                f"站点 {settings.base_url}，账号 {settings.username or '(未填写)'}",
                "请在 .env 中填写 USERNAME 与 PASSWORD",
            ))
        except Exception as exc:  # noqa: BLE001
            items.append(SelfTestItem("配置解析", False, str(exc),
                                      "请检查 .env 中的 BASE_URL 等字段"))
    else:
        items.append(SelfTestItem("配置解析", False, "未找到 .env",
                                  "执行 `labreg init` 生成模板"))

    # 计划解析
    if courses_file.exists():
        try:
            plans = config_mod.load_course_plans(courses_file)
            count = sum(len(c.experiments) for c in plans for c in c.classes)
            items.append(SelfTestItem(
                "计划解析", bool(plans),
                f"{len(plans)} 门课程，共 {count} 项实验安排",
                "请在 configs/courses.yaml 中填写 courses",
            ))
        except Exception as exc:  # noqa: BLE001
            items.append(SelfTestItem("计划解析", False, str(exc),
                                      "请检查 courses.yaml 的缩进与字段写法"))
    else:
        items.append(SelfTestItem("计划解析", False, "未找到 courses.yaml",
                                  "执行 `labreg init` 生成模板"))

    return items
