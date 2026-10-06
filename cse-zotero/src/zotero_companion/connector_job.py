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
        return {k: status.get(k) for k in ("ready", "version", "supported_version", "module_revision", "heartbeat_at", "error")}
    except PluginClientError:
        return {"ready": False, "error": "CSE Zotero plugin job endpoint is unavailable", "setup": SETUP}


def reconcile_stop(safety, plugin):
    """Retain cooldown observations even if the previous CLI died before receiving them."""
    try:
        job = plugin._request("/zotero-companion/acquire-job", method="POST", payload={"action": "status"}).get("job") or {}
    except PluginClientError:
        return
    if job.get("state") in {"queued", "running", "stopping"}:
        raise AcquireStop("Another Connector acquisition is running; no parallel paper visits")
    record_observations(safety, job.get("publisher"), job.get("result") or {})


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


def record_observations(safety, pub, outcome):
    events = list(outcome.get("observations") or [])
    if stop := outcome.get("stop"):
        events.append({**stop, "at": outcome.get("stopped_at", time.time())})
    for event in sorted(events, key=lambda e: e.get("at", 0)):
        at = event.get("at", 0)
        if pub and at + 86400 > time.time():
            try:
                safety.stop(pub, event["reason"], host=event.get("host", ""),
                            cooldown=event.get("cooldown", False), at=at)
            except AcquireStop:
                pass


def connector_save(url, safety, pub, *, collection=None, doi=""):
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
        "id": job_id, "url": url, "doi": doi, "collection": collection, "publisher": pub,
        "cooldowns": {k: v.get("cooldown_until", 0) for k, v in safety.data.items() if isinstance(v, dict)}}})
    deadline = time.monotonic() + 225
    outcome = {}
    notified = False
    try:
        while time.monotonic() < deadline:
            status = plugin._request("/zotero-companion/acquire-job", method="POST", payload={"action": "status"})
            job = status.get("job") or {}
            if job.get("id") != job_id:
                raise AcquireStop("Connector job was lost; no retry")
            outcome = job.get("result") or {}
            if not notified and (check := outcome.get("check") or {}).get("kind") == "interactive":
                notified = True
                deadline += 300
                if notify := shutil.which("notify-send"):
                    try:
                        subprocess.run([notify, "CSE Zotero needs a check completed",
                                        f"{checked_url(check['url'])} needs you to complete a check in Chrome; the save will finish automatically. Open its minimized window."],
                                       timeout=5, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except (OSError, subprocess.TimeoutExpired):
                        pass
            if job.get("state") in {"done", "stopping"}:
                break
            time.sleep(1)
        else:
            plugin._request("/zotero-companion/acquire-job", method="POST", payload={"action": "cancel", "id": job_id})
            outcome["stop"] = {"reason": "Connector attempt timed out; no reload or retry", "host": checked_url(url)}
    except (PluginClientError, AcquireStop):
        outcome["stop"] = {"reason": "Connector job disconnected; no retry", "host": checked_url(url)}
    # Pickup may lag submission by 20 seconds: space the next visit from completion.
    hosts = {canonical_host(pub), checked_url(url)}
    final = outcome.get("url")
    if final and urlsplit(final).hostname:
        hosts.add(canonical_host(urlsplit(final).hostname))
    for host in hosts:
        safety.data.setdefault(host, {})["last_browser"] = time.time()
    safety.save()
    return outcome
