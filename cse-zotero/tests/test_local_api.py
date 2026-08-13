import json

from zotero_companion.local_api import ZoteroLocalAPI


class FakeResponse:
    status = 200

    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.value).encode()


def test_paged_gets_until_short_page():
    calls = []

    def opener(request, timeout):
        calls.append((request.full_url, request.method, timeout))
        start = int(request.full_url.split("start=")[1])
        return FakeResponse([{"key": str(index)} for index in range(start, start + (2 if start == 0 else 1))])

    api = ZoteroLocalAPI(opener=opener)
    assert list(api.paged("/api/users/0/items", limit=2)) == [
        {"key": "0"},
        {"key": "1"},
        {"key": "2"},
    ]
    assert all(method == "GET" for _, method, _ in calls)


def test_get_text_reads_plain_text_with_the_read_only_api_header():
    calls = []

    class TextResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b"file:///tmp/companion.md"

    def opener(request, timeout):
        calls.append((request.full_url, request.method, request.headers, timeout))
        return TextResponse()

    api = ZoteroLocalAPI(opener=opener)

    assert api.get_text("/api/users/0/items/ATT123/file/view/url") == "file:///tmp/companion.md"
    assert calls[0][1] == "GET"
    assert calls[0][2]["Zotero-api-version"] == "3"
