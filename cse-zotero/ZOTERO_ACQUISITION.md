# Zotero acquisition and external discovery

This contract owns external discovery and single-paper acquisition safeguards.
Zotero owns bibliographic records and retained attachments. Discovery metadata,
service summaries, and acquired PDFs do not establish scientific claims.

## Authority and interface

Search retained evidence and the live library before external discovery. Name
an unanswered literature gap before commissioning a new discovery search.
Reuse relevant completed Undermind searches when available; external workspace
changes and uploads retain their own authorization requirements.

An agent asked to get a specific paper may run:

```bash
cse-zotero acquire <DOI-or-article-URL> --collection <key-or-name> --json
cse-zotero acquire <DOI-or-article-URL> --collection <key-or-name> --dry-run --json
```

The request for that paper authorizes its parent and PDF child. This route has
no separate per-save approval, `--apply`, or native question gate. It accepts
one paper, never a crawl or batch. Metadata corrections, collection
reorganization, companion attachment writes, paid conversion, corpus refresh,
and bibliography export remain separate operations with their existing gates.

The dry run translates metadata, checks duplicates and the collection, and
reports planned routes without creating a parent or downloading a PDF. The
collection must already exist and be an unambiguous name or key in the personal
library. Without it, use Zotero's selected collection; a selected group library
is refused. A duplicate with a PDF returns both keys without moving or attaching
anything; one missing a PDF continues the permitted routes for its existing
parent. Deduplication checks DOI first, then normalized exact title.

DOIs embedded in article URLs and identifiers recognized by Zotero (DOI, ISBN,
arXiv, PMID) use Zotero's search translators. DOI translation is pinned to
Zotero's Crossref REST translator, which does not visit publisher pages.
Metadata lookups go to registries and library catalogs, not publishers, and keep Zotero's native request and retry handling within one CLI pacing slot.
URLs without a recognized identifier use the native Connector translator for
that article page. Do not invent metadata or PDF URLs.

## Route order and publisher boundaries

Acquisition checks DOI, then translated title duplicates, and tries:

1. Unpaywall's declared OA PDF locations, using
   `https://api.unpaywall.org/v2/<doi>?email=42780259+tannerpolley@users.noreply.github.com`.
2. The publisher's official API with a configured token for Elsevier or Wiley.
3. The modified official Zotero Connector in the user's everyday Chrome, for
   all publishers, including Elsevier, Wiley and ACS.
4. Human handoff with the exact DOI or official article URL.

