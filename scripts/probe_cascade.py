"""探测脚本：确认机房级联、节次→时间映射、引用按钮名、已有排课。

用法：
    $env:LABREG_COURSE='00000000'
    $env:LABREG_CLASS='示例课程-0001A'
    $env:LABREG_RWID='72732'
    $env:LABREG_XMID='37514'
    python scripts/probe_cascade.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _common import make_client, require_env, task_query  # noqa: E402
from labreg import pages  # noqa: E402


def main() -> int:
    client = make_client()
    course = require_env("LABREG_COURSE")
    class_name = require_env("LABREG_CLASS")
    rwid = require_env("LABREG_RWID")
    xmid = require_env("LABREG_XMID")

    query = task_query(client, course, class_name, rwid, xmid)
    url = f"{pages.PAGE_BATCH_SCHEDULE}?{query}"

    tree = client.tree(url)
    print("=== 排课页初始状态 ===")
    print("  机房选项   :", pages.parse_room_options(tree))
    print("  隐藏字段   :", {k: pages.hidden(tree, k)
                             for k in ("hidtype", "hiduid", "hidkcdm", "hidIsUnderTime")})
    print("  实验项目   :", pages.parse_experiment_options(tree))
    print("  学生批次   :", pages.parse_batch_options(tree))
    print("  星期复选组 :", pages.parse_weekday_options(tree))
    print("  已有排课行 :", len(pages.parse_schedule_rows(tree)))

    print()
    print("=== 节次 → 时间映射 ===")
    for j1, j2 in ((3, 4), (6, 7), (1, 2)):
        resp = client.post(url, data={"__EVENTTARGET": "ddljie2",
                                      "ddljie1": str(j1), "ddljie2": str(j2),
                                      "ddlxm": xmid})
        tree = pages.parse(resp.text)
        values = {f: pages.hidden(tree, f)
                  for f in ("tbshi", "tbfen", "tbshi2", "tbfen2")}
        print(f"  {j1}-{j2}节 -> " + " ".join(f"{k}={v}" for k, v in values.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
