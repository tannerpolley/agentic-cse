# Zotero acquisition and external discovery

Read this contract when an agent may use an external literature-discovery
service, open a publisher page, acquire a remote paper, or save a paper through
Zotero Connector. Zotero remains the bibliographic and document authority;
external services are discovery aids.

The institution permits AI-assisted research use. That context does not waive
article licenses, institutional access conditions, publisher rate limits,
no-scraping terms, or security controls.

## External discovery

Use CSE Zotero and the live Zotero library first. Commission external
discovery only after naming a literature gap that retained evidence does not
answer.

When Undermind is available, reuse an applicable workspace and completed search
before creating another. Use targeted semantic or citation search for bounded
questions and deep search when broader coverage would resolve the named gap.
Creating or reorganizing workspaces, folders, files, stars, or uploads is an
external mutation and requires user authorization.

Transfer candidates by DOI, or by exact title and creators when no DOI exists.
Undermind cite keys are workspace-local and are not Zotero identities. Deduplicate
every candidate against the live Zotero library before proposing acquisition.

Undermind metadata, search summaries, and PDF-agent responses are screening
material. Promote a claim only from Zotero-retained evidence with exact source
locators. Reading an Undermind-held open-access PDF does not add it to Zotero;
uploading a local or Zotero PDF to Undermind is a separate external write.

## Acquisition sequence

1. Read the repository `AGENTS.md` and the canonical Zotero skill when it is
   installed.
2. Search the live Zotero library and deduplicate by DOI, title, and creators.
3. Confirm the institutional VPN is active before publisher access or a Zotero
   Connector save. Use the Zotero workflow's status check when available; if it
   is unavailable or returns `unknown`, ask the user to confirm. Stop when the
   VPN is inactive or unconfirmed. Never start, stop, reconfigure, rotate, or
   chain VPNs or proxies, and never discover or report a public IP address.
4. Select one route:

   - **Human-operated Connector handoff:** prepare a small list, normally one to
     five exact DOI or official article URLs. The user opens each link in their
     ordinary Chrome session, clicks Zotero Connector, chooses the collection,
     and confirms the attachment.
   - **Metadata-only import:** use an authoritative DOI metadata source or
     user-provided RIS/BibTeX only when a supported local import capability is
     currently available. Report `no PDF attachment`; do not script a substitute
     when the capability is absent.
   - **Local-file attachment:** attach only a user-supplied local file, after a
     separate native write approval. This route does not contact a publisher.

5. Report every candidate's title, creators, DOI or official URL, duplicate
   status, proposed attachment, and suggested collection. If the current target
   cannot be read, say so and let the user choose it in Zotero Connector.
6. Immediately before a library write, use native `request_user_input`. For the
   human Connector route use exactly:

   - `Approve; I will save the listed papers in Zotero (Recommended)`
   - `Stop; do not save`

   For a supported metadata-only import use exactly:

   - `Approve; import metadata via local Connector (Recommended)`
   - `Stop; do not import`

7. After Connector approval, the user performs the browser and Connector steps.
   The agent does not open, claim, focus, click, or automate publisher tabs and
   does not poll while the user works. Then use exactly:

   - `Done; verify Zotero (Recommended)`
   - `Stop; do not verify`

8. Verify each approved parent through the local Zotero interface by exact DOI
   or title, then inspect collection membership, children, and the approved local
   attachment path. Do not move an item when the user chose another collection.
9. Preview any CSE Zotero wiki refresh separately. Apply it only after a distinct
   approval; refreshes do not promote summaries or scientific claims.

## Hard stops

Stop and report the exact blocker for CAPTCHA, Cloudflare or automated-access
checks, HTTP 403/429, login walls, access denial, or unusual-activity messages.
The user may complete an ordinary access step manually. The agent does not solve,
bypass, probe, replay, instrument, or automatically retry a challenge.

Publisher pages are never accessed through DevTools, browser console, CDP,
altered headers or scripts, challenge tokens, stealth settings, proxy rotation,
IP rotation, headless scraping, guessed PDF URLs, crawling, or rapid parallel
requests. DevTools are limited to explicit read-only diagnosis of the local
Zotero/Connector integration.

For more than occasional individual papers, use the publisher's approved API or
text-and-data-mining access and license. Keep credentials and downloaded corpora
private and follow their sharing and retention terms.
