"""分析已抓取页面的表单控件：select / input / checkbox 列表及其选项。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from lxml import html as lhtml

PAGE = Path(sys.argv[1])
tree = lhtml.fromstring(PAGE.read_bytes().decode("utf-8", "ignore"))

print("=" * 80)
print("SELECT 下拉框")
print("=" * 80)
for sel in tree.xpath("//select"):
    sid = sel.get("id") or sel.get("name")
    opts = []
    for o in sel.xpath("./option"):
        opts.append((o.get("value"), (o.text_content() or "").strip()))
    print(f"\n#{sid}  (name={sel.get('name')}, count={len(opts)})")
    for v, t in opts[:60]:
        print(f"    value={v!r} text={t!r}")
    if len(opts) > 60:
        print(f"    ... 其余 {len(opts) - 60} 项")

print()
print("=" * 80)
print("INPUT / BUTTON")
print("=" * 80)
for el in tree.xpath("//input|//button"):
    typ = el.get("type", "")
    name = el.get("name")
    iid = el.get("id")
    val = el.get("value")
    if typ == "hidden" and not name:
        continue
    print(f"  type={typ!r:12} id={iid!r:28} name={name!r:32} value={val!r}")

print()
print("=" * 80)
print("CHECKBOX LIST (name$数字)")
print("=" * 80)
groups: dict[str, list] = {}
for el in tree.xpath("//input[@type='checkbox']"):
    name = el.get("name") or ""
    m = re.match(r"^(.*)\$(\d+)$", name)
    if m:
        groups.setdefault(m.group(1), []).append((int(m.group(2)), el.get("value"),
                                                 el.get("id"), el.get("checked")))
    else:
        print(f"  单个: name={name!r} value={el.get('value')!r} id={el.get('id')!r}")
for key, items in groups.items():
    items.sort()
    print(f"\n  组 {key!r} 共 {len(items)} 项")
    for idx, val, iid, chk in items[:60]:
        print(f"    [{idx}] value={val!r} id={iid!r} checked={chk}")

print()
print("=" * 80)
print("TABLE 概要")
print("=" * 80)
for t in tree.xpath("//table"):
    tid = t.get("id")
    rows = t.xpath("./tr")
    print(f"  table id={tid!r} rows={len(rows)}")
    for r in rows[:3]:
        cells = [c.text_content().strip()[:24] for c in r.xpath("./td|./th")]
        print(f"      {cells}")
