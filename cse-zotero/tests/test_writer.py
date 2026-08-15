import json
import os
from urllib.parse import urlsplit

import pytest

from zotero_companion.writer import (
    KeyFileError,
    WriterHTTPError,
    ZoteroLocalAPIWriter,
    build_search_plan,
    build_tag_plan,
    load_local_api_key,
)

SECRET = "A" * 32
SERVER_ID = "server-id-1"


class FakeResponse:
    def __init__(self, status=200, value=None, headers=None, body=None):
        self.status = status
        self.headers = headers or {}
        self._body = body if body is not None else json.dumps(value).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._body


def write_key(tmp_path):
    path = tmp_path / "local-api-key"
    path.write_text(SECRET, encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o600)
    return path


def request_header(request, name):
    wanted = name.lower()
    return next(
        (value for key, value in request.header_items() if key.lower() == wanted),
        None,
    )


def test_key_loading_rejects_missing_and_insecure_files(tmp_path):
    missing = tmp_path / "missing"
    with pytest.raises(KeyFileError) as missing_error:
        load_local_api_key(missing)
    assert SECRET not in str(missing_error.value)

    insecure = tmp_path / "insecure"
    insecure.write_text(SECRET, encoding="utf-8")
    if os.name != "nt":
        insecure.chmod(0o644)
        with pytest.raises(KeyFileError):
            load_local_api_key(insecure)


def test_writer_discovers_and_caches_server_id_and_sends_auth_headers(tmp_path):
    calls = []

    def opener(request, timeout):
        calls.append(request)
        if request.method == "GET":
            return FakeResponse(headers={"Zotero-Server-ID": SERVER_ID}, body=b"")
        return FakeResponse(204, headers={"Zotero-Server-ID": SERVER_ID}, body=b"")

    writer = ZoteroLocalAPIWriter(key_path=write_key(tmp_path), opener=opener)
    writer.patch_item_tags("ABCD2345", [{"tag": "priority:key", "type": 0}], version=8)
    writer.patch_item_tags("EFGH5678", [{"tag": "role:review", "type": 0}], version=9)

    assert sum(request.method == "GET" for request in calls) == 1
    patch = next(request for request in calls if request.method == "PATCH")
    assert request_header(patch, "Zotero-API-Version") == "3"
    assert request_header(patch, "Zotero-API-Key") == SECRET
    assert request_header(patch, "Zotero-Server-ID") == SERVER_ID
    assert request_header(patch, "Content-Type") == "application/json"
    assert "key=" not in patch.full_url
    assert json.loads(patch.data) == {
        "tags": [{"tag": "priority:key", "type": 0}],
        "version": 8,
    }


def test_writer_patches_collections_with_item_version_precondition(tmp_path):
    calls = []

    def opener(request, timeout):
        calls.append(request)
        if request.method == "GET":
            return FakeResponse(headers={"Zotero-Server-ID": SERVER_ID}, body=b"")
        return FakeResponse(204, headers={"Zotero-Server-ID": SERVER_ID}, body=b"")

    writer = ZoteroLocalAPIWriter(key_path=write_key(tmp_path), opener=opener)
    writer.patch_item_collections("ITEM1", ["FAGAJ6GB"], version=21)

    patch = next(request for request in calls if request.method == "PATCH")
    assert request_header(patch, "Zotero-API-Key") == SECRET
    assert request_header(patch, "Zotero-Server-ID") == SERVER_ID
    assert json.loads(patch.data) == {
        "collections": ["FAGAJ6GB"],
        "version": 21,
    }


def test_tag_plan_is_pure_and_maps_only_manual_assignments():
    items = [
        {
            "key": "ITEM1",
            "version": 12,
            "data": {
                "key": "ITEM1",
                "tags": [
                    {"tag": "Review", "type": 0},
                    {"tag": "existing", "type": 0},
                    {"tag": "Machine Learning", "type": 1},
                ],
            },
        }
    ]

    plan = build_tag_plan(items)

    assert plan == [
        {
            "key": "ITEM1",
            "version": 12,
            "blocked_reason": None,
            "removed": ["Review"],
            "added": ["role:review"],
            "tags": [
                {"tag": "existing", "type": 0},
                {"tag": "Machine Learning", "type": 1},
                {"tag": "role:review", "type": 0},
            ],
        }
    ]
    assert items[0]["data"]["tags"][0]["tag"] == "Review"


def test_dry_run_does_not_require_key_or_send_mutations(tmp_path):
    calls = []

    def opener(request, timeout):
        calls.append(request)
        assert request.method == "GET"
        assert urlsplit(request.full_url).path == "/api/users/0/items"
        return FakeResponse(
            headers={"Last-Modified-Version": "12"},
            value=[
                {
                    "key": "ITEM1",
                    "version": 12,
                    "data": {
                        "key": "ITEM1",
                        "tags": [{"tag": "Review", "type": 0}],
                    },
                }
            ]
        )

    writer = ZoteroLocalAPIWriter(key_path=tmp_path / "does-not-exist", opener=opener)
    result = writer.tag_cleanup()

    assert result["mode"] == "dry-run"
    assert result["items_changed"] == 1
    assert len(calls) == 1


