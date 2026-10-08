"""Single-paper acquisition with persisted CLI pacing and native Connector saves."""
from __future__ import annotations

import base64
from contextlib import ExitStack
import fcntl
import json
import ipaddress
import os
import re
import stat
import socket
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, unquote, urljoin, urlsplit
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from xml.etree import ElementTree as ET

from .local_api import ZoteroLocalAPI
from .plugin_client import ZoteroPluginClient

EMAIL = "42780259+tannerpolley@users.noreply.github.com"
USER_AGENT = f"cse-zotero/1.0 (mailto:{EMAIL})"
STATE = Path.home() / ".local/state/cse-zotero/acquire.json"
CONFIG = Path.home() / ".config/zotero-companion"
TOKENS = ("elsevier-api-key", "elsevier-insttoken", "wiley-tdm-token")
RESTRICTED = {"elsevier", "wiley", "acs"}
PMC_CLOUD_HOST = "pmc-oa-opendata.s3.amazonaws.com"
PMC_CLOUD = "https://" + PMC_CLOUD_HOST


class AcquireStop(RuntimeError):
    pass


class Cooldown(AcquireStop):
    """An earlier stop still cools this host; optional free-copy sources skip it."""


class APIConfiguration(AcquireStop):
    """A verified API key configuration error permits Connector fall-through."""


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
    host = canonical_host(unquote(parsed.hostname))
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        try:
            address = ipaddress.ip_address(socket.inet_ntoa(socket.inet_aton(host)))
        except OSError:
            address = None
    if address:
        if not address.is_global or address.is_multicast or address.is_reserved:
            raise AcquireStop("Remote URL must use a public destination")
    elif "." not in host or host.endswith((".local", ".internal", ".localhost", ".localdomain")) or not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", host):
        raise AcquireStop("Remote URL must use a public destination")
    return host


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
            raise Cooldown(f"{pub} cooldown active for {int(remaining)} seconds")

    def stop(self, pub, reason, *, cooldown=False, host="", at=None):
        now = time.time() if at is None else at
        for key in {canonical_host(pub), canonical_host(host)} - {""}:
            entry = self.data.setdefault(key, {})
            if entry.get("stopped_at", 0) > now:
                continue
            entry.update(stop_reason=reason, stopped_at=now)
            if cooldown:
                entry["cooldown_until"] = max(entry.get("cooldown_until", 0), now + 86400)
        self.save()
        raise AcquireStop(reason)

    def check_url(self, url, *, api=False, browser=False):
        host = checked_url(url)
        if not browser and host in {"pmc.ncbi.nlm.nih.gov", "www.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov"} and re.search(r"/pdf(?:/|$)", urlsplit(url).path, re.I):
            raise AcquireStop("PMC web PDF links require the official PMC Cloud route")
        blocked = restricted_host(host)
        if blocked and not (api or browser):
            raise AcquireStop(f"{blocked} publisher sites require the Connector or official API")
        if api and host not in {"api.elsevier.com", "api.wiley.com"}:
            raise AcquireStop("Publisher API redirect outside official API host refused")
        self.available(host)
        return host

    def before(self, pub, url, route, *, api=False, public=False):
        pub = canonical_host(pub)
        host = self.check_url(url, api=api, browser=route == "browser") if url else ""
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
                raise AcquireStop(f"{pub} daily browser attempt cap reached (25)")
            last = max(entry.get("last_browser", 0), self.data.get(host, {}).get("last_browser", 0))
            delay = 60 - (now - last)
        else:
            delay = (10 if pub == "wiley" else 1) - (now - self.data.get("last_api", 0))
        if delay > 0:
            time.sleep(min(delay, 60))
        if not public:
            require_vpn()
        if route == "browser":
            entry["count"] = entry.get("count", 0) + 1
            entry["last_browser"] = time.time()
            self.data.setdefault(host, {})["last_browser"] = time.time()
        else:
            self.data["last_api"] = time.time()
        self.save()

    def response(self, pub, status, body=b"", *, is_pdf=False, host="", detail=""):
        reason = None if body.startswith(b"%PDF") else challenge(body[:200000].decode("utf-8", "replace"))
        if reason:
            self.stop(pub, f"Publisher access challenge: {reason} (HTTP {status})", cooldown=True, host=host)
        if status in {401, 403, 429}:
            self.stop(pub, f"Publisher HTTP {status}{': ' + detail if detail else ''}; no retry", cooldown=status == 429, host=host)
        if is_pdf and not body.startswith(b"%PDF"):
            self.stop(pub, "Non-PDF bytes where a PDF was expected", host=host)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_):
        return None


