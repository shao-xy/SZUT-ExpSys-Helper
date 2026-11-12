"""输出层：统一人读文本与机读 JSON 两种呈现。

Agent 通过 ``--json`` 拿到结构化结果，避免解析自然语言输出。
"""

from __future__ import annotations

import json
import sys
from typing import Any


class Printer:
    """按需输出文本或 JSON。"""

    def __init__(self, as_json: bool = False) -> None:
        self.as_json = as_json
        self._buffer: list[dict[str, Any]] = []

    def line(self, text: str = "") -> None:
        """输出一行人类可读文本。JSON 模式下忽略。"""
        if not self.as_json:
            print(text)

    def detail(self, text: str) -> None:
        """输出缩进细节。"""
        if not self.as_json:
            print(f"    {text}")

    def error(self, text: str) -> None:
        print(text, file=sys.stderr)

    def record(self, **fields: Any) -> None:
        """收集一条结构化记录，供 JSON 输出使用。"""
        self._buffer.append(fields)

    def emit(self, payload: dict[str, Any] | None = None) -> None:
        """输出最终结果。JSON 模式下打印聚合后的 JSON。"""
        if not self.as_json:
            return
        body: dict[str, Any] = dict(payload or {})
        if self._buffer:
            body["items"] = self._buffer
        print(json.dumps(body, ensure_ascii=False, indent=2))