PMC OA locations use NCBI's [official PMC Cloud dataset](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/) and its metadata-declared main PDF via Unpaywall's PMCID or the [ID Converter](https://pmc.ncbi.nlm.nih.gov/tools/id-converter-api/) fallback (`tool=cse-zotero`, maintainer email), preserving cooldowns, sequential one-request-per-second pacing, and the 50 MiB limit; PMC web PDF links and the legacy OA Web Service/compressed packages (retired August 2026) are never fetched.

The first successful route wins. Hard stops end acquisition immediately. OA
and API success create a translated parent only when attaching the PDF. The
Connector creates its own parent; the companion endpoint restores an existing
DOI/title duplicate as the explicit master, merges with Zotero's native item
merge, and deletes only the newly saved duplicate. This also handles an
automatic duplicate add-on that initially kept the new item and trashed the old one.
It files the surviving parent in the requested collection. Failure leaves at
most one metadata-only parent and reports its key and the handoff URL. A PDF
must begin with `%PDF` and fit the 50 MiB limit. The parent and PDF child are
verified through Zotero's local API. JSON reports `item_key`, `attachment_key`,
`collection_key`, `route`, `verified`, `stop_reason`, and `handoff_url`; incomplete
acquisition exits nonzero. A skipped API configuration error appears in
`skipped_routes`.

Identify Elsevier (member 78; `10.1016`, `10.1006`), Wiley (311; `10.1002`,
`10.1111`) and ACS (316; `10.1021`) by Crossref member and DOI prefix. Plain
Unpaywall downloads for these publishers require explicit `host_type: repository`
and never fetch their publisher/CDN hosts directly. Their browser fallback uses
the modified official Connector, with the same limits as every other publisher.

Elsevier's API is
`https://api.elsevier.com/content/article/doi/<encoded-doi>` with
`Accept: application/pdf`, `X-ELS-APIKey`, and optional `X-ELS-Insttoken`.
An API HTTP 403 with `X-ELS-Status: AUTHENTICATION_ERROR` or the equivalent
“Requestor configuration settings insufficient” error is a key configuration
skip, allowing Connector fall-through; a challenge response or HTTP 429 still
hard-stops. Other 401/403 responses also stop. Error messages retain
`X-ELS-Status` when supplied. See the official
[Article Retrieval API](https://dev.elsevier.com/documentation/ArticleRetrievalAPI.wadl)
and [API authentication](https://dev.elsevier.com/tecdoc_api_authentication.html).

Wiley's API is
`https://api.wiley.com/onlinelibrary/tdm/v1/articles/<encoded-doi>` with
`Wiley-TDM-Client-Token`. Obtain a token through Wiley Online Library's account
and TDM agreement; institutional entitlement requires the institution network.
The client uses Wiley's stricter 10-second interval. See
[Wiley's TDM documentation](https://onlinelibrary.wiley.com/library-info/resources/text-and-datamining).
No public ACS token API was verified; ACS uses OA then the normal Connector.

## VPN, pacing, and hard stops

Require the NetworkManager connection `CAEDM IKEv2 VPN` to be active before
each publisher-site, repository-PDF, or publisher-API request. Crossref and
Unpaywall metadata queries do not require it. When inactive, acquisition runs
`nmcli --wait 25 con up 'CAEDM IKEv2 VPN'` with a 30-second process limit,
then re-checks the active connection. Failed activation or unverifiable status
stops publisher access. This existing connection may be activated without
another approval. Never stop, reconfigure, rotate, or chain VPNs or proxies.
Never discover or report the public IP.

A nonblocking process lock serializes acquisition. Persist pacing, daily
counts, cooldowns, and stop reasons in
`~/.local/state/cse-zotero/acquire.json`. An unreadable state refuses remote
access. Browser attempts wait at least 60 seconds between single-paper visits to the
same publisher or host, with a daily cap of 25 attempts per publisher. Native
page resources, redirects, translation and PDF downloads belong to that one
visit. Each attempt has a three-minute deadline; a stuck page is closed without
reloading. Connector backoff retries and CAPTCHA/JavaScript challenge bypass
methods are blocked during the attempt. CLI API/OA requests are sequential and at most one per
second globally, with Wiley at one per 10 seconds. Interrupted requests still
consume their recorded pacing slot. No parallel acquisition.

Except for the Elsevier API configuration skip described above, publisher and
PDF requests stop without retry for HTTP 401, 403, or 429, CAPTCHA, Cloudflare/“Just a
moment”, human-verification or unusual-activity pages, login walls, or
non-PDF bytes where a PDF was expected. Record the reason. A publisher 429 or
challenge adds a 24-hour cooldown for both publisher and canonical responding
host; acquisitions refuse either until expiry. Do not solve, bypass, probe, replay, or retry
challenges, nor attempt another route after a hard stop. Do not remove safety
state to evade cooldowns. Handoff reports the exact paper URL. Agents do not sign in to publisher
accounts; institutional browser access is through the configured VPN.

## Tokens and everyday Chrome

Keep credentials out of repositories, logs, command-line arguments, and JSON.
Create these files under `~/.config/zotero-companion/`, each mode `600`, each
containing only the token on one line (an ending newline is allowed):

- `elsevier-api-key`: the user's registered Elsevier API key.
- `elsevier-insttoken`: optional institutional token paired with that key.
- `wiley-tdm-token`: Wiley click-through TDM client token.

`cse-zotero doctor --json` reports token names and configured/missing/invalid
status, never their values. ACS has no token file until an official supported
access mechanism is established. API requests identify this client honestly
as `cse-zotero/1.0 (mailto:42780259+tannerpolley@users.noreply.github.com)`. Credentials never follow
cross-host redirects.

Build the agent extension from the installed official Connector:

```bash
agent-heavy --timeout 15m --max 4G uv run python scripts/build_connector.py
cse-zotero doctor --json
cse-zotero acquire <doi> --collection <key> --route browser --json
```

The build copies the official Connector from everyday Chrome's Default profile,
ID `ekhagklcjbdpajgpjgmbionohlpdbjgc`, to
`~/.local/share/cse/zotero/zotero-connector-agent/`. It adds `connector-agent.js`
and appends its import to `background-worker.js`; the manifest and all other
application files stay byte-identical. Chrome's generated `_metadata` rules
cache is omitted. The currently supported native API version is 5.0.217;
a newer installed version is reported as a mismatch and requires inspection
before rebuilding. The official installed files are never edited.

The user loads this unpacked extension once in `chrome://extensions` and turns
off the official Connector to avoid conflicting saves; see README setup.
`doctor --json` reports its heartbeat, active/version status and any mismatch.
Acquisition can start everyday Chrome with `--no-startup-window`; it never
stops the user's browser. A missing heartbeat stops with a setup message.
There is no dedicated browser, remote debugging, hidden display, headless
mode, spoofed user agent or input simulation.

The CLI posts one job to the local companion plugin's `/acquire-job` endpoint.
The added worker module picks it up every 20 seconds and uses a Chrome API
call to reset the MV3 idle timer, without adding manifest permissions.
A job is claimed once, checkpoints its save session, and is never replayed
after worker interruption. A three-minute deadline closes its owned window.
The module creates a minimized, unfocused window, tracks its tab before
navigating to the article, and calls the native `saveWithTranslator` once.
Native translators, HTTP/cookie handling and attachment import perform the
save. The companion endpoint then preserves one parent in the requested
collection; the CLI verifies the parent and PDF through the local API.

Agents never attach a debugger to publisher pages or simulate input. Tab
URL/title, response status/headers and native completion results detect access
stops. Job-scoped request and PDF checks block backoff retries and all
challenge-bypass/solve-in-tab paths; ordinary toolbar clicks retain the native
behavior. Cooldown blocking is scoped to the job's tab. Results include final
URL, title and observed status when available. The owned window closes on
completion or any stop. `--route browser` forces this one-paper route for
diagnostics with all safeguards retained.

## Retention boundary

Zotero attachments and project-selected data authorities remain external,
user-owned state. Git commits do not back them up. Corpus refresh does not
promote summaries or claims; retain exact source locators and the project's
chosen recovery policy.
