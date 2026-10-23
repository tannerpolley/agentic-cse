"""One paper job for the modified Connector in the user's everyday Chrome."""
from __future__ import annotations

import subprocess
import shutil
import time
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from .acquire import AcquireStop, canonical_host, checked_url
from .plugin_client import PluginClientError, ZoteroPluginClient

SETUP = "Load ~/.local/share/cse/zotero/zotero-connector-agent in chrome://extensions and disable the official Connector; see README setup"


def connector_status():
    try:
        status = ZoteroPluginClient()._request("/zotero-companion/acquire-job", method="POST", payload={"action": "status"})
        return {k: status.get(k) for k in ("ready", "version", "supported_version", "module_revision",
                                          "expected_revision", "revision_mismatch", "heartbeat_at", "error")}
    except PluginClientError:
        return {"ready": False, "error": "CSE Zotero plugin job endpoint is unavailable", "setup": SETUP}


def ensure_chrome():
    # Default Chrome's singleton lock identifies its browser PID; never control its windows.
    lock = Path.home() / ".config/google-chrome/SingletonLock"
    try:
        pid = int(lock.readlink().name.rsplit("-", 1)[1])
        if Path(f"/proc/{pid}").exists():
            return
    except (OSError, ValueError, IndexError):
        pass
    subprocess.Popen(["/usr/bin/google-chrome", "--no-startup-window", "--no-first-run", "--no-default-browser-check"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def connector_save(url, safety, pub, *, collection=None, doi="", existing_key=None):
    checked_url(url)
    ensure_chrome()
    plugin = ZoteroPluginClient()
    ready_until = time.monotonic() + 35
    while not (status := connector_status()).get("ready"):
        if time.monotonic() >= ready_until:
            raise AcquireStop("Agent Connector is not active: " + status.get("error", SETUP))
        time.sleep(1)
    safety.before(pub, url, "browser")
    job_id = uuid4().hex
    plugin._request("/zotero-companion/acquire-job", method="POST", payload={"action": "submit", "job": {
        "id": job_id, "url": url, "doi": doi, "collection": collection, "existing_key": existing_key, "publisher": pub}})
    deadline = time.monotonic() + 225
    outcome = {}
    try:
        while time.monotonic() < deadline:
            status = plugin._request("/zotero-companion/acquire-job", method="POST", payload={"action": "status"})
            job = status.get("job") or {}
            if job.get("id") != job_id:
                raise AcquireStop("Connector job was lost; no retry")
            outcome = job.get("result") or {}
            if job.get("state") == "done":
                break
            if job.get("deadline") and time.time() * 1000 >= job["deadline"] + 15000:
                outcome = {"error": "Connector attempt timed out; no retry"}
                break
            time.sleep(1)
        else:
            outcome = {"error": "Connector attempt timed out; no retry"}
    except (PluginClientError, AcquireStop) as error:
        outcome = {"error": str(error)}
    # Pickup may lag submission by 20 seconds: space the next visit from completion.
    hosts = {canonical_host(pub), checked_url(url)}
    final = outcome.get("url")
    if final and urlsplit(final).hostname:
        hosts.add(canonical_host(urlsplit(final).hostname))
    for host in hosts:
        safety.data.setdefault(host, {})["last_browser"] = time.time()
    safety.save()
    if stop := outcome.get("stop"):
        try:
            safety.stop(pub, stop["reason"], host=checked_url(outcome.get("handoff") if
                        str(outcome.get("handoff", "")).startswith("https://") else final or url))
        except AcquireStop:
            pass
        if outcome.get("handoff") and (notify := shutil.which("notify-send")):
            try:
                subprocess.run([notify, "CSE Zotero needs a manual save",
                                f"{pub} needs you to save this paper; link in the agent's result"],
                               timeout=5, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (OSError, subprocess.TimeoutExpired):
                pass
    return outcome