def request(url, *, safety=None, pub="", route="oa", headers=None, is_pdf=False, allowed_hosts=None):
    opener = build_opener(NoRedirect())
    for _ in range(8):
        host = checked_url(url)
        if allowed_hosts and host not in allowed_hosts:
            raise AcquireStop("Official service redirect outside its allowed host refused")
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
            if allowed_hosts and final_host not in allowed_hosts:
                raise AcquireStop("Official service redirect outside its allowed host refused")
            if public and final_host not in {"api.crossref.org", "api.unpaywall.org"}:
                raise AcquireStop("Metadata service redirected outside its API; refused")
            if safety:
                safety.check_url(response.geturl(), api=route == "api")
            status = response.code
            body = response.read(50 * 1024 * 1024 + 1)
            detail = response.headers.get("X-ELS-Status", "")
            if route == "api" and status >= 400:
                detail = detail or body.decode("utf-8", "replace").strip()
                for value in (headers or {}).values():
                    detail = detail.replace(value, "[redacted]")
                detail = detail.replace("\n", " ")[:240]
            if route == "api" and pub == "elsevier" and status == 403 and not challenge(body.decode("utf-8", "replace")):
                if "AUTHENTICATION_ERROR" in detail or "Requestor configuration settings insufficient" in body.decode("utf-8", "replace"):
                    raise APIConfiguration("Elsevier API HTTP 403: " + (detail or "AUTHENTICATION_ERROR: Requestor configuration settings insufficient"))
            if not public:
                safety.response(pub, status, body, host=final_host, detail=detail)
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
                raise AcquireStop(f"Remote HTTP {status}{': ' + detail if detail else ''}; no retry")
            if len(body) > 50 * 1024 * 1024:
                raise AcquireStop("PDF exceeds 50 MiB limit")
            if is_pdf:
                safety.response(pub, status, body, is_pdf=True, host=final_host)
            return body
    raise AcquireStop("Redirect limit exceeded; no retry")


def pmc_id(location):
    for field in ("url_for_pdf", "url_for_landing_page", "url"):
        parsed = urlsplit(location.get(field) or "")
        if canonical_host(parsed.hostname or "") in {"pmc.ncbi.nlm.nih.gov", "www.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov"}:
            match = re.search(r"/(?:pmc/)?articles/(?:PMC)?(\d+)(?:/|$)", parsed.path, re.I)
            if match:
                return "PMC" + match[1]
    match = re.fullmatch(r"oai:pubmedcentral.nih.gov:(\d+)", location.get("pmh_id") or "")
    return "PMC" + match[1] if match else None


def optional(fetch, *args, **kwargs):
    try:
        return fetch(*args, **kwargs)
    except Cooldown:
        return None


