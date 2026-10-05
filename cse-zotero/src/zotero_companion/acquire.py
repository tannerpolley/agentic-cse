"""Single-paper acquisition; all remote requests pass the persisted safety gate."""
from __future__ import annotations

import base64
import fcntl
import json
import os
import re
import stat
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, unquote, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .local_api import ZoteroLocalAPI
from .plugin_client import ZoteroPluginClient

EMAIL = "42780259+tannerpolley@users.noreply.github.com"
USER_AGENT = f"cse-zotero/1.0 (mailto:{EMAIL})"
STATE = Path.home() / ".local/state/cse-zotero/acquire.json"
CONFIG = Path.home() / ".config/zotero-companion"
TOKENS = ("elsevier-api-key", "elsevier-insttoken", "wiley-tdm-token")
RESTRICTED = {"elsevier", "wiley", "acs"}


class AcquireStop(RuntimeError):
    pass


def token(name):
    path = CONFIG / name
    if not path.exists():
        return None
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode) or stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise AcquireStop(f"Token file must be a regular file with mode 600: {path}")
    value = path.read_text().strip()
    if not value or any(c.isspace() for c in value):
        raise AcquireStop(f"Invalid token file: {path}")
    return value


def configured_tokens():
    result = {}
    for name in TOKENS:
        try:
            result[name] = "configured" if token(name) else "missing"
        except (OSError, AcquireStop):
            result[name] = "invalid_permissions_or_format"
    return result


def require_vpn():
    def active():
        try:
            names = subprocess.run(["nmcli", "-t", "-f", "NAME", "connection", "show", "--active"],
                                   capture_output=True, text=True, timeout=5, check=True).stdout.splitlines()
        except (OSError, subprocess.SubprocessError):
            raise AcquireStop("VPN status unavailable") from None
        return "CAEDM IKEv2 VPN" in names
    if active():
        return
    try:
        subprocess.run(["nmcli", "--wait", "25", "con", "up", "CAEDM IKEv2 VPN"],
                       capture_output=True, text=True, timeout=30, check=True)
    except (OSError, subprocess.SubprocessError):
        raise AcquireStop("Unable to activate CAEDM IKEv2 VPN; publisher access refused") from None
    if not active():
        raise AcquireStop("CAEDM IKEv2 VPN did not become active; publisher access refused")


def publisher(doi="", member=""):
    prefix = doi.lower().split("/")[0]
    if prefix in {"10.1016", "10.1006"} or str(member) == "78":
        return "elsevier"
    if prefix in {"10.1002", "10.1111"} or str(member) == "311":
        return "wiley"
    if prefix == "10.1021" or str(member) == "316":
        return "acs"
    return f"crossref-{member}" if member else prefix or "unknown"


def canonical_host(host):
    return host.rstrip(".").encode("idna").decode("ascii").lower().rstrip(".")


def restricted_host(host):
    host = canonical_host(host)
    for name, domains in {"elsevier": ("elsevier.com", "sciencedirect.com", "sciencedirectassets.com", "cell.com", "thelancet.com"),
                          "wiley": ("wiley.com", "wiley-vch.de"),
                          "acs": ("acs.org", "acs.figshare.com")}.items():
        if any(host == d or host.endswith("." + d) for d in domains):
            return name
    return None


def checked_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise AcquireStop("Remote URL must use HTTPS without embedded credentials")
    return canonical_host(parsed.hostname)


def challenge(text):
    text = text.lower()
    return next((s for s in ("just a moment", "captcha", "cf-chl-", "unusual activity", "access denied",
                            "verify you are human", "pow_challenge", "sign in to access", "log in to access", "login required")
                 if s in text), None)


def pdf_bytes(body):
    if not body.startswith(b"%PDF"):
        raise AcquireStop("Non-PDF bytes where a PDF was expected")
    return body


