---
name: mathpix
description: Use when extracting a PDF or image attachment is likely to be better as Markdown or Mathpix Markdown than raw text extraction, especially scientific articles, equations, tables, figures, scanned pages, screenshots, or Zotero PDF attachments.
---

# Mathpix

This is the repository-local copy of the Mathpix workflow used by
CSE Zotero. It is based on the local Scientific-Codex-Skills Mathpix skill.

Use the official Mathpix `mpx` CLI through the signed-in Snip account to
convert difficult PDFs or images into Markdown-like companion files only when
an authoritative companion does not already exist. Prefer this workflow when
equations, tables, figures, scanned text, or article structure matter.

## Non-negotiable Zotero companion gate

For a PDF that came from Zotero, conversion is a last resort. Before invoking
the wrapper:

1. Identify the Zotero parent and PDF attachment.
2. Run the Zotero helper's `children PARENT --json` command and inspect all
   child attachments.
3. For every `.md` or `.mmd` child, resolve its path with
   `attachment-path ATTACHMENTKEY` and use that existing file. If a repository
   copy is needed, copy it byte-for-byte into the evidence bundle and record
   the child attachment key and hash.
4. Invoke Mathpix only after confirming that no usable Markdown companion
   exists.

The child filename need not match the PDF filename, and Zotero may store the
child in a different storage directory. Therefore, a same-stem check beside
the PDF is useful but is not a substitute for inspecting Zotero children.
Never convert a PDF merely because the PDF is present or because a repository
copy is desired. The wrapper enforces this policy with
`--confirmed-no-companion`. `--force-reconvert` is an exceptional escape hatch
for an explicitly requested comparison or re-OCR, not routine ingestion.

## Fast start

Run the wrapper from the repository root or any other directory:

```bash
python .agent/skills/mathpix/scripts/convert_with_mpx.py \
  "/absolute/path/article.pdf" \
  --out "wiki/evidence/ITEMKEY/article.mmd" \
  --confirmed-no-companion
```

The wrapper supports `.mmd` (preferred for Mathpix equations) and `.md`:

```bash
python .agent/skills/mathpix/scripts/convert_with_mpx.py \
  "/absolute/path/article.pdf" \
  --out "wiki/evidence/ITEMKEY/article.md" \
  --format md \
  --confirmed-no-companion
```

It refuses to run when `MATHPIX_OCR_API_KEY` is configured, because that can
route the conversion through OCR API-key billing. It requires the Snip-token
configuration established by `mpx login`:

- `MATHPIX_SNIP_AUTH_TOKEN`
- `MATHPIX_SNIP_PRICING_AGREE`

Do not edit Mathpix auth files manually or print their values. If auth is
missing, run `mpx login` in a real terminal.

## Zotero workflow

1. Search Zotero and identify the parent item and PDF attachment key.
2. List the parent's children and resolve any Markdown companion path with the
   Zotero helper before considering conversion.
3. Use or copy an existing `.md`/`.mmd` child exactly. Do not convert that PDF.
4. If no usable companion exists, resolve the PDF path and run this wrapper
   with `--confirmed-no-companion` into `wiki/evidence/<ZOTERO_KEY>/`.
5. Inspect the beginning of newly converted output and search it for equations, tables,
   figure captions, and limitations.
6. Record the parent Zotero key, attachment key, source format, and output
   path in an evidence README or manifest.

The source PDF and Zotero database remain immutable. Creating a repository
companion file does not attach it back into Zotero. Making the companion a
visible Zotero child attachment is a separate, explicit Zotero write action.

## Agent reading rules

- Read the whole converted article when making a paper-level synthesis; chunk
  long documents without silently skipping sections.
- Preserve exact quotes and page/section locations for claims.
- Treat Mathpix output as source transcription, not as proof that OCR or
  equation parsing is perfect.
- Keep figures and remote Mathpix image references attributable to the source;
  download local copies only when a reproducible artifact requires them.
- Report absolute input/output paths and whether the Snip-token route was used.

## Commands

```bash
# Mathpix Markdown companion (only after the Zotero companion gate)
python .agent/skills/mathpix/scripts/convert_with_mpx.py \
  "/path/to/paper.pdf" --out "wiki/evidence/ITEMKEY/paper.mmd" \
  --confirmed-no-companion

# Standard Markdown extension, retaining Mathpix-compatible math syntax
python .agent/skills/mathpix/scripts/convert_with_mpx.py \
  "/path/to/paper.pdf" --out "wiki/evidence/ITEMKEY/paper.md" --format md \
  --confirmed-no-companion
```
