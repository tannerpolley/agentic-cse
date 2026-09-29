"""Client for the optional background CSE Zotero plugin."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class PluginClientError(RuntimeError):
    """Raised when the background plugin cannot be contacted."""


@dataclass(frozen=True)
class ZoteroPluginClient:
    base_url: str = "http://127.0.0.1:23119"
    timeout: float = 5.0

    def _request(self, path: str, *, method: str, payload: dict | None = None) -> dict:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            raise PluginClientError(f"{exc}: {exc.read().decode('utf-8', 'replace')}") from exc
        except (URLError, TimeoutError) as exc:
            raise PluginClientError(str(exc)) from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PluginClientError("CSE Zotero plugin returned invalid JSON") from exc

    def status(self) -> dict:
        return self._request("/zotero-companion/status", method="GET")

    def tag_cleanup(self, *, apply: bool = False) -> dict:
        payload = {"mode": "apply", "confirm": "ZOTERO-COMPANION-APPLY-v1"} if apply else {}
        return self._request("/zotero-companion/tag-cleanup", method="POST", payload=payload)

    def saved_searches(self, *, apply: bool = False) -> dict:
        payload = {"mode": "apply", "confirm": "ZOTERO-COMPANION-SEARCHES-v1"} if apply else {}
        return self._request("/zotero-companion/saved-searches", method="POST", payload=payload)

    def project_organize(self, plan: dict, *, apply: bool = False) -> dict:
        # Only the plan itself; mode and confirmation come from --apply alone.
        payload = {"project": plan.get("project"), "operations": plan.get("operations")}
        if apply:
            payload.update(mode="apply", confirm="ZOTERO-COMPANION-ORGANIZE-v1")
        return self._request("/zotero-companion/project-organize", method="POST", payload=payload)
