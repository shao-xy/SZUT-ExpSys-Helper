"""深度导出 HAR 中关键接口的请求体与响应，便于逆向表单字段。

用法：python scripts/dump_key.py var/session.har <关键字> [...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import parse_qsl


def main() -> int:
    har_path = Path(sys.argv[1])
    keys = [k.lower() for k in sys.argv[2:]]
    har = json.loads(har_path.read_text(encoding="utf-8-sig"))
    entries = har["log"]["entries"]

    for i, e in enumerate(entries):
        req = e["request"]
        url = req["url"]
        if keys and not any(k in url.lower() for k in keys):
            continue
        print("=" * 100)
        print(f"[{i}] {req['method']} {url}")
        print(f"    status={e['response']['status']}")
        q = parse_qsl(url.split("?", 1)[1]) if "?" in url else []
        if q:
            print(f"    QUERY: {q}")
        headers = {h['name']: h['value'] for h in req.get('headers', [])}
        interesting = {k: v for k, v in headers.items() if k.lower() in
                       ('referer', 'content-type', 'origin', 'x-requested-with', 'cookie')}
        for k, v in interesting.items():
            v = (v[:200] + "...(len=%d)" % len(v)) if len(v) > 200 else v
            print(f"    HDR {k}: {v}")
        pd = req.get("postData") or {}
        txt = pd.get("text") or ""
        if txt:
            try:
                parsed = parse_qsl(txt)
                print(f"    FORM ({len(parsed)} fields):")
                for k, v in parsed:
                    if k.startswith("__"):
                        v = (v[:40] + f"...(len={len(v)})") if len(v) > 40 else v
                    print(f"      {k!r} = {v!r}")
            except Exception:
                print(f"    BODY: {txt[:3000]}")
        rt = (e["response"].get("content") or {}).get("text") or ""
        if rt:
            print(f"    RESPONSE({len(rt)} chars): {rt[:1500]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
