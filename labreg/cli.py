"""命令行入口。

子命令：
    init          生成可编辑的工作区文件（.env、configs/courses.yaml）
    check         检查本地配置是否就绪
    plan          展示课程排课计划
    preflight     检查网络、登录、任务书与计划匹配情况
    courses       列出站点上可排课的班级
    status        查看班级当前状态
    run           执行排课
    clear         清除已有排课
    install-skill 安装 Agent Skill
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import pages, preflight as preflight_mod, workflow
from .client import SiteClient
from .config import CONFIG_DIR, load_course_plans, load_settings
from .output import Printer
from .scaffold import init_workspace
from .workflow import Scheduler


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )


def _login(args) -> tuple[SiteClient, Scheduler] | None:
    try:
        settings = load_settings()
    except Exception as exc:  # noqa: BLE001
        print(f"配置检查失败：{exc}", file=sys.stderr)
        return None

    client = SiteClient(
        settings.base_url,
        settings.username,
        settings.password,
        timeout=settings.timeout,
        verify_ssl=settings.verify_ssl,
    )
    result = client.login()
    if not result.ok:
        print(f"登录失败：{result.message}", file=sys.stderr)
        return None
    logging.info("登录成功")
    return client, Scheduler(client)


def cmd_selftest(args) -> int:
    """本地自检：不访问站点，验证安装与配置。"""
    from .selftest import run_selftest
    out = Printer(args.json)
    items = run_selftest()
    for item in items:
        mark = "通过" if item.ok else "未就绪"
        out.line(f"[{mark}] {item.name}：{item.detail}")
        if not item.ok and item.hint:
            out.line(f"        → {item.hint}")
        out.record(name=item.name, ok=item.ok, detail=item.detail, hint=item.hint)
    failed = [i for i in items if not i.ok]
    out.line()
    if failed:
        out.line(f"有 {len(failed)} 项未就绪，请按上方提示处理。")
    else:
        out.line("本地环境自检通过，可运行 `labreg preflight` 做站点检查。")
    out.emit({"passed": not failed})
    return 0 if not failed else 1


def cmd_init(args) -> int:
    """生成工作区文件，供新教师定制。"""
    result = init_workspace(Path(args.directory), force=args.force)
    for path in result.created:
        print(f"已生成：{path}")
    for path in result.skipped:
        print(f"已存在，跳过：{path}")
    print()
    print("接下来：")
    print("  1) 编辑 .env，填写站点地址与账号密码")
    print("  2) 编辑 configs/courses.yaml，填写课程、班级与各实验周次")
    print("  3) 运行 `labreg preflight` 检查是否具备排课条件")
    return 0


def cmd_check(args) -> int:
    try:
        s = load_settings()
    except Exception as exc:  # noqa: BLE001
        print(f"配置检查失败：{exc}", file=sys.stderr)
        return 1
    print(f"BASE_URL  : {s.base_url}")
    print(f"USERNAME  : {s.username or '(未填写)'}")
    print(f"PASSWORD  : {'已填写' if s.password else '(未填写)'}")
    print(f"TIMEOUT   : {s.timeout}s")
    return 0


def cmd_preflight(args) -> int:
    """执行前置检查。"""
    out = Printer(args.json)
    try:
        settings = load_settings()
    except Exception as exc:  # noqa: BLE001
        out.error(f"配置检查失败：{exc}")
        return 1

    plans = None
    target = Path(args.config) if args.config else CONFIG_DIR / "courses.yaml"
    if target.exists():
        try:
            plans = load_course_plans(target)
        except Exception as exc:  # noqa: BLE001
            out.error(f"排课计划解析失败：{exc}")
            return 1
    else:
        out.line(f"提示：未找到排课计划 {target}，将跳过计划匹配检查。")
        out.line()

    client = SiteClient(settings.base_url, settings.username, settings.password,
                        timeout=settings.timeout, verify_ssl=settings.verify_ssl)
    report = preflight_mod.run_preflight(client, plans, need_site=not args.offline)

    if args.json:
        out.emit({
            "passed": report.passed,
            "checks": [
                {"name": c.name, "ok": c.ok, "detail": c.detail,
                 "hint": c.hint, "blocking": c.blocking}
                for c in report.checks
            ],
        })
    else:
        out.line(report.render())
    return 0 if report.passed else 1


def cmd_plan(args) -> int:
    out = Printer(args.json)
    target = Path(args.config) if args.config else CONFIG_DIR / "courses.yaml"
    if not Path(target).exists():
        out.error(f"未找到课程配置文件：{target}")
        return 1
    plans = load_course_plans(target)
    if not plans:
        out.error(f"{target} 中没有 courses 配置")
        return 1

    for course in plans:
        out.line(f"课程：{course.name} [{course.course_code}]")
        for cls in course.classes:
            out.line(f"  班级：{cls.name}  {cls.weekday} "
                     f"{cls.start_period}-{cls.end_period}节  地点 {cls.room}")
            for exp in cls.experiments:
                out.line(f"    - {exp.project}：{exp.describe}")
                out.record(
                    course=course.name,
                    course_code=course.course_code,
                    class_name=cls.name,
                    project=exp.project,
                    weeks=[exp.slot.start_week, exp.slot.end_week],
                    weekday=exp.slot.weekday,
                    start_period=exp.slot.start_period,
                    end_period=exp.slot.end_period,
                    room=exp.slot.room,
                    parity=exp.slot.parity,
                )
    out.emit({"config": str(target), "courses": len(plans)})
    return 0


def cmd_courses(args) -> int:
    out = Printer(args.json)
    pair = _login(args)
    if pair is None:
        return 1
    client, scheduler = pair

    rows = scheduler.list_classes()
    if not rows:
        out.error(preflight_mod.TASK_BOOK_HINT)
        return 1

    out.line("可排课班级：")
    for row in rows:
        out.line(f"  {row.name}  [{row.course_code}]  {row.course_name}")
        out.record(name=row.name, course_code=row.course_code,
                   course_name=row.course_name)
    out.emit({"count": len(rows)})
    return 0


def cmd_status(args) -> int:
    out = Printer(args.json)
    pair = _login(args)
    if pair is None:
        return 1
    client, scheduler = pair

    for row in scheduler.list_classes():
        if args.class_name and row.name != args.class_name:
            continue
        out.line(f"班级 {row.name}  [{row.course_code}]")
        tasks = scheduler.list_task_rows(row.course_code, row.name)
        for task in tasks:
            task_params = task.params
            query = scheduler.build_query(row.course_code, row.name,
                                          task_params.get("rwid", ""),
                                          task_params.get("xmid", ""))
            confirm = pages.parse_confirm_state(
                client.tree(f"{pages.PAGE_CONFIRM}?{query}"))
            group_tree = client.tree(f"{pages.PAGE_GROUP_FORM}?{query}")
            pending = len(pages.parse_pending_students(group_tree))
            schedule_tree = client.tree(f"{pages.PAGE_BATCH_SCHEDULE}?{query}")
            scheduled = pages.parse_schedule_rows(schedule_tree)
            out.line(f"  - {task.project_name}")
            out.line(f"      确认学生 {confirm.confirmed}/{confirm.matched}"
                     f" | 待分批 {pending}"
                     f" | 已排课 {len(scheduled)} 条")
            for item in scheduled:
                out.line(f"        {item['time']} @ {item['place']}")
            out.record(
                class_name=row.name,
                course_code=row.course_code,
                project=task.project_name,
                xmid=task_params.get("xmid", ""),
                confirmed=confirm.confirmed,
                matched=confirm.matched,
                pending_group=pending,
                scheduled=len(scheduled),
                arrangements=[
                    {"time": i["time"], "place": i["place"]} for i in scheduled
                ],
            )
    out.emit()
    return 0


def cmd_clear(args) -> int:
    """清除指定班级的已有排课记录。"""
    out = Printer(args.json)
    pair = _login(args)
    if pair is None:
        return 1
    client, scheduler = pair

    for row in scheduler.list_classes():
        if args.class_name and row.name != args.class_name:
            continue
        out.line(f"班级 {row.name}")
        for task in scheduler.list_task_rows(row.course_code, row.name):
            task_params = task.params
            rwid = task_params.get("rwid", "")
            xmid = task_params.get("xmid", "")
            query = scheduler.build_query(row.course_code, row.name, rwid, xmid)

            while True:
                tree = client.tree(f"{pages.PAGE_BATCH_SCHEDULE}?{query}")
                existing = pages.parse_schedule_rows(tree)
                if not existing:
                    break
                item = existing[0]
                out.line(f"  - {task.project_name}：{item['time']} @ {item['place']}")
                if args.dry_run:
                    out.record(class_name=row.name, project=task.project_name,
                               time=item["time"], place=item["place"],
                               action="would-delete")
                    break
                result = scheduler.delete_schedule(row.course_code, row.name,
                                                  rwid, xmid, item["delete_id"])
                out.line(f"      → {result.message}")
                out.record(class_name=row.name, project=task.project_name,
                           time=item["time"], place=item["place"],
                           action="deleted", ok=result.ok, message=result.message)
                if not result.ok:
                    break
    out.emit()
    return 0


def cmd_run(args) -> int:
    out = Printer(args.json)
    pair = _login(args)
    if pair is None:
        return 1
    client, scheduler = pair

    target = Path(args.config) if args.config else CONFIG_DIR / "courses.yaml"
    if not Path(target).exists():
        out.error(f"未找到课程配置文件：{target}")
        out.error("可运行 `labreg init` 生成模板。")
        return 1
    plans = load_course_plans(target)

    # 前置检查：任务书未提交时直接终止并给出人工操作指引
    report = preflight_mod.run_preflight(client, plans, need_site=True)
    if not report.passed:
        out.error(report.render())
        out.emit({"passed": False, "phase": "preflight"})
        return 1
    if not args.json:
        out.line(report.render())
        out.line("-" * 60)

    site_rows = scheduler.list_classes()
    if not site_rows:
        out.error(preflight_mod.TASK_BOOK_HINT)
        out.emit({"passed": False, "phase": "preflight"})
        return 1

    failures = 0
    for course in plans:
        for cls in course.classes:
            site_row = next((r for r in site_rows if r.name == cls.name), None)
            if site_row is None:
                out.error(f"[跳过] 站点未找到班级 {cls.name}")
                out.record(class_name=cls.name, step="locate", ok=False,
                           message="站点未找到该班级")
                failures += 1
                continue

            tasks = scheduler.list_task_rows(site_row.course_code, cls.name)
            for exp in cls.experiments:
                task = next((t for t in tasks if exp.project in t.project_name), None)
                if task is None:
                    out.error(f"[跳过] {cls.name} 未找到实验项目 {exp.project}")
                    out.record(class_name=cls.name, project=exp.project,
                               step="locate", ok=False,
                               message="站点未找到该实验项目")
                    failures += 1
                    continue

                task_params = task.params
                rwid = task_params.get("rwid", "")
                xmid = task_params.get("xmid", "")
                label = f"{cls.name} / {exp.project}"

                if not args.skip_confirm:
                    result = scheduler.confirm_students(site_row.course_code, cls.name, rwid, xmid)
                    out.line(f"[确认] {label}: {result.message}")
                    out.record(class_name=cls.name, project=exp.project,
                               step="confirm", ok=result.ok, message=result.message)
                    if not result.ok:
                        failures += 1
                        continue

                if not args.skip_group:
                    result = scheduler.group_students(site_row.course_code, cls.name,
                                                     rwid, xmid, cls.batches)
                    out.line(f"[分批] {label}: {result.message}")
                    out.record(class_name=cls.name, project=exp.project,
                               step="group", ok=result.ok, message=result.message)
                    if not result.ok:
                        failures += 1
                        continue

                if args.dry_run:
                    out.line(f"[预演] {label}: 将排入 {exp.describe}")
                    out.record(class_name=cls.name, project=exp.project,
                               step="schedule", ok=True, dry_run=True,
                               message=f"将排入 {exp.describe}")
                    continue

                slot = cls.slot_for(exp)
                result = scheduler.schedule(site_row.course_code, cls.name,
                                            rwid, xmid,
                                            workflow.Slot(
                                                start_week=slot.start_week,
                                                end_week=slot.end_week,
                                                weekday=slot.weekday,
                                                start_period=slot.start_period,
                                                end_period=slot.end_period,
                                                room=slot.room,
                                                parity=slot.parity,
                                            ),
                                            force=args.force)
                out.line(f"[排课] {label}: {result.message}")
                out.record(class_name=cls.name, project=exp.project,
                           step="schedule", ok=result.ok, message=result.message,
                           plan=exp.describe)
                if not result.ok:
                    failures += 1

    out.line()
    if failures:
        out.error(f"完成，但有 {failures} 项失败。")
    else:
        out.line("全部完成。")
    out.emit({"passed": failures == 0, "failures": failures,
              "dry_run": bool(args.dry_run)})
    return 1 if failures else 0


def cmd_install_skill(args) -> int:
    """把 Agent Skill 安装到目标目录。"""
    from .scaffold import copy_skill
    try:
        target = copy_skill(Path(args.target))
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"已安装 Skill：{target}")
    print("在支持 Skill 的 Agent 中即可通过「实验系统排课」触发。")
    return 0


def cmd_sync_skill(args) -> int:
    """把包内 Skill 同步到仓库内的 .trae/skills，保持单一来源。"""
    from .scaffold import sync_skill
    targets = args.target or [".trae/skills"]
    changed = sync_skill(targets)
    if not changed:
        print("Skill 已是最新，无需同步。")
    for path in changed:
        print(f"已同步：{path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="labreg",
        description="实验教学管理系统课程排课工具（以课程为单位批量安排实验）",
    )
    ap.add_argument("-v", "--verbose", action="store_true", help="输出调试日志")
    sub = ap.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="生成可编辑的工作区文件")
    p_init.add_argument("-d", "--directory", default=".", help="工作目录，默认当前目录")
    p_init.add_argument("--force", action="store_true", help="覆盖已存在的文件")
    p_init.set_defaults(func=cmd_init)

    p_self = sub.add_parser("selftest", help="本地自检，不访问站点")
    p_self.add_argument("--json", action="store_true", help="以 JSON 输出")
    p_self.set_defaults(func=cmd_selftest)

    sub.add_parser("check", help="检查本地配置").set_defaults(func=cmd_check)

    p_plan = sub.add_parser("plan", help="展示排课计划")
    p_plan.add_argument("-c", "--config", help="课程配置文件路径")
    p_plan.add_argument("--json", action="store_true", help="以 JSON 输出")
    p_plan.set_defaults(func=cmd_plan)

    p_pre = sub.add_parser("preflight", help="检查网络、登录、任务书与计划匹配")
    p_pre.add_argument("-c", "--config", help="课程配置文件路径")
    p_pre.add_argument("--offline", action="store_true", help="只检查本地配置，不访问站点")
    p_pre.add_argument("--json", action="store_true", help="以 JSON 输出")
    p_pre.set_defaults(func=cmd_preflight)

    p_courses = sub.add_parser("courses", help="列出站点可排课班级")
    p_courses.add_argument("--json", action="store_true", help="以 JSON 输出")
    p_courses.set_defaults(func=cmd_courses)

    p_status = sub.add_parser("status", help="查看班级当前状态")
    p_status.add_argument("-k", "--class-name", help="只查看指定班级")
    p_status.add_argument("--json", action="store_true", help="以 JSON 输出")
    p_status.set_defaults(func=cmd_status)

    p_clear = sub.add_parser("clear", help="清除已有排课")
    p_clear.add_argument("-k", "--class-name", help="只处理指定班级")
    p_clear.add_argument("--dry-run", action="store_true", help="只列出，不执行删除")
    p_clear.add_argument("--json", action="store_true", help="以 JSON 输出")
    p_clear.set_defaults(func=cmd_clear)

    p_run = sub.add_parser("run", help="执行排课")
    p_run.add_argument("-c", "--config", help="课程配置文件路径")
    p_run.add_argument("--dry-run", action="store_true", help="只走确认与分批，不提交排课")
    p_run.add_argument("--skip-confirm", action="store_true", help="跳过确认学生")
    p_run.add_argument("--skip-group", action="store_true", help="跳过学生分批")
    p_run.add_argument("--force", action="store_true", help="存在冲突时仍然提交")
    p_run.add_argument("--json", action="store_true", help="以 JSON 输出")
    p_run.set_defaults(func=cmd_run)

    p_skill = sub.add_parser("install-skill", help="安装 Agent Skill")
    p_skill.add_argument("-d", "--target", default=".claude/skills",
                          help="Skill 安装目录，默认 .claude/skills")
    p_skill.set_defaults(func=cmd_install_skill)

    p_sync = sub.add_parser("sync-skill", help="同步仓库内的 Agent Skill")
    p_sync.add_argument("-d", "--target", action="append",
                         default=None, help="同步目标目录，可重复指定")
    p_sync.set_defaults(func=cmd_sync_skill)

    args = ap.parse_args(argv)
    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