class Safety:
    def __init__(self, path=STATE):
        self.path = Path(path)

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = self.path.with_suffix(".lock").open("a")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close()
            raise AcquireStop("Another acquisition is running") from None
        try:
            self.data = json.loads(self.path.read_text()) if self.path.exists() else {}
            if not isinstance(self.data, dict) or any(
                not isinstance(value, (int, float) if key == "last_api" else dict)
                for key, value in self.data.items()
            ):
                raise ValueError()
        except (OSError, ValueError):
            self.lock.close()
            raise AcquireStop("Acquisition safety state is unreadable; refusing remote access") from None
        return self

    def __exit__(self, *_):
        self.lock.close()

    def save(self):
        temp = self.path.with_suffix(".tmp")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as out:
            json.dump(self.data, out)
        os.chmod(temp, 0o600)
        temp.replace(self.path)

    def available(self, pub):
        entry = self.data.get(canonical_host(pub), {})
        remaining = entry.get("cooldown_until", 0) - time.time()
        if remaining > 0:
            raise AcquireStop(f"{pub} cooldown active for {int(remaining)} seconds")

    def stop(self, pub, reason, *, cooldown=False, host=""):
        now = time.time()
        for key in {canonical_host(pub), canonical_host(host)} - {""}:
            entry = self.data.setdefault(key, {})
            entry.update(stop_reason=reason, stopped_at=now)
            if cooldown:
                entry["cooldown_until"] = now + 86400
        self.save()
        raise AcquireStop(reason)

    def check_url(self, url, *, api=False):
        host = checked_url(url)
        blocked = restricted_host(host)
        if blocked and not api:
            raise AcquireStop(f"{blocked} publisher sites are API-only")
        if api and host not in {"api.elsevier.com", "api.wiley.com"}:
            raise AcquireStop("Publisher API redirect outside official API host refused")
        self.available(host)
        return host

    def before(self, pub, url, route, *, api=False, public=False):
        host = self.check_url(url, api=api) if url else ""
        self.available(pub)
        if not public:
            require_vpn()
        entry = self.data.setdefault(pub, {})
        now = time.time()
        if route == "browser":
            day = time.strftime("%Y-%m-%d", time.gmtime(now))
            if entry.get("day") != day:
                entry.update(day=day, count=0)
            if entry.get("count", 0) >= 25:
                raise AcquireStop(f"{pub} daily browser request cap reached (25)")
            last = self.data.get(host, {}).get("last_browser", 0)
            delay = 60 - (now - last)
        else:
            delay = (10 if pub == "wiley" else 1) - (now - self.data.get("last_api", 0))
        if delay > 0:
            time.sleep(min(delay, 60))
        if not public:
            require_vpn()
        if route == "browser":
            entry["count"] = entry.get("count", 0) + 1
            self.data.setdefault(host, {})["last_browser"] = time.time()
        else:
            self.data["last_api"] = time.time()
        self.save()

    def response(self, pub, status, body=b"", *, is_pdf=False, host=""):
        reason = None if body.startswith(b"%PDF") else challenge(body[:200000].decode("utf-8", "replace"))
        if reason:
            self.stop(pub, f"Publisher access challenge: {reason} (HTTP {status})", cooldown=True, host=host)
        if status in {401, 403, 429}:
            self.stop(pub, f"Publisher HTTP {status}; no retry", cooldown=status == 429, host=host)
        if is_pdf and not body.startswith(b"%PDF"):
            self.stop(pub, "Non-PDF bytes where a PDF was expected", host=host)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_):
        return None


def request(url, *, safety=None, pub="", route="oa", headers=None, is_pdf=False):
    opener = build_opener(NoRedirect())
    for _ in range(8):
        host = checked_url(url)
        public = host in {"api.crossref.org", "api.unpaywall.org"}
        if safety:
            safety.before(pub or host, url, route, api=route == "api", public=public)
        elif not public:
            raise AcquireStop("Remote publisher access requires the acquisition safety gate")
        try:
            response = opener.open(Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})}), timeout=30)
        except HTTPError as exc:
            response = exc
        except (URLError, TimeoutError):
            raise AcquireStop("Remote request failed; no retry") from None
        with response:
            final_host = checked_url(response.geturl())
            if public and final_host not in {"api.crossref.org", "api.unpaywall.org"}:
                raise AcquireStop("Metadata service redirected outside its API; refused")
            if safety:
                safety.check_url(response.geturl(), api=route == "api")
            status = response.code
            body = response.read(50 * 1024 * 1024 + 1)
            if not public:
                safety.response(pub, status, body, host=final_host)
            if status in {301, 302, 303, 307, 308}:
                target = urljoin(url, response.headers.get("Location", ""))
                if public and checked_url(target) not in {"api.crossref.org", "api.unpaywall.org"}:
                    raise AcquireStop("Metadata service redirected outside its API; refused")
                # Never forward publisher credentials to another host.
                if headers and checked_url(target) != host:
                    raise AcquireStop("API credential redirect refused")
                url = target
                continue
            if status == 404:
                return None
            if status >= 400:
                raise AcquireStop(f"Remote HTTP {status}; no retry")
            if len(body) > 50 * 1024 * 1024:
                raise AcquireStop("PDF exceeds 50 MiB limit")
            if is_pdf:
                safety.response(pub, status, body, is_pdf=True, host=final_host)
            return body
    raise AcquireStop("Redirect limit exceeded; no retry")


