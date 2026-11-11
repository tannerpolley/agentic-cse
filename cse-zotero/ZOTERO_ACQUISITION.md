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
ignoring trash. An existing PDF returns its keys only after the shared
verification below. Other library writes keep their existing previews and
approvals.

## Routes

Try Unpaywall's declared open-access PDF locations, PMC Cloud, an official
Elsevier/Wiley API when configured, then the everyday-Chrome Connector. The
first verified PDF wins; an incomplete acquisition hands back the DOI or
article link.
DOI metadata uses Zotero's Crossref translator. If lookup fails (including a DOI
registered outside Crossref), return the translator reason and DOI link for a
landing-page handoff through web translators. Do not invent PDF URLs.

Unattended acquisition works for open access and official APIs with working
tokens and entitlement. Springer is verified through the Connector. Elsevier,
Wiley, AIP and ACS web routes commonly need a human. The current Elsevier key is
refused for Article Retrieval (support ticket **261006-005015**); the Wiley token
is not yet configured. Elsevier's explicit key-configuration error skips that
API; challenge responses and 429 still stop acquisition.

PMC uses its official Cloud dataset and metadata-declared PDF, with the ID
Converter as a fallback. Do not fetch PMC web PDF links or legacy OA packages.
Elsevier/Wiley/ACS direct OA downloads require a declared repository location,
excluding their publisher/CDN hosts.

All routes and existing attachments share one completeness check: require a
`%PDF` prefix, at most 50 MiB, and a readable page count using Poppler's
`pdfinfo` (required on the CLI host). Reject a PDF with fewer than half the
pages in a numeric Crossref page range (falling back to Zotero's pages), or a
single page unless the range explicitly describes a one-page article. Article
numbers are not page ranges. Rejected downloads fall through with the reason;
a rejected native Connector save hands off without reporting verified success
or deleting its attachment. Native Connector downloads stay native. Without a
usable range, multiple pages alone cannot prove completeness.

Elsevier requests explicitly use `view=FULL`; the [Article Retrieval docs](https://dev.elsevier.com/documentation/ArticleRetrievalAPI.wadl)
list response formats and view selection but no PDF coverage response header.
The shared page check therefore remains necessary.

`acquire --refetch` previews recovery for confirmed truncation only; uncertain
existing attachments hand off for inspection and are never removed. Explicit
single-page ranges such as `123-123` or `S10-S10` are usable; lone numbers and
article numbers cannot establish a one-page paper. The shared verifier uses
Zotero pages when Crossref has no usable range.

The preview makes no acquisition or attachment writes. Review the returned parent, old
attachment keys, failure reasons and `preview_sha256`, then obtain owner
approval before running the same command with `--apply --preview-sha256 <digest>`.
The digest binds the old files, page range, collection and route; changes require
a fresh preview. The new attachment is saved and verified before the old PDFs
are removed. Acquisition or verification failure retains the old attachments. A complete existing PDF is
reused even with `--refetch`.

Replacement is supported only through the CLI. The add-on replacement endpoint
is an internal operation, not an independently approved write interface: it
checks parent/attachment relationships, while the CLI owns the approved preview
digest, old-file hash checks and completeness verification. No constant token
provides approval. Connector sessions with several fresh PDFs hand off without
selecting one or removing an existing attachment.

Tokens live in mode-0600 files under `~/.config/zotero-companion/`:
`elsevier-api-key`, optional `elsevier-insttoken`, and `wiley-tdm-token`.
Never expose token values in logs, arguments or JSON; doctor reports names and
status only. Credentials do not follow cross-host redirects.

## CLI limits

The CLI is the single trust boundary for agent input: require HTTPS and public
hosts; reject loopback, private, link-local, `.local`, `.internal` and single-label
hosts. The optional setting in `~/.config/zotero-companion/config.toml` is:

```toml
[acquisition]
vpn_connection = "Your NetworkManager connection name"
```

When configured, require that connection for non-public publisher/API/repository
access except Wiley, which needs it off for institutional login. If it is
active, hand back the Wiley link without a browser attempt or disconnecting it.
The existing NetworkManager connection may be activated and checked automatically;
do not rotate or reconfigure networks, discover public IPs, or change browser
identity. Public metadata requests do not require the VPN.

When the setting is absent, acquisition never calls NetworkManager or requires
a VPN. Users without institutional access can acquire verified open-access
copies and use APIs for which they have valid tokens and entitlement. Removing
the setting grants no subscription access: restricted papers still need an
entitled institutional login or return a link for handoff. Publisher route
restrictions, challenge refusals, completeness checks and pacing still apply.

A process lock serializes acquisition. Persist pacing, daily counts and the
last stop reason in `~/.local/state/cse-zotero/acquire.json`; unreadable state
refuses remote access. Space browser visits by at least 60 seconds per publisher/host,
with a 25-attempt daily publisher cap. CLI API/OA requests are sequential, at
most one per second globally and one per 10 seconds for Wiley. A stop ends
only the current paper; the next paper keeps the 60-second spacing and no
publisher is put on hold.

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
the page-check wait. A 429 stops at once. A check page waits until the job
deadline, so it can clear by itself or the user can clear it in the agent
window; if it persists, close the window and hand back the link. The agent never
clicks, solves, reloads or retries a check itself.

The Connector's own human-check pop-up and `openWindow` stay native for agent
tabs, so a PDF behind a check (ScienceDirect, for example) still downloads.
Agent saves keep only the PDF: the page snapshot is skipped. A stop hands back
the link in the result, with no desktop notification. Agent tab IDs remain marked for
60 seconds after the job ends; later native work is left to the Connector.

Everything else in the Connector stays native, including retries, hidden
iframes, the Amazon path and Zotero desktop's attachment resolver. Subresources
and extension background requests are not policed or attributed to the job.
There is no separate login-wall detector or five-minute human-check wait.
The worker's own window is never raised or focused. The Connector's native
check pop-up does open in front, and it may outlive the job by up to its own
60-second wait. The agent copy adds Chrome's
`background` permission to remain available with no windows, and its startup
event wakes the worker. Keep Chrome background apps enabled. The CLI starts
everyday Chrome without a startup window when needed and waits for readiness
before submitting a paper; an idle `doctor` status is not an acquisition veto.

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

Build the agent copy with `nice -n 10 uv run python scripts/build_connector.py`.
Follow README's one-time unpacked-extension setup and keep the official copy
disabled. Official application files stay unchanged. The plugin reads the
installed build revision; the idle worker reloads once per newer revision.
`cse-zotero doctor --json` reports readiness and any persistent mismatch.
