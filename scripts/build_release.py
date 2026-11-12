"""构建公开发布包。

产出 dist/labreg-release/ —— 一份可直接 git init 并推送到 GitHub 的干净副本。

与工作仓库的差别：
  · 不含 .env、var/、HAR 等本地数据
  · 不含 configs/courses.yaml（本人排课计划），只留示例
  · 不含 Git 历史（避免历史中的凭据随之外泄）
  · .env.example 与模板中不含真实站点地址
  · 探测脚本的凭据与班级参数改为环境变量传入

用法：
    python scripts/build_release.py
    python scripts/build_release.py --out dist/other-name
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 整个目录不复制
EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "env", "var", "dist", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".idea", ".vscode",
    ".claude", ".agents", ".screenshots", "labreg.egg-info",
}
# 单个文件不复制
EXCLUDE_FILES = {
    ".env", ".env.local", "courses.yaml",
}
EXCLUDE_SUFFIXES = {".har", ".pyc", ".pyo"}


def copy_tree(src: Path, dst: Path) -> None:
    """按排除规则复制目录。"""
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.is_dir():
            if item.name in EXCLUDE_DIRS:
                continue
            copy_tree(item, dst / item.name)
        elif item.name in EXCLUDE_FILES or item.suffix in EXCLUDE_SUFFIXES:
            continue
        else:
            shutil.copy2(item, dst / item.name)


def write_release_env_example(dst: Path) -> None:
    """确保发布包中的 .env.example 带有站点地址。

    站点号是同事上手的必要信息，且该地址仅在校园网内可达，故保留。
    """
    path = dst / ".env.example"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if "BASE_URL=" in text and "BASE_URL=\n" in text + "\n":
        text = text.replace("BASE_URL=\n", "BASE_URL=http://10.28.203.178/\n")
        path.write_text(text, encoding="utf-8")


def write_release_gitignore(dst: Path) -> None:
    """发布包的忽略规则：排除本地凭据与个人排课计划。"""
    (dst / ".gitignore").write_text(
        "# 本地凭据\n"
        ".env\n"
        ".env.local\n"
        "*.har\n"
        "var/\n"
        "\n"
        "# 个人排课计划（含课程代码、班级、周次、教室）\n"
        "configs/courses.yaml\n"
        "\n"
        "# Python\n"
        "__pycache__/\n"
        "*.py[cod]\n"
        "*.egg-info/\n"
        ".venv/\n"
        "venv/\n"
        "env/\n"
        ".pytest_cache/\n"
        "\n"
        "# 编辑器 / 系统\n"
        ".vscode/\n"
        ".idea/\n"
        ".DS_Store\n"
        "Thumbs.db\n"
        "\n"
        "# Agent Skill 安装目录\n"
        ".claude/skills/\n"
        ".agents/skills/\n",
        encoding="utf-8",
    )


def write_release_readme_note(dst: Path) -> None:
    """在 README 开头插入使用前必读的小节。"""
    path = dst / "README.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    note = (
        "> **使用前请先读本节。**\n"
        ">\n"
        "> 1. **实验系统地址：<http://10.28.203.178/index2.aspx>**\n"
        ">    站点在校园网内，不在校内请先连学校 VPN。\n"
        ">    浏览器打不开时，先连 VPN，再运行 `labreg preflight` 测连通性。\n"
        "> 2. 本工具只覆盖排课环节。**课程大纲与实验任务书必须由教师本人在系统中手工提交**，\n"
        ">    工具不会代做，也无法代做。任务书未提交时，工具会终止并提示。\n"
        "> 3. 首次使用按「五分钟上手」执行：`labreg init` → 填 `.env` 与 `configs/courses.yaml`\n"
        ">    → `labreg selftest` → `labreg preflight` → `labreg run --dry-run` → `labreg run`。\n"
        "> 4. 排课计划 `configs/courses.yaml` 含个人教学信息，默认不入库。\n"
        ">\n"
        "---\n\n"
    )
    if "使用前请先读本节" not in text:
        path.write_text(note + text, encoding="utf-8")


def remove_internal_docs(dst: Path) -> None:
    """移除只面向维护者本人的文档。"""
    for name in ("分发指南.md", "发布说明-v0.1.0.md", "发布说明-v0.2.0.md"):
        path = dst / "docs" / name
        if path.exists():
            path.unlink()


def verify_clean(dst: Path) -> list[str]:
    """检查发布包中是否残留敏感内容，返回问题列表。

    只检查会被他人阅读的文件：源码、文档、配置。
    tests/ 下的数据是构造的测试样本，不含真实信息；本脚本自身包含检测标记，同样跳过。
    """
    problems: list[str] = []
    # 站点号（10.28.203.178）有意保留：仅校园网内可达，且同事上手必需。
    markers = ("szutQAZsxy01", "202500033", "高级数据库技术",
               "09300389", "邵新洋", "02-087")
    skip_names = {"build_release.py"}
    for path in dst.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix in {".png", ".jpg", ".har", ".pyc"}:
            continue
        rel = path.relative_to(dst)
        if path.name in skip_names or rel.parts[0] == "tests":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for marker in markers:
            if marker in text:
                problems.append(f"{rel} 含敏感片段：{marker}")
    if (dst / ".env").exists():
        problems.append("发布包中存在 .env")
    if (dst / "configs" / "courses.yaml").exists():
        problems.append("发布包中存在 configs/courses.yaml")
    if (dst / ".git").exists():
        problems.append("发布包中存在 .git（会带出历史）")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="构建公开发布包")
    ap.add_argument("--out", default="dist/labreg-release", help="输出目录")
    ap.add_argument("--keep", action="store_true", help="保留已存在的输出目录")
    args = ap.parse_args()

    out = (ROOT / args.out).resolve()
    if out.exists():
        if not args.keep:
            shutil.rmtree(out)
        else:
            for item in out.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
    if out == ROOT:
        print("输出目录不能是仓库根目录", flush=True)
        return 1

    copy_tree(ROOT, out)
    write_release_env_example(out)
    write_release_gitignore(out)
    write_release_readme_note(out)
    remove_internal_docs(out)

    problems = verify_clean(out)
    if problems:
        print("发布包检查未通过：")
        for p in problems:
            print("  -", p)
        return 1

    print(f"发布包已生成：{out}")
    print(f"文件数：{sum(1 for _ in out.rglob('*') if _.is_file())}")
    print()
    print("下一步：")
    print(f"  cd {args.out}")
    print("  git init && git add -A && git commit -m '初始发布'")
    print("  git remote add origin <仓库地址> && git push -u origin main")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
