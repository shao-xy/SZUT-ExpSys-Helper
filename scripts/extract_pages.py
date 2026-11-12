"""从 HAR 中抽取关键页面的 HTML 响应，保存为离线样本到 var/pages/。

用途：无需联网即可逆向表单字段与下拉选项。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import unquote

OUT = Path(__file__).resolve().parent.parent / "var" / "pages"

TARGETS = [
    ("plkb2", "plkb2.aspx"),
    ("fzKeBiao", "fzKeBiao.aspx"),
    ("jskclist", "jskclist.aspx"),
    ("jsfzlist", "jsfzlist.aspx"),
    ("xsteam", "xsteam.aspx"),
    ("kbjxlist2", "kbjxlist2.aspx"),
    ("kbjxlist", "kbjxlist.aspx"),
    ("JsKeBiaoView", "JsKeBiaoView.aspx"),
]


def main() -> int:
    har_path = Path(sys.argv[1])
    har = json.loads(har_path.read_text(encoding="utf-8-sig"))
    OUT.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for i, e in enumerate(har["log"]["entries"]):
        url = e["request"]["url"]
        for tag, needle in TARGETS:
            if needle not in url:
                continue
            content = e["response"].get("content") or {}
            text = content.get("text") or ""
            if not text:
                continue
            if content.get("encoding") == "base64":
                import base64
                try:
                    text = base64.b64decode(text).decode("utf-8", "ignore")
                except Exception:
                    continue
            name = f"{tag}_{counts.get(tag, 0)}.html"
            counts[tag] = counts.get(tag, 0) + 1
            (OUT / name).write_text(text, encoding="utf-8")
            # 同时保存该次请求的上下文
            (OUT / f"{tag}_{counts[tag]-1}.meta.json").write_text(
                json.dumps(
                    {
                        "url": unquote(url),
                        "method": e["request"]["method"],
                        "status": e["response"]["status"],
                        "postData": (e["request"].get("postData") or {}).get("text", "")[:4000],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
    for k, v in counts.items():
        print(f"{k}: {v} 个页面")
    print(f"输出目录：{OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
