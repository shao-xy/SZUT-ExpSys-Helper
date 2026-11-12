"""客户端层的回归测试。

重点验证「非页面响应不得清空会话隐藏域」——
冲突检查接口返回的是纯文本，若在此清掉 __VIEWSTATE，
后续表单提交就会被站点静默拒绝。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from labreg.client import SiteClient  # noqa: E402


class FakeResponse:
    """最小可用的响应替身。"""

    def __init__(self, text: str, url: str = "http://example/page") -> None:
        self.text = text
        self.url = url
        self.apparent_encoding = "utf-8"
        self.status_code = 200
        self.headers: dict[str, str] = {}


PAGE_HTML = """
<html><body><form>
<input type="hidden" name="__VIEWSTATE" value="VS1" />
<input type="hidden" name="__VIEWSTATEGENERATOR" value="VG1" />
<input type="hidden" name="__EVENTVALIDATION" value="EV1" />
</form></body></html>
"""

PAGE_HTML_NO_EVENTVALIDATION = """
<html><body><form>
<input type="hidden" name="__VIEWSTATE" value="VS1" />
<input type="hidden" name="__VIEWSTATEGENERATOR" value="VG1" />
</form></body></html>
"""


def make_client() -> SiteClient:
    client = SiteClient("http://example.com")
    client.hidden_fields = {
        "__VIEWSTATE": "VS1",
        "__VIEWSTATEGENERATOR": "VG1",
        "__EVENTVALIDATION": "EV1",
    }
    return client


def test_plain_text_response_keeps_hidden_fields() -> None:
    client = make_client()
    client._absorb(FakeResponse("您排的这门课在第15周有冲突。"))
    assert client.hidden_fields["__VIEWSTATE"] == "VS1"
    assert client.hidden_fields["__EVENTVALIDATION"] == "EV1"


def test_empty_response_keeps_hidden_fields() -> None:
    client = make_client()
    client._absorb(FakeResponse(""))
    assert client.hidden_fields["__VIEWSTATE"] == "VS1"


def test_page_response_updates_hidden_fields() -> None:
    client = make_client()
    client._absorb(FakeResponse(PAGE_HTML))
    assert client.hidden_fields["__VIEWSTATE"] == "VS1"
    assert client.hidden_fields["__EVENTVALIDATION"] == "EV1"


def test_page_without_eventvalidation_drops_stale_value() -> None:
    client = make_client()
    client._absorb(FakeResponse(PAGE_HTML_NO_EVENTVALIDATION))
    assert client.hidden_fields["__VIEWSTATE"] == "VS1"
    assert "__EVENTVALIDATION" not in client.hidden_fields


def test_page_without_any_hidden_field_clears_cache() -> None:
    client = make_client()
    client._absorb(FakeResponse("<html><body><form></form></body></html>"))
    assert client.hidden_fields == {}