def identifier(value):
    value = value.strip()
    if value.startswith(("http://", "https://")):
        parsed = urlsplit(value)
        host = checked_url(value.replace("http://", "https://", 1))
        candidates = parse_qs(parsed.query)
        candidate = next((v for key in ("doi", "id") for v in candidates.get(key, [])
                          if re.match(r"10\.\d{4,9}/", v, re.I)), None)
        path = unquote(parsed.path)
        if host not in {"doi.org", "dx.doi.org"}:
            path = re.sub(r"/(?:full|pdf|epdf|abstract)/?$", "", path, flags=re.I)
        match = re.search(r"10\.\d{4,9}/[^\s?#]+", candidate or path, re.I)
    else:
        match = re.search(r"10\.\d{4,9}/[^\s?#]+", unquote(value), re.I)
    return match.group(0).lower() if match else value


def duplicate(items, doi=""):
    if not doi:
        return None
    for item in items:
        data = item.get("data", item)
        if data.get("itemType") not in {"attachment", "note"} and identifier(data.get("DOI", "")) == doi:
            return item.get("key") or data["key"]
    return None


def use_existing_parent(api, result, key):
    result["item_key"] = key
    children = api.get(f"/api/users/0/items/{key}/children")
    pdf = next((i["key"] for i in children if i["data"].get("contentType") == "application/pdf"), None)
    if pdf:
        result.update(ok=True, attachment_key=pdf, route="existing", verified=True, handoff_url=None)
    return bool(pdf)