def test_apply_uses_item_version_and_redacts_error_body(tmp_path):
    calls = []
    key_path = write_key(tmp_path)

    def opener(request, timeout):
        calls.append(request)
        path = urlsplit(request.full_url).path
        if request.method == "GET" and path == "/api/users/0/items":
            return FakeResponse(
                headers={"Last-Modified-Version": "12"},
                value=[
                    {
                        "key": "ITEM1",
                        "version": 12,
                        "data": {
                            "key": "ITEM1",
                            "tags": [{"tag": "Review", "type": 0}],
                        },
                    }
                ]
            )
        if request.method == "GET" and path == "/api/":
            return FakeResponse(headers={"Zotero-Server-ID": SERVER_ID}, body=b"")
        if request.method == "PATCH":
            assert request_header(request, "Zotero-Server-ID") == SERVER_ID
            return FakeResponse(204, headers={"Zotero-Server-ID": SERVER_ID}, body=b"")
        raise AssertionError(f"unexpected request {request.method} {path}")

    writer = ZoteroLocalAPIWriter(key_path=key_path, opener=opener)
    result = writer.tag_cleanup(apply=True)

    assert result["mode"] == "apply"
    patch = next(request for request in calls if request.method == "PATCH")
    assert json.loads(patch.data)["version"] == 12

    def failed_opener(request, timeout):
        if request.method == "GET":
            return FakeResponse(headers={"Zotero-Server-ID": SERVER_ID}, body=b"")
        return FakeResponse(
            401,
            headers={"Zotero-Server-ID": SERVER_ID},
            body=f"invalid token {SECRET}".encode(),
        )

    failing = ZoteroLocalAPIWriter(key_path=key_path, opener=failed_opener)
    with pytest.raises(WriterHTTPError) as error:
        failing.patch_item_tags("ITEM1", [], version=12)
    assert SECRET not in str(error.value)
    assert "[redacted]" in str(error.value)


def test_search_plan_lists_only_missing_workflow_searches():
    plan = build_search_plan([{"data": {"name": "Workflow — To Read"}}])

    assert [entry["name"] for entry in plan] == [
        "Workflow — Reading",
        "Workflow — Reviewed",
        "Priority — Key",
    ]
    assert plan[0]["conditions"][0] == {
        "condition": "tag",
        "operator": "is",
        "value": "status:reading",
    }


def test_search_apply_uses_library_version_precondition(tmp_path):
    calls = []

    def opener(request, timeout):
        calls.append(request)
        path = urlsplit(request.full_url).path
        if request.method == "GET" and path == "/api/users/0/searches":
            return FakeResponse(
                headers={"Last-Modified-Version": "8"},
                value=[],
            )
        if request.method == "GET" and path == "/api/":
            return FakeResponse(headers={"Zotero-Server-ID": SERVER_ID}, body=b"")
        if request.method == "POST" and path == "/api/users/0/searches":
            assert request_header(request, "If-Unmodified-Since-Version") == "8"
            payload = json.loads(request.data)
            assert len(payload) == 4
            assert payload[0]["conditions"][1] == {
                "condition": "noChildren",
                "operator": "true",
                "value": "",
            }
            return FakeResponse(
                value={"success": True},
                headers={"Zotero-Server-ID": SERVER_ID},
            )
        raise AssertionError(f"unexpected request {request.method} {path}")

    writer = ZoteroLocalAPIWriter(key_path=write_key(tmp_path), opener=opener)
    result = writer.saved_searches(apply=True)

    assert result["mode"] == "apply"
    assert result["precondition"] == {"library_version": 8}


def test_linked_companion_is_dry_run_first_and_returns_child_key(tmp_path):
    calls = []
    companion = tmp_path / "paper.mmd"
    companion.write_text("# extracted\n", encoding="utf-8")

    def opener(request, timeout):
        calls.append(request)
        path = urlsplit(request.full_url).path
        if request.method == "GET" and path.endswith("/items/PARENT1"):
            return FakeResponse(
                value={"key": "PARENT1", "data": {"itemType": "journalArticle"}},
                headers={"Last-Modified-Version": "22"},
            )
        if request.method == "GET" and path == "/api/":
            return FakeResponse(headers={"Zotero-Server-ID": SERVER_ID}, body=b"")
        if request.method == "POST" and path == "/api/users/0/items":
            assert request_header(request, "If-Unmodified-Since-Version") == "22"
            attachment = json.loads(request.data)[0]
            assert attachment["parentItem"] == "PARENT1"
            assert attachment["path"] == str(companion.resolve())
            return FakeResponse(
                value={"successful": {"0": {"key": "CHILD123"}}},
                headers={"Zotero-Server-ID": SERVER_ID},
            )
        raise AssertionError(f"unexpected request {request.method} {path}")

    writer = ZoteroLocalAPIWriter(key_path=write_key(tmp_path), opener=opener)
    plan = writer.linked_attachment("PARENT1", companion)
    assert plan["mode"] == "dry-run"
    assert len(calls) == 1

    applied = writer.linked_attachment("PARENT1", companion, apply=True)
    assert applied["attachment_key"] == "CHILD123"
