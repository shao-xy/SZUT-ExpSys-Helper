"""脚手架：为新使用者生成可直接编辑的工作区文件。

只生成文本文件，不访问站点、不修改任何站点数据。
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


@dataclass
class ScaffoldResult:
    created: list[Path]
    skipped: list[Path]

    @property
    def any_created(self) -> bool:
        return bool(self.created)


def render_courses_template() -> str:
    return (TEMPLATE_DIR / "courses.yaml.template").read_text(encoding="utf-8")


def render_env_template() -> str:
    return (TEMPLATE_DIR / "env.template").read_text(encoding="utf-8")


def init_workspace(root: Path, force: bool = False) -> ScaffoldResult:
    """在 root 下生成 .env 与 configs/courses.yaml。

    已存在的文件不会被覆盖，除非 force 为 True。
    """
    root = Path(root)
    created: list[Path] = []
    skipped: list[Path] = []

    env_path = root / ".env"
    if env_path.exists() and not force:
        skipped.append(env_path)
    else:
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text(render_env_template(), encoding="utf-8")
        created.append(env_path)

    courses_path = root / "configs" / "courses.yaml"
    if courses_path.exists() and not force:
        skipped.append(courses_path)
    else:
        courses_path.parent.mkdir(parents=True, exist_ok=True)
        courses_path.write_text(render_courses_template(), encoding="utf-8")
        created.append(courses_path)

    return ScaffoldResult(created=created, skipped=skipped)


def skill_source_dir() -> Path:
    """Skill 的唯一来源：包内的 labreg/skill/。"""
    return Path(__file__).resolve().parent / "skill"


def copy_skill(target_dir: Path) -> Path:
    """把 Skill 目录复制到 target_dir，返回安装后的路径。"""
    source = skill_source_dir()
    if not source.exists():
        raise FileNotFoundError(f"未找到 Skill 源目录：{source}")
    target = Path(target_dir) / "labreg"
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    return target


def sync_skill(target_dir: Path) -> list[Path]:
    """把包内 Skill 同步到若干目标目录，返回实际发生变化的路径。

    用于让仓库内的 .trae/skills 与包内源保持一致，避免两份文档漂移。
    """
    source = skill_source_dir()
    changed: list[Path] = []
    for target_dir in (Path(t) for t in target_dir):
        target = target_dir / "labreg"
        if not target.exists():
            copy_skill(target_dir)
            changed.append(target / "SKILL.md")
            continue
        src_text = (source / "SKILL.md").read_text(encoding="utf-8")
        dst_file = target / "SKILL.md"
        if dst_file.exists() and dst_file.read_text(encoding="utf-8") == src_text:
            continue
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        dst_file.write_text(src_text, encoding="utf-8")
        changed.append(dst_file)
    return changed