def pmc_pdf(pmcid, doi, safety):
    if not pmcid:
        url = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/?" + urlencode(
            {"ids": doi, "idtype": "doi", "format": "json", "tool": "cse-zotero", "email": EMAIL})
        raw = request(url, safety=safety, pub="ncbi-pmc", allowed_hosts={"pmc.ncbi.nlm.nih.gov"})
        records = json.loads(raw).get("records", []) if raw else []
        pmcid = next((r.get("pmcid") for r in records if r.get("doi", "").lower() == doi), None)
    if not pmcid or not re.fullmatch(r"PMC\d+", pmcid):
        return None
    url = PMC_CLOUD + "/?" + urlencode({"list-type": 2, "prefix": "metadata/" + pmcid + ".", "max-keys": 20})
    raw = request(url, safety=safety, pub="ncbi-pmc", allowed_hosts={PMC_CLOUD_HOST})
    if not raw:
        return None
    try:
        listing = ET.fromstring(raw)
    except ET.ParseError:
        raise AcquireStop("Invalid PMC Cloud listing; no retry") from None
    if listing.findtext("{*}IsTruncated") == "true":
        raise AcquireStop("PMC article has more than 20 versions; automatic retrieval refused")
    records = []
    for node in listing.findall("{*}Contents/{*}Key"):
        if not re.fullmatch(r"metadata/" + pmcid + r"\.\d+\.json", node.text or ""):
            continue
        raw = request(PMC_CLOUD + "/" + node.text, safety=safety, pub="ncbi-pmc", allowed_hosts={PMC_CLOUD_HOST})
        if raw:
            records.append(json.loads(raw))
    # Prefer the published article; version numbers do not imply publication order.
    for record in sorted(records, key=lambda r: bool(r.get("is_manuscript"))):
        if record.get("pmcid") != pmcid or record.get("doi", "").lower() != doi or not record.get("is_pmc_openaccess"):
            continue
        url = record.get("pdf_url")
        if not url:
            continue
        url = url.replace("s3://pmc-oa-opendata/", PMC_CLOUD + "/", 1)
        if checked_url(url) != PMC_CLOUD_HOST or not re.match("/" + pmcid + r"\.\d+/", urlsplit(url).path):
            raise AcquireStop("PMC declared PDF is outside the official article prefix")
        body = request(url, safety=safety, pub="ncbi-pmc", is_pdf=True, allowed_hosts={PMC_CLOUD_HOST})
        if body:
            return body
    return None


