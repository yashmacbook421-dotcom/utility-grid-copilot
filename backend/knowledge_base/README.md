# Knowledge base

Real, authoritative documents for the RAG pipeline — alongside the
synthetic procedures in `../docs/procedures/`, not replacing them.

## Structure

```
knowledge_base/
├── regulations/           # FERC/regulatory reports
├── operating_procedures/  # CAISO business practice manuals
├── reliability/           # NERC reliability standards
├── forecasting/           # load/resource assessments
├── renewable_energy/      # solar/wind integration, duck-curve material
├── california/            # CPUC and other California-specific documents
├── technical_reports/     # anything else
├── uploads/                # created automatically by POST /api/ingest/pdf
├── download_manifest.py    # the list of tracked documents + where to get them
└── download_and_ingest.py  # downloads + ingests everything in the manifest
```

## Adding a document

**Option A — tracked in the manifest (recommended for anything you want
version-controlled and reproducible):**

1. Add an entry to `download_manifest.py`:
   ```python
   ManifestEntry(
       title="...",
       organization="...",       # e.g. "NERC", "CAISO", "FERC", "CPUC"
       document_type="...",      # e.g. "reliability_standard", "report"
       source_url="https://...", # must be a real, direct PDF link
       subfolder="reliability",  # one of the folders above
       filename="....pdf",
       region="California",      # optional
   )
   ```
2. **Verify the URL is real and live before adding it** — e.g.
   `curl -sI <url>` and confirm `200` + `content-type: application/pdf`.
   Don't add a document you haven't confirmed actually resolves.
3. Run:
   ```bash
   docker compose exec backend python -m knowledge_base.download_and_ingest
   ```
   No other application code changes needed — this is the whole point of
   the manifest pattern.

**Option B — ad hoc, via the API** (no manifest entry, not version-controlled):

```bash
curl -X POST http://localhost:8000/api/ingest/pdf \
  -F "file=@/path/to/document.pdf" \
  -F "title=..." \
  -F "organization=..." \
  -F "document_type=..." \
  -F "source_url=https://..."
```

Or point at a whole local folder of PDFs:

```bash
curl -X POST http://localhost:8000/api/ingest/directory \
  -H "Content-Type: application/json" \
  -d '{"directory_path": "/app/knowledge_base/some_folder", "organization": "...", "document_type": "..."}'
```

## What happens during ingestion

PDF → per-page text extraction (`pypdf`) → section-heading detection
(regex, tuned against this corpus's actual documents — see
`app/services/pdf_ingest.py`) → chunking within page boundaries (a chunk
never spans two pages, so page-number citations stay accurate) → local
embedding (`sentence-transformers`) → stored as `Document` +
`DocumentChunk` rows, with an `IngestionRun` audit row recording
success/failure either way.

Only use authoritative, publicly available sources — government agencies
(NERC, FERC, CPUC), grid operators (CAISO), or similarly official bodies.
Don't scrape arbitrary websites, and don't add a document without
confirming it's real and correctly attributed.