def acquire(value, *, collection=None, dry_run=False, route="auto"):
    result = {"ok": False, "item_key": None, "attachment_key": None, "route": None, "stop_reason": None,
              "handoff_url": None}
    api = ZoteroLocalAPI()
    plugin = ZoteroPluginClient(timeout=90)
    try:
        with Safety() as safety:
            ident = identifier(value)
            if value.startswith(("http://", "https://")):
                result["handoff_url"] = value.replace("http://", "https://", 1)
            doi = ident if ident.startswith("10.") else ""
            result["doi"] = doi or None
            if doi:
                result["handoff_url"] = "https://doi.org/" + doi
            existing = duplicate(api.items(top_level=True), doi)
            if existing and use_existing_parent(api, result, existing):
                return result
            crossref = {}
            if doi:
                raw = request("https://api.crossref.org/works/" + quote(doi, safe=""), safety=safety)
                crossref = json.loads(raw)["message"] if raw else {}
            pub = publisher(doi, crossref.get("member", ""))
            result["publisher"] = pub
            if route == "browser" and pub in RESTRICTED:
                raise AcquireStop(f"{pub} is API-only; browser route refused")
            safety.available(pub)
            if existing:
                metadata = {"metadata": api.get(f"/api/users/0/items/{existing}")["data"]}
            else:
                safety.before(pub, None, "api", public=True)  # Reserve the native metadata operation's slot.
                metadata = plugin._request("/zotero-companion/acquire-metadata", method="POST",
                                           payload={"identifier": ident, "collection": collection, "mode": "dry-run" if dry_run else "apply"})
                if not dry_run:
                    result.update(item_key=metadata.get("item_key"), collection_key=metadata.get("collection_key"))
                if metadata.get("existing") and use_existing_parent(api, result, metadata["item_key"]):
                    return result
            if not doi:
                native = metadata.get("metadata", {})
                doi = identifier(native.get("DOI", ""))
                if doi:
                    result.update(doi=doi, handoff_url="https://doi.org/" + doi)
                    raw = request("https://api.crossref.org/works/" + quote(doi, safe=""), safety=safety)
                    crossref = json.loads(raw)["message"] if raw else {}
                    pub = publisher(doi, crossref.get("member", ""))
                    result["publisher"] = pub
                elif native.get("url"):
                    target = native["url"].replace("http://", "https://", 1)
                    checked_url(target)
                    result["handoff_url"] = target
                safety.available(pub)
                if route == "browser" and pub in RESTRICTED:
                    raise AcquireStop(f"{pub} is API-only; browser route refused")
            if dry_run:
                return {**result, "ok": True, "mode": "dry-run", "metadata": metadata,
                        "tokens": configured_tokens(), "planned_routes": ["oa", "api", "handoff"] if pub in RESTRICTED else ["oa", "browser", "handoff"]}
            body = None
            if doi and route == "auto":
                raw = request("https://api.unpaywall.org/v2/" + quote(doi, safe="") + "?email=" + EMAIL, safety=safety)
                oa = json.loads(raw) if raw else {}
                locations = [oa.get("best_oa_location")] + oa.get("oa_locations", [])
                seen = set()
                for location in locations:
                    location = location or {}
                    if pub in RESTRICTED and location.get("host_type") != "repository":
                        continue
                    url = location.get("url_for_pdf")
                    if not url or url in seen or restricted_host(checked_url(url)):
                        continue
                    seen.add(url)
                    body = request(url, safety=safety, pub=pub, is_pdf=True)
                    if body:
                        result["route"] = "unpaywall"
                        break
            if not body and route == "auto" and pub in {"elsevier", "wiley"}:
                name = "elsevier-api-key" if pub == "elsevier" else "wiley-tdm-token"
                credential = token(name)
                if credential:
                    if pub == "elsevier":
                        url = "https://api.elsevier.com/content/article/doi/" + quote(doi, safe="")
                        headers = {"X-ELS-APIKey": credential, "Accept": "application/pdf"}
                        inst = token("elsevier-insttoken")
                        if inst:
                            headers["X-ELS-Insttoken"] = inst
                    else:
                        url = "https://api.wiley.com/onlinelibrary/tdm/v1/articles/" + quote(doi, safe="")
                        headers = {"Wiley-TDM-Client-Token": credential, "Accept": "application/pdf"}
                    body = request(url, safety=safety, pub=pub, route="api", headers=headers, is_pdf=True)
                    if body:
                        result["route"] = pub + "-api"
            if not body and pub not in RESTRICTED and result["handoff_url"]:
                from .agent_browser import browser_pdf
                body = browser_pdf(result["handoff_url"] or value, safety, pub)
                if body:
                    result["route"] = "browser"
            if not body:
                raise AcquireStop("No permitted PDF route; save with the normal Zotero Connector")
            attached = plugin._request("/zotero-companion/acquire-attachment", method="POST",
                                       payload={"item_key": result["item_key"], "pdf_base64": base64.b64encode(pdf_bytes(body)).decode(), "mode": "apply"})
            result["attachment_key"] = attached["attachment_key"]
            parent = api.get(f"/api/users/0/items/{result['item_key']}")["data"]
            children = api.get(f"/api/users/0/items/{result['item_key']}/children")
            if doi and identifier(parent.get("DOI", "")) != doi:
                raise AcquireStop("Live verification failed: parent DOI differs")
            if not doi and (not parent.get("title") or parent["title"] != metadata["metadata"].get("title")):
                raise AcquireStop("Live verification failed: parent title differs from translated metadata")
            if not any(i["key"] == result["attachment_key"] and i["data"].get("contentType") == "application/pdf" for i in children):
                raise AcquireStop("Live verification failed: PDF child is missing")
            result.update(ok=True, verified=True, handoff_url=None)
    except (AcquireStop, OSError, ValueError, KeyError, RuntimeError) as exc:
        result["stop_reason"] = str(exc)
    return result