def identifier(value):
    value = value.strip()
    if value.startswith(("http://", "https://")):
        parsed = urlsplit(value)
        host = checked_url(value)
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
    ident = ""
    metadata = None
    connector_session = None
    def ensure_parent():
        if not result["item_key"] and metadata is not None and not connector_session:
            safety.before("metadata", None, "api", public=True)
            created = plugin._request("/zotero-companion/acquire-metadata", method="POST",
                                      payload={"identifier": ident, "collection": collection, "mode": "apply"})
            result.update(item_key=created["item_key"], collection_key=created.get("collection_key"))
    with ExitStack() as stack:
        try:
            safety = stack.enter_context(Safety())
            if re.match(r"^[a-z][a-z0-9+.-]*:", value, re.I) and not re.match(r"^(?:doi|isbn|arxiv|pmid|pmcid):", value, re.I):
                checked_url(value)
            ident = identifier(value)
            if value.startswith(("http://", "https://")):
                result["handoff_url"] = value
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
            if not doi and result["handoff_url"]:
                host = checked_url(result["handoff_url"])
                pub = restricted_host(host) or host
            result["publisher"] = pub
            if existing:
                metadata = {"metadata": api.get(f"/api/users/0/items/{existing}")["data"]}
            elif not ident.startswith(("http://", "https://")):
                safety.before("metadata", None, "api", public=True)  # Reserve the native metadata operation's slot.
                metadata = plugin._request("/zotero-companion/acquire-metadata", method="POST",
                                           payload={"identifier": ident, "collection": collection, "mode": "dry-run"})
                result["collection_key"] = metadata.get("collection_key")
                if metadata.get("existing") and use_existing_parent(api, result, metadata["item_key"]):
                    return result
            if not doi:
                native = (metadata or {}).get("metadata", {})
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
            if dry_run:
                if metadata is None:
                    result.update(plugin._request("/zotero-companion/acquire-connector", method="POST",
                                                  payload={"collection": collection, "mode": "dry-run"}))
                return {**result, "ok": True, "mode": "dry-run", "metadata": metadata,
                        "tokens": configured_tokens(), "planned_routes": ["oa", "api", "connector", "handoff"]}
            body = None
            if doi and route == "auto":
                raw = request("https://api.unpaywall.org/v2/" + quote(doi, safe="") + "?email=" + EMAIL, safety=safety)
                oa = json.loads(raw) if raw else {}
                locations = [oa.get("best_oa_location")] + oa.get("oa_locations", [])
                seen = set()
                tried_pmc = False
                for location in locations:
                    location = location or {}
                    if pub in RESTRICTED and location.get("host_type") != "repository":
                        continue
                    pmcid = pmc_id(location)
                    if pmcid:
                        if pmcid not in seen:
                            seen.add(pmcid)
                            tried_pmc = True
                            body = optional(pmc_pdf, pmcid, doi, safety)
                            if body:
                                result["route"] = "pmc-cloud"
                                break
                        continue
                    url = location.get("url_for_pdf")
                    if not url or url in seen or restricted_host(checked_url(url)):
                        continue
                    seen.add(url)
                    body = optional(request, url, safety=safety, pub=pub, is_pdf=True)
                    if body:
                        result["route"] = "unpaywall"
                        break
                if not body and not tried_pmc:
                    body = optional(pmc_pdf, None, doi, safety)
                    if body:
                        result["route"] = "pmc-cloud"
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
                    try:
                        body = request(url, safety=safety, pub=pub, route="api", headers=headers, is_pdf=True)
                    except APIConfiguration as exc:
                        result["skipped_routes"] = [str(exc)]
                    if body:
                        result["route"] = pub + "-api"
            if not body and result["handoff_url"]:
                from .connector_job import connector_save
                preflight = plugin._request("/zotero-companion/acquire-connector", method="POST",
                                            payload={"collection": collection, "mode": "dry-run"})
                result["collection_key"] = preflight.get("collection_key")
                result["route"] = "connector"
                saved = connector_save(result["handoff_url"], safety, pub,
                                       collection=result["collection_key"], doi=doi, existing_key=result["item_key"])
                stop = saved.get("stop")
                result["browser"] = {k: (stop or {}).get(k, saved.get(k)) for k in ("url", "title", "status")}
                connector_session = saved.get("session_id")
                if connector_session:
                    filed = plugin._request("/zotero-companion/acquire-connector", method="POST", payload={
                        "mode": "apply", "session_id": connector_session, "doi": doi,
                        "existing_key": result["item_key"], "collection": result["collection_key"] or collection})
                    result.update({k: filed[k] for k in ("item_key", "attachment_key", "collection_key") if k in filed})
                    if filed.get("handoff"):
                        raise AcquireStop(filed["handoff"])
                    metadata = {"metadata": filed["metadata"]}
                if stop:
                    raise AcquireStop(stop["reason"])
                if saved.get("handoff") or saved.get("error"):
                    raise AcquireStop(saved.get("handoff") or saved["error"])
                if result["attachment_key"]:
                    result["route"] = "connector"
            if body:
                ensure_parent()
                attached = plugin._request("/zotero-companion/acquire-attachment", method="POST",
                                       payload={"item_key": result["item_key"], "pdf_base64": base64.b64encode(pdf_bytes(body)).decode(), "mode": "apply"})
                result["attachment_key"] = attached["attachment_key"]
            if not result["attachment_key"]:
                raise AcquireStop((saved.get("error") if not body and result["handoff_url"] else None) or "No PDF acquired; save with the normal Zotero Connector")
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
            if not dry_run:
                try:
                    ensure_parent()
                except (OSError, ValueError, KeyError, RuntimeError) as error:
                    result["stop_reason"] += "; metadata save failed: " + str(error)
    return result
