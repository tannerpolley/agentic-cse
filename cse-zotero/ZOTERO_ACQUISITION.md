# Zotero acquisition and external discovery

This contract owns single-paper acquisition. Zotero owns bibliographic records
and retained attachments; discovery metadata and acquired PDFs do not establish
scientific claims. Search retained evidence and the live library before external
discovery, name the unanswered gap, and reuse completed searches when relevant.
External workspace changes and uploads retain their own authorization rules.

## One paper

Each paper is identified by DOI or article URL. Either the user's request or an
agent's finding that a relevant paper is missing from the library authorizes
its parent and PDF child. An agent-found paper goes to the project's registered
collection; without one, report the paper instead of acquiring it.

```bash
cse-zotero acquire <DOI-or-article-URL> --collection <key-or-name> --json
cse-zotero acquire <DOI-or-article-URL> --collection <key-or-name> --dry-run --json
```

Acquisition is sequential and accepts one paper. The dry run checks metadata,
duplicates and the collection without creating items, downloading PDFs or
starting Chrome. The collection must exist in the personal library; selected
group libraries are refused. Deduplication uses DOI, then normalized exact title,
ignoring trash. An existing PDF returns its keys immediately. Other library
writes keep their existing previews and approvals.

## Routes

Try Unpaywall's declared open-access PDF locations, PMC Cloud, an official
Elsevier/Wiley API when configured, then the everyday-Chrome Connector. The
first PDF wins; an incomplete acquisition hands back the DOI or article link.
DOI metadata uses Zotero's Crossref translator. Do not invent PDF URLs.

Unattended acquisition works for open access and official APIs with working
tokens and entitlement. Springer is verified through the Connector. Elsevier,
Wiley, AIP and ACS web routes commonly need a human. The current Elsevier key is
refused for Article Retrieval (support ticket **261006-005015**); the Wiley token
is not yet configured. Elsevier's explicit key-configuration error skips that
API; challenge responses and 429 still stop acquisition.

PMC uses its official Cloud dataset and metadata-declared PDF, with the ID
Converter as a fallback. Do not fetch PMC web PDF links or legacy OA packages.
Elsevier/Wiley/ACS direct OA downloads require a declared repository location,
excluding their publisher/CDN hosts. CLI PDF downloads and imports require a
`%PDF` prefix and fit the 50 MiB limit. Native Connector downloads stay native.

Tokens live in mode-0600 files under `~/.config/zotero-companion/`:
`elsevier-api-key`, optional `elsevier-insttoken`, and `wiley-tdm-token`.
Never expose token values in logs, arguments or JSON; doctor reports names and
status only. Credentials do not follow cross-host redirects.

## CLI limits

The CLI is the single trust boundary for agent input: require HTTPS and public
hosts; reject loopback, private, link-local, `.local`, `.internal` and single-label
hosts. Require `CAEDM IKEv2 VPN` for publisher/API/repository access. Its existing
NetworkManager connection may be activated and checked automatically; do not
rotate or reconfigure networks, discover public IPs, or change browser identity.
Crossref and Unpaywall metadata do not require the VPN.

A process lock serializes acquisition. Persist pacing, daily counts and
cooldowns in `~/.local/state/cse-zotero/acquire.json`; unreadable state refuses
remote access. Space browser visits by at least 60 seconds per publisher/host,
with a 25-attempt daily publisher cap. CLI API/OA requests are sequential, at
most one per second globally and one per 10 seconds for Wiley. A stop marked
`cooldown` records 24 hours for the publisher and responding host. Do not clear
state to evade it. If the CLI dies mid-job, its cooldown is not recorded.

## Everyday-Chrome Connector

An agent job is a native Connector click in a normal, unfocused window, with
one marker tab and one active paper tab. The worker polls every 20 seconds and
runs one job for at most three minutes. It skips blank/loading tabs and waits
for the complete page's URL to stay unchanged for three seconds before saving.
No translator produces a clear handoff; a multiple-item page is refused.
Otherwise call native `saveWithTranslator(tab, 0)`, capture its save session,
and wait for that tab's `progressWindow.done` before closing the window.

Only main-frame 429, `cf-mitigated: challenge`, or titles matching “just a
moment”, “checking your browser”, “verify you are human” or “captcha” trigger
the page-check wait. Allow 15 seconds to clear without interaction; if it
persists, close the window, hand back the link and record the cooldown.

For agent tabs, the Connector's human-check window prompt and `openWindow`
create no window: stop with a handoff and cooldown. The CLI sends one
`notify-send` notification when available: “<publisher> needs you to save this
paper; link in the agent's result”. Never click, solve, reload or retry a check.
Ordinary tabs keep native popup behavior. Agent tab IDs remain marked for
60 seconds after the job ends; later native work is left to the Connector.

Everything else in the Connector stays native, including retries, hidden
iframes, the Amazon path and Zotero desktop's attachment resolver. Subresources
and extension background requests are not policed or attributed to the job.
There is no separate login-wall detector or five-minute human-check wait.
The worker never raises or focuses a window.

The plugin channel has only submit, pickup, finish and status, with queued,
running and done states. A running job past its deadline becomes done with an
error. Worker startup closes windows whose first tab carries its marker.
Finalization merges the fresh parent into the CLI's existing parent when that
parent is alive, then erases the fresh duplicate. A missing or trashed existing
parent leaves the fresh item intact. A session without a parent hands off; a
DOI mismatch is refused. Return the surviving item/PDF keys and file the parent
in the requested collection; the CLI verifies them through Zotero's local API.

One quiet time window suppresses Zoplicate creation handling, Linter add hooks,
Actions & Tags events and Attanger's added-item queue. It lasts until the
Connector job deadline plus 30 seconds, or through metadata/PDF import plus
30 seconds. The user's own saves during that window also skip these add-ons.
Wrappers are installed once at startup and restored at shutdown.

Build the agent copy with `agent-heavy uv run python scripts/build_connector.py`.
Follow README's one-time unpacked-extension setup and keep the official copy
disabled. Official application files stay unchanged. The plugin reads the
installed build revision; the idle worker reloads once per newer revision.
`cse-zotero doctor --json` reports readiness and any persistent mismatch.
