---
name: wicked-garden-mem-ingest
description: "Ingest source files into the wicked-estate knowledge store as cited chunks. Chunk text files deterministically, send binary documents (pdf, doc/docx, ppt/pptx, xls/xlsx, odt/odp/ods, rtf, epub) by path for estate conversion, and read images with vision. Report estate refusals with their reason. Use when: dispatched by the wicked-garden-mem skill's ingest action, or directly for 'ingest this file', 'add this document to the knowledge base', 'index this directory', 'learn from this pdf'."
metadata:
  role: worker
---

# Mem Ingest Worker

This skill is designed to run as an isolated worker; when your harness cannot fork, run it inline and keep its output separate from the caller's.

You ingest source files into the **wicked-estate knowledge store** so later
`knowledge.recall` / cited-answer calls can return them with `source`
citations. This ports the brain-era ingest pipeline (FOLD-2, Phase 5-S7)
onto estate: **you** chunk text and read images; the **engine** converts
binary documents, redacts, chunks at H1/H2 headings, writes, and ranks
(`knowledge.ingest` / `knowledge.write` — deterministic, never calls a model). Estate's embedded
method card `skill://knowledge-ingest/SKILL.md` is the chunking doctrine
this pipeline follows.

## Runtime
Script-backed steps use the `wicked-garden` launcher: `wicked-garden run <plugin-root-relative path, e.g. scripts/…> [args]`. It is on PATH after `npm i -g wicked-garden`; otherwise use `npx wicked-garden run …`; inside a wicked-crew run it is `"$WICKED_GARDEN_ROOT/scripts/wicked-garden"`.
If none of these is available, or Python 3 is missing, skip the script-backed step, say so, and follow the manual alternative where one is given next to it — never invent the script's output.
Relative paths in this skill are relative to the directory that contains this SKILL.md.

## Parameters

- **source** (required): path to a file or directory
- **scope** (optional): estate scope, default `project:<cwd-basename>`
- **title** (optional): document title, default derived from the filename

## The write seam

All writes go through the mem backend (stdio shim → estate MCP):

```bash
wicked-garden run \
  scripts/mem/estate_memory.py ingest -
```

with a JSON body on stdin (chunks are long — never inline them in argv).
Send exactly one of `chunks` or `path`, together with a `title`:

```json
{"title": "<doc title>", "chunks": ["<chunk 1>", "<chunk 2>"],
 "scope": "<scope>", "source": "<absolute-or-repo-relative source path>"}
```

Rules that make chunks worth storing:

- **Self-contained** — one idea per chunk (a section, a slide, a sheet, a
  table row group). Recall returns chunks verbatim; a fragment that needs
  its neighbours is a bad chunk.
- **Source provenance always** — `source` is what a cited answer cites. An
  uncited chunk cannot back `wicked-garden-search answer`. Supply it for
  chunks; path ingest defaults `source` to the document's path when omitted.
- For a single standalone fact, use the `write` action instead
  (`{"content": ..., "class": "concept", "source": ...}`).

## Step 1 — assess the source

- Single file → Step 2 (text) or Step 3 (binary) by extension.
- Directory → Step 4 (batch).
- Health check when in doubt: `... estate_memory.py health '{}'` — on
  `"ok": false`, stop and report the degrade (estate binary missing or
  store unreachable). Do not fake success.

Text extensions: `.md .txt .csv .html .htm .json .py .js .jsx .ts .tsx .sh
.rs .go .java .yaml .yml .toml`. Binary document extensions: `.pdf .doc
.docx .ppt .pptx .xls .xlsx .odt .odp .ods .rtf .epub`.
Image extensions (vision): `.png .jpg .jpeg .gif .webp`.

## Step 2 — TEXT files (deterministic chunking)

1. Read the file.
2. Split:
   - **Markdown**: on H1/H2 headings; sub-split any section over ~800 words
     at paragraph breaks.
   - **Code**: one chunk per file (small files) or per top-level
     class/function group; prepend a one-line `path — what it is` header so
     the chunk stands alone.
   - **CSV/other text**: paragraph groups of ~800 words; for CSV keep the
     header row with every chunk.
3. Send title + chunks + scope + source through the write seam (one `ingest`
   call per file).

## Step 3 — binary documents and images

For a binary document, send one path ingest through the same write seam:

```json
{"title": "<doc title>", "path": "<document path>",
 "scope": "<scope>", "source": "<citation path>"}
```

The path must be inside the directory the backend runs in: run the backend
from the document's directory or a parent, and resolve relative paths from
that cwd. Estate converts the document in-process. If estate refuses it
(for example, a scanned PDF `needs OCR`, a missing file, or a secret-file
rule), report it as **not ingested** with estate's reason. Do not
automatically convert it elsewhere or retry through vision.

For images only, examine the image with vision and write one chunk
describing its visual content plus any legible text verbatim. Preserve
numbers, names, and tables exactly. Send chunks through the Step-2 seam,
with `source` set to the original image's path.

## Step 4 — directories (batch)

Do NOT ingest files one-by-one in conversation. Write a small Python batch
script to the session scratch dir that walks the tree (skip dotdirs,
`node_modules`, `__pycache__`, lockfiles), applies the Step-2 chunking to
each text file, and sends each convertible binary document as one `{path}`
ingest from Step 3. Pipe one JSON body per file into
`wicked-garden run scripts/mem/estate_memory.py ingest -`, with the backend's
cwd set to the directory being walked (or a parent). Run the batch script
with `python3 <script> || python <script>`, then:

- Report successful files, returned doc_ids, and chunk counts where returned.
- Report each refused file as not ingested, with estate's reason.
- List only images for vision ingest (Step 3), or hand that list back for
  the caller to choose.

## Step 5 — verify (seeded recall)

Pick 1–2 distinctive phrases from the ingested content and confirm they
come back cited:

```bash
wicked-garden run \
  scripts/mem/estate_memory.py sources '{"query":"<distinctive phrase>"}'
```

The matching chunk must appear with the right `source`. If it doesn't,
say so — never report an unverified ingest as done.

## Step 6 — report

- `{N} files ingested, scope {scope}`; chunk counts where returned
- doc_ids returned by the backend
- refused files and estate's reasons; images pending vision ingest (if deferred)
- verification: which seeded phrases came back, with their `source`
