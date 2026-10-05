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
is refused. A duplicate returns its existing key without moving or attaching
anything. Deduplication checks DOI first, then normalized exact title.

DOIs embedded in article URLs and identifiers recognized by Zotero (DOI, ISBN,
arXiv, PMID) use Zotero's search translators. DOI translation is pinned to
Zotero's Crossref REST translator, which does not visit publisher pages.
Metadata lookups go to registries and library catalogs, not publishers, and keep Zotero's native request and retry handling within one CLI pacing slot.
URLs without a recognized identifier are unsupported and return their exact
URL for the ordinary Connector. Do not invent metadata or PDF URLs.

## Route order and publisher boundaries

Acquisition saves one translated parent without automatic translator
attachments, then tries:

1. Unpaywall's declared OA PDF locations, using
   `https://api.unpaywall.org/v2/<doi>?email=42780259+tannerpolley@users.noreply.github.com`.
2. The publisher's official API with a configured token for Elsevier or Wiley.
3. Dedicated agent Chrome for other publishers, reading only the page-declared
   `citation_pdf_url` and fetching it in page context with credentials.
4. Human handoff with the exact DOI or official article URL.

The first successful route wins. Hard stops end the acquisition immediately;
they never trigger another route. Parent metadata may remain if a PDF route
fails; output reports its key and the handoff URL. A PDF must begin with `%PDF`
and fit the 50 MiB transfer limit. Attachments are imported by the companion
plugin, then parent DOI and PDF child are verified through Zotero's local API.
JSON reports `item_key`, `attachment_key`, `collection_key`, `route`,
`verified`, `stop_reason`, and `handoff_url`; incomplete acquisition exits nonzero.

Identify restricted publishers by Crossref member and DOI prefix: Elsevier
(member 78; `10.1016`, `10.1006`), Wiley (311; `10.1002`, `10.1111`), ACS
(316; `10.1021`). Their publisher sites, including redirects and OA publisher
PDFs, are never fetched. Unpaywall locations must explicitly report
`host_type: repository` for these publishers; unknown provenance is skipped. Do not call
Zotero DOI/URL attachment resolvers for these publishers. This implementation
uses Unpaywall rather than Zotero attachment resolvers, avoiding their implicit
page requests and retries. Explicit browser routing is refused for all three.
Unknown publishers still pass host checks on every redirect.

Elsevier uses only
`https://api.elsevier.com/content/article/doi/<encoded-doi>` with
`Accept: application/pdf`, `X-ELS-APIKey`, and optional `X-ELS-Insttoken`.
Never automate ScienceDirect or other Elsevier article pages. See the official
[Article Retrieval API](https://dev.elsevier.com/documentation/ArticleRetrievalAPI.wadl),
[API authentication](https://dev.elsevier.com/tecdoc_api_authentication.html), and
[TDM license](https://www.elsevier.com/about/policies-and-standards/text-and-data-mining/license).

Wiley uses only
`https://api.wiley.com/onlinelibrary/tdm/v1/articles/<encoded-doi>` with
`Wiley-TDM-Client-Token`. Obtain a token through Wiley Online Library's account
and click-through TDM agreement; institutional entitlement requires the
institution network. Wiley publishes caps of 3 articles/second and 60 requests
per 10 minutes, and asks ongoing requests to be 10 seconds apart. The client
uses the stricter 10-second interval. See [Wiley's TDM documentation](https://onlinelibrary.wiley.com/library-info/resources/text-and-datamining).

No public ACS token API was verified. After permitted repository OA attempts,
ACS goes to human handoff. ACS says TDM is outside standard agreements and
must be negotiated into the institution's license or a separate agreement.
Ask the institution's library or ACS for the applicable permission and access
method. A Crossref PDF link is not permission or a token API. For example,
`10.1021/bi00728a004` has a `similarity-checking` link, not a `text-mining`
link. See [ACS licensing FAQ](https://solutions.acs.org/access-options/corp-gov-np/),
[ACS academic agreement](https://solutions.acs.org/wp-content/uploads/2021/04/ACS-Publications-Institutional-Access-Agreement-Academic.pdf),
and [Crossref's TDM guidance](https://www.crossref.org/documentation/retrieve-metadata/text-and-data-mining/).

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
access. Browser requests wait at least 60 seconds between requests to the
same host, including redirects and PDF fetches, and have a daily cap of 25
requests per publisher. CLI API/OA requests are sequential and at most one per
second globally, with Wiley at one per 10 seconds. Interrupted requests still
consume their recorded pacing slot. No parallel acquisition.

Publisher and PDF requests stop without retry for HTTP 401, 403, or 429, CAPTCHA, Cloudflare/“Just a
moment”, human-verification or unusual-activity pages, login walls, or
non-PDF bytes where a PDF was expected. Record the reason. A publisher 429 or
challenge adds a 24-hour publisher cooldown; acquisitions refuse that
publisher until expiry. Do not solve, bypass, probe, replay, or retry
challenges, nor attempt another route after a hard stop. Do not remove safety
state to evade cooldowns. The user can complete ordinary login or Connector
saving manually.

## Tokens and dedicated browser

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

```bash
cse-zotero agent-browser start --json
cse-zotero agent-browser status --json
cse-zotero agent-browser stop --json
cse-zotero acquire <permitted-OA-doi> --collection <key> --route browser --json
```

Chrome uses `~/.local/share/cse/zotero/agent-chrome`, loopback remote debugging,
and native headless mode to avoid creating or focusing desktop windows. It
uses no stealth flags, spoofed user agent, or webdriver hiding. It starts only
on explicit `agent-browser start`, not during acquisition. Navigation and PDF
requests are intercepted for VPN, host restrictions, pacing, status, and
challenge checks. Unneeded page resources are blocked; browser fallback may
therefore be unsupported on pages requiring scripts. It never activates a tab.
`--route browser` skips OA/API solely to exercise a permitted single-paper
browser route; duplicate checks and every safeguard remain active.

For a one-time manual sign-in, stop agent Chrome, then the user can launch:

```bash
google-chrome --user-data-dir="$HOME/.local/share/cse/zotero/agent-chrome" --no-first-run
```

After the user closes that window, restart agent Chrome. Agents do not launch
that visible window, click, type, or control the user's ordinary browser.

## Retention boundary

Zotero attachments and project-selected data authorities remain external,
user-owned state. Git commits do not back them up. Corpus refresh does not
promote summaries or claims; retain exact source locators and the project's
chosen recovery policy.
