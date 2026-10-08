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
   article pages without blocking checks.
4. Human handoff with the exact DOI or official article URL.

Unattended acquisition works for open access through Unpaywall and PMC Cloud,
and through the official Elsevier/Wiley APIs when the user's token and
entitlement work. The everyday-Chrome Connector route is verified for Springer.
Elsevier, Wiley, AIP and ACS web routes commonly require a human; the job
returns the paper link rather than spending further publisher attempts.

PMC OA locations use NCBI's [official PMC Cloud dataset](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/) and its metadata-declared main PDF via Unpaywall's PMCID or the [ID Converter](https://pmc.ncbi.nlm.nih.gov/tools/id-converter-api/) fallback (`tool=cse-zotero`, maintainer email), preserving cooldowns, sequential one-request-per-second pacing, and the 50 MiB limit; PMC web PDF links and the legacy OA Web Service/compressed packages (retired August 2026) are never fetched.

The first successful route wins. Hard stops end acquisition immediately. OA
and API success create a translated parent only when attaching the PDF. The
Connector creates its own parent. Before the native save, the companion plugin
finds the pre-existing DOI match, or normalized title match, excluding trash,
and pins its key on the save session. Agent sessions save their items with
`skipSelect` and notifier `skipRenameFile` set before the add notification.
Zoplicate 5.1.1 recognizes those flags and never queues these additions for
automatic merging or its progress popup. Each created parent is marked in memory
with its save-session ID before notifications commit. The installed Linter,
Actions & Tags and Attanger hooks exclude that session's parents and attachments
before their automatic queues; this exclusion ends when finalization completes.
Ordinary sessions retain their native options and add-on behavior. No global
prefs or progress-window suppression are used. Finalization merges into the pinned parent with Zotero's native merge
and deletes only the newly saved duplicate.
It files the surviving parent in the requested collection. Failure leaves at
most one metadata-only parent and reports its key and the handoff URL. CLI
OA/API downloads and companion PDF imports must begin with `%PDF` and fit the
50 MiB limit; native Connector and desktop imports keep Zotero's validation.
Agent translation discards a purported ScienceDirect PDF that points back to an
article path; an article redirect is not a PDF.
The parent and PDF child are
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
`X-ELS-Status` when supplied. The user's current key is refused for Article
Retrieval; support ticket **261006-005015** is open. See the official
[Article Retrieval API](https://dev.elsevier.com/documentation/ArticleRetrievalAPI.wadl)
and [API authentication](https://dev.elsevier.com/tecdoc_api_authentication.html).

Wiley's API is
`https://api.wiley.com/onlinelibrary/tdm/v1/articles/<encoded-doi>` with
`Wiley-TDM-Client-Token`. Obtain a token through Wiley Online Library's account
and TDM agreement; institutional entitlement requires the institution network.
The user's Wiley token is not yet configured. The client uses Wiley's stricter
10-second interval. See
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
visit. Each attempt has a three-minute deadline, extended once by up to five
minutes for an interactive check; a stuck page is closed without reloading.
Article windows are created in normal state with `focused: false`; this keeps
the page visible to its JavaScript. The local GNOME/X11 fixture measured no
focus transition through create, native save, finalization or close. Agent jobs
never create human-check attachment popups. No job raises or focuses a window.
Agent jobs use the Connector's shipped request, retry, attachment fallback and
automatic-check handling, including its domain-whitelisted hidden iframe and
Amazon WAF request with `Sec-Fetch-Site: same-origin`. These internal requests
are part of one paper visit, as on a user toolbar click. CLI API/OA requests
are sequential and at most one per second globally, with Wiley at one per
10 seconds. Interrupted requests still
consume their recorded pacing slot. No parallel acquisition.

The Connector may wait on its one navigation window for an automatic check
(including Cloudflare “Just a moment” or a managed HTTP 403 with
`cf-mitigated: challenge`) to clear by itself for at most 15 seconds. If it
clears, continue the native save; otherwise stop with a 24-hour publisher and
responding-host cooldown. An explicit interactive check (human-verification
checkbox or CAPTCHA) keeps that same window minimized and unfocused, sends
one desktop notification through `notify-send` when available, and waits up to
five minutes for the user to clear it. The agent never raises the window,
clicks, enters input, solves the check, reloads, or retries. Clearing continues
the native save automatically. An unanswered interactive check closes the
window, returns the paper link, and records a 24-hour cooldown for the publisher
and responding host. Classification uses tab titles, response
headers and the document snapshots already sent by the official Connector.
When the Connector requests a human-check attachment popup, the agent never
creates that window. It immediately closes the job window, returns the paper
link, and records a 24-hour cooldown for the publisher and responding host.
The CLI sends one desktop notification when `notify-send` is available:
`<publisher> needs you to save this paper; link in the agent's result`.
Ordinary toolbar saves keep the Connector's original popup behavior.

Login walls, access denied, unusual activity, HTTP 429, and other HTTP 401/403
responses still hard-stop. A 429 on any job request (main frame, subresource,
or this extension's background request) immediately closes the job windows.
The cancellation guard stops native HTTP backoff from sending again; after
persisting the result the worker reloads to terminate remaining background
work. This is worker cancellation, never a page reload or another attempt.
The other page stops apply to the job page.
Login detection waits until the tab is complete and its URL has remained
stable for three seconds. Silent OAuth/SSO hops carrying `prompt=none` are
never classified as login walls or saved as article pages.
Native attachment handling may process automatic PDF/download checks as on a
toolbar click; a request for a human-check popup ends the agent job with a
handoff. API and direct OA requests retain their immediate challenge stops.
Record the reason. An observe-only browser response listener records HTTP 429,
`cf-mitigated: challenge` and `x-amzn-waf-action: challenge/captcha` from the job
tabs and background requests initiated by this extension. The observation
retains the URL path, request type, and whether it came from
the article tab or extension background; query strings are
omitted to avoid recording signed download credentials. The CLI writes a
24-hour cooldown for the publisher and every canonical responding host, even
if native handling completes the save. Unanswered interactive checks and
direct-route access challenges also cool the publisher and responding host;
the Elsevier API configuration skip remains exempt. Acquisitions refuse
either until expiry. The agent never adds solving, bypass, probe, replay or
retry behavior to the native Connector, nor attempts another route after a
hard stop. Do not remove safety state to evade cooldowns. Handoff reports the
exact paper URL. Agents do not sign in to publisher accounts; institutional
browser access is through the configured VPN.

Native translation keeps toolbar-click fallback enabled. An empty translation
is treated as a failure before saving, so the Connector can use its own next
translator or webpage fallback. Its native `saveItems` and `saveSnapshot`
sessions are pinned and finalized into the existing parent. Failed saves and
empty sessions hand off with a clear reason; a settled page with no detected
translator reports "no Zotero translator for this page". Job results retain
the detected translators, empty-result failure, and native save count/outcome.

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
`~/.local/share/cse/zotero/zotero-connector-agent/`. It adds the job worker,
shared public-URL validator and an empty job-marker page, and appends the
worker imports to `background-worker.js`; the copied manifest removes
the store `key` and sets the name to `Zotero Connector (agent)` for a separate
unpacked identity, with permissions unchanged. Other official application files,
including `itemSaver_background.js`, stay byte-identical. Chrome's generated `_metadata` rules
cache is omitted. The currently supported native API version is 5.0.217;
a newer installed version is reported as a mismatch and requires inspection
before rebuilding. The official installed files are never edited.

The user loads this unpacked extension once in `chrome://extensions` and turns
off the official Connector to avoid conflicting saves; see README setup.
`doctor --json` detects the copy by heartbeat, without a fixed extension ID,
and reports its active/version status and any mismatch.
The build publishes its module revision in `cse-agent-build.json` after writing
the extension files. The plugin reads that record for heartbeat and status
responses (`expected_revision`). An older idle worker calls
`chrome.runtime.reload()` once per newer revision, remembering the attempt in
local extension storage; active paper jobs finish before it reloads.
Doctor reports the running and expected revisions and any persisting mismatch.
Acquisition can start everyday Chrome with `--no-startup-window`; it never
stops the user's browser. A missing heartbeat stops with a setup message.
There is no dedicated browser, remote debugging, hidden display, headless
mode, spoofed user agent or input simulation.

The CLI posts one job to the local companion plugin's `/acquire-job` endpoint.
The added worker module picks it up every 20 seconds and uses a Chrome API
call to reset the MV3 idle timer, without adding manifest permissions.
A job is claimed once, checkpoints its owned window and save session, and is
never replayed after worker interruption. A claim without a window checkpoint
is finished as failed at its deadline, freeing the slot for new submissions.
Worker startup closes windows carrying this extension's job marker, including
ones created before a checkpoint. Windows follow the unfocused mode rule above,
with a marker tab and a target tab tracked before article navigation.
The module calls the native `saveWithTranslator` once.
Native translators, HTTP/cookie handling and attachment import perform the
save. The companion endpoint then preserves one parent in the requested
collection; the CLI verifies the parent and PDF through the local API.

Agents never attach a debugger to publisher pages or simulate input. Tab
URL/title, response status/headers and native completion results detect the page
stops and check waits described above. Public HTTPS destinations are required
at CLI and plugin submission and on owned main-frame navigation/redirects.
Loopback, private and link-local address literals, local names (`.local`,
`.internal`, `.localhost`, `.localdomain` and single-label hosts), and other
schemes are refused. The local job channel uses its fixed port 23119 endpoint.
During a job, a declarative block rule covers cooled domains for the job tabs
and extension background requests (`tabId: -1`); the rule is removed at job end.
The worker's HTTP entry guard enforces job cancellation, including native
backoff re-entry. It does not tag requests or classify internal destinations;
COHTTP and desktop resolver requests retain their native handling. Its native save-method hook only captures the pre-save parent and
session; its completion hook observes save progress. Zotero desktop's resolver
path (`saveAttachmentFromResolver` to `Attachments.addFileFromURLs`) remains
native, as on a user click, and is outside browser response observation.
Ordinary toolbar clicks retain their native behavior. Results include final
URL, title and observed status when available. The owned window stays minimized
during an interactive wait, and closes on completion or a terminal stop.
`--route browser` forces this one-paper route for
diagnostics with all safeguards retained.

## Retention boundary

Zotero attachments and project-selected data authorities remain external,
user-owned state. Git commits do not back them up. Corpus refresh does not
promote summaries or claims; retain exact source locators and the project's
chosen recovery policy.
