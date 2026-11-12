"""HAR 分析工具：提取接口清单、请求参数与响应结构。

用法：
    python scripts/inspect_har.py <har文件路径>
    python scripts/inspect_har.py <har文件路径> --keyword 安排
    python scripts/inspect_har.py <har文件路径> --detail 3
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any


def load_har(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as fh:
        return json.load(fh)


def iter_entries(har: dict[str, Any]):
    for entry in har.get("log", {}).get("entries", []):
        yield entry


def entry_summary(entry: dict[str, Any]) -> dict[str, Any]:
    req = entry.get("request", {})
    resp = entry.get("response", {})
    url = req.get("url", "")
    method = req.get("method", "")
    post = req.get("postData", {}) or {}
    body = post.get("text", "") or ""
    return {
        "method": method,
        "url": url,
        "path": re.sub(r"https?://[^/]+", "", url).split("?")[0],
        "query": (req.get("queryString") or []),
        "mime": post.get("mimeType", ""),
        "body": body,
        "status": resp.get("status", 0),
        "size": resp.get("content", {}).get("size", 0),
        "resp_text": resp.get("content", {}).get("text", "") or "",
        "resp_mime": resp.get("content", {}).get("mimeType", ""),
    }


def pretty_json(raw: str) -> str:
    if not raw:
        return ""
    try:
        return json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        return raw[:2000]


def main() -> int:
    ap = argparse.ArgumentParser(description="分析浏览器导出的 HAR 文件")
    ap.add_argument("har", help="HAR 文件路径")
    ap.add_argument("--keyword", help="按关键字过滤接口（匹配 URL 或请求体）")
    ap.add_argument("--detail", type=int, default=0, help="打印前 N 条接口的完整请求/响应")
    ap.add_argument("--only-xhr", action="store_true", help="仅显示 XHR/fetch 请求")
    args = ap.parse_args()

    har_path = Path(args.har)
    if not har_path.exists():
        print(f"文件不存在：{har_path}", file=sys.stderr)
        return 1

    har = load_har(har_path)
    entries = list(iter_entries(har))
    print(f"共 {len(entries)} 条记录，来自 {har_path.name}\n")

    grouped: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()

    for entry in entries:
        s = entry_summary(entry)
        if args.only_xhr and "xhr" not in s["mime"] and "json" not in s["mime"]:
            # mimeType 缺失时依靠 resourceType 兜底
            res_type = entry.get("_resourceType", "")
            if res_type not in ("xhr", "fetch"):
                continue
        blob = f"{s['url']} {s['body']}"
        if args.keyword and args.keyword.lower() not in blob.lower():
            continue
        grouped.setdefault(f"{s['method']} {s['path']}", []).append(s)

    print("=" * 78)
    print("接口清单")
    print("=" * 78)
    for key, items in grouped.items():
        s = items[0]
        print(f"{key}  ×{len(items)}  status={s['status']}")

    if args.detail:
        print()
        print("=" * 78)
        print(f"详细请求/响应（前 {args.detail} 条）")
        print("=" * 78)
        for s in [x for items in grouped.values() for x in items][: args.detail]:
            print(f"\n--- {s['method']} {s['url']}")
            if s["query"]:
                print("Query:", json.dumps(s["query"], ensure_ascii=False))
            if s["body"]:
                print("Request Body:")
                print(pretty_json(s["body"])[:4000])
            print(f"Response ({s['status']}, {s['resp_mime']}):")
            print(pretty_json(s["resp_text"])[:4000])

    print(f"\n合计 {sum(len(v) for v in grouped.values())} 个匹配接口")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
