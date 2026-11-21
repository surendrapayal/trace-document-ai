# TRACE Platform — Knowledge Base Setup Guide

This document explains what the RAG Knowledge Base is, why it exists, what files need to be
created, who creates them, and how to upload and index them.

---

## What is the Knowledge Base?

The Knowledge Base (KB) is a collection of plain text reference documents that describe
Heartland's contract structure, pricing models, fee names, and merchant types. These documents
are uploaded to GCS, chunked, embedded, and indexed into Vertex AI Vector Search.

At pipeline runtime (Stage 3 — RAG Retrieval), the contract text is used to query the KB and
retrieve the most relevant chunks. Those chunks are passed to Gemini in Stage 4 alongside the
contract text, grounding the extraction in known Heartland-specific rules.

**Without the KB, Gemini extracts fields from the contract text alone — with no domain context.
With the KB, Gemini knows exactly how Heartland labels fields, what values are valid, and how
to distinguish IC++ from Flat Rate contracts.**

---

## Why is it Needed?

Gemini is a general-purpose LLM. It has no built-in knowledge of:

- How Heartland structures their 4-page contract format
- That `"Interchange Plus"` in the pricing section means `IC++` billing model
- That `"Monthly 5 bps"` means IC++ settlement and `"Monthly 0 bps"` means Flat Rate
- That `"Service/Mandate Fee"` should be normalized to `"Service Fee"`
- That a single `"Discount Rate"` column means IC++ while two columns (`Discount CP` / `Discount CNP`) means Flat Rate

The KB teaches Gemini these rules. Every time a contract is processed, the 5 most relevant KB
chunks are retrieved and injected into each of the 7 Gemini extraction prompts as context.

---

## Who Creates These Files?

These are **not extracted from contract PDFs**. They are **manually authored reference documents**
written by people who understand Heartland's contract format and business rules.

| Role | Responsibility |
|---|---|
| Business / Domain Expert | Writes the content — knows Heartland contract structure, pricing rules, fee names |
| Operations / Contract Specialist | Reviews and validates accuracy against real contracts |
| Developer | Formats as `.txt`, uploads to GCS, runs the indexer |

For this POC, all 4 files are already authored and available in `RAG_KNOWLEDGE_BASE.md`.
They were derived from two real Heartland contracts: `CHETSHOESLLC.pdf` (IC++ contract) and
`FITCHBURG HISTORICAL SOCIETY.pdf` (Flat Rate contract).

---

## How Many Files and What Types?

**4 files total** for the Heartland POC. All are plain `.txt` files.

| # | File Name | Type | What it Contains |
|---|---|---|---|
| 1 | `heartland_playbook.txt` | Contract structure guide | Page layout, section locations, field names, IC++ vs Flat Rate identification rules, all column names in pricing and fee tables |
| 2 | `heartland_fee_dictionary.txt` | Fee name mapping | Canonical mappings from Heartland's printed fee labels to normalized names used in the schema |
| 3 | `heartland_pricing_models.txt` | Pricing model reference | Detailed explanation of IC++ and Flat Rate models with real contract examples, identification rules, and who each model suits |
| 4 | `heartland_merchant_types.txt` | Merchant type reference | Ownership types, new/existing business values, length-in-business values, business category examples |

---

## File Details

### File 1 — `heartland_playbook.txt`

**Purpose**: Master reference for Heartland's contract structure. Tells Gemini where every
field lives on the page and how to read the pricing section.

**Key content**:
- 4-page contract layout (what is on each page)
- Header field definitions: MID, atlas Token, SDR, Affiliate ID
- Company Information section: two address blocks, Primary contact, HIC Admin
- Credit Card Pricing section: 5-column summary bar, pricing table columns
- IC++ identification rules: single Discount Rate column, low rates, Monthly 5 bps
- Flat Rate identification rules: two discount columns (CP/CNP), higher rates, Monthly 0 bps
- Recurring fees table: 9 standard fees in fixed order, $0.00 = waived (still extract)
- Merchant Details section: all Yes/No compliance fields
- Processing Details section: transaction method percentages (must sum to 100%)
- Document generation date format

**Who needs to update it**: When Heartland changes their contract layout or adds new sections.

---

### File 2 — `heartland_fee_dictionary.txt`

**Purpose**: Prevents fee name mismatches between what is printed on the contract and what
the schema expects. Gemini uses this to normalize fee names consistently.

**Key content**:
- 17 fee name mappings (Heartland label → canonical name)
- Notes on which fees apply to IC++ vs Flat Rate contracts
- Clarification that `Discount Rate` in IC++ = markup only, not total cost

**Who needs to update it**: When Heartland introduces new fee line items or renames existing ones.

---

### File 3 — `heartland_pricing_models.txt`

**Purpose**: Deep explanation of the two pricing models with real contract examples. Helps
Gemini correctly classify the billing model and extract rates accurately.

**Key content**:
- IC++ model: how it works, real example rates from Chet Shoes LLC, who it suits, 4 identification rules
- Flat Rate model: how it works, real example rates from Fitchburg Historical Society, who it suits, 4 identification rules

**Who needs to update it**: When new pricing models are introduced (e.g. Tiered pricing).

---

### File 4 — `heartland_merchant_types.txt`

**Purpose**: Reference for all enumerated merchant classification fields. Prevents Gemini
from inventing values that do not exist in the schema.

**Key content**:
- 5 ownership types with descriptions
- 3 new/existing business values with exact label text
- 6 length-in-business values (exact strings as printed on contract)
- Business category examples (free-text field)

**Who needs to update it**: When new merchant types or business categories are observed in contracts.

---

## Where the Content Comes From

The content for all 4 files is already written in `docs/requirement/RAG_KNOWLEDGE_BASE.md`.
Each file's content is in a fenced code block under its heading.

**To create the `.txt` files**: copy the content from each code block in `RAG_KNOWLEDGE_BASE.md`
into a separate `.txt` file with the filename shown in the heading.

---

## GCS Storage Location

All KB files are stored in the single `GCS_BUCKET` under the `kb/` prefix:

```
gs://<GCS_BUCKET>/
    kb/
        documents/                          ← upload your .txt files here
            heartland_playbook.txt
            heartland_fee_dictionary.txt
            heartland_pricing_models.txt
            heartland_merchant_types.txt
        chunks/                             ← auto-created by kb_indexer.py
            <uuid>.txt                      ← one file per chunk
            <uuid>.txt
            ...
```

---

## How to Upload and Index

**Step 1 — Create the 4 txt files** from `RAG_KNOWLEDGE_BASE.md` content.

**Step 2 — Upload to GCS:**
```bash
gsutil cp heartland_playbook.txt          gs://skumar_trace_ai/kb/documents/
gsutil cp heartland_fee_dictionary.txt    gs://skumar_trace_ai/kb/documents/
gsutil cp heartland_pricing_models.txt    gs://skumar_trace_ai/kb/documents/
gsutil cp heartland_merchant_types.txt    gs://skumar_trace_ai/kb/documents/
```

**Step 3 — Run the indexer** (requires Vector Search index to be created first via `scripts/create_index.py`):
```bash
python -m trace_ai.knowledge_base.kb_indexer
```

**What the indexer does:**
```
Each .txt file in kb/documents/
        │
        ▼
Chunk into 500-character pieces (50-char overlap between chunks)
        │
        ▼
Embed each chunk → 768-dim vector  (task_type="RETRIEVAL_DOCUMENT")
        │
        ├── Store chunk text → gs://<GCS_BUCKET>/kb/chunks/<uuid>.txt
        └── Upsert vector   → Vertex AI Vector Search index (batches of 100)
```

Expected output:
```
Indexed N chunks into Vector Search.
```

---

## How it is Used at Runtime (Stage 3)

Every time a contract is processed:

```
masked_text[:2000]  (first 2000 chars of contract)
        │
        ▼
embed_single()  →  768-dim query vector  (task_type="RETRIEVAL_QUERY")
        │
        ▼
Vector Search find_neighbors()  →  top 5 nearest chunk IDs
        │
        ▼
Download each chunk from gs://<GCS_BUCKET>/kb/chunks/<uuid>.txt
        │
        ▼
Join chunks with separator  →  rag_context string
        │
        ▼
Passed into all 7 Gemini extraction prompts in Stage 4
```

If no neighbors are found, `rag_context` is returned as `""` and the pipeline continues
without KB grounding — extraction still runs but accuracy may be lower.

---

## When to Re-index

Re-run `python -m trace_ai.knowledge_base.kb_indexer` after:

| Trigger | Action |
|---|---|
| Adding a new KB document to GCS | Re-index to include new chunks |
| Updating an existing KB document | Re-index to refresh vectors |
| Changing `VERTEX_EMBEDDING_MODEL` | Re-index all — vectors are model-specific |
| Changing `VERTEX_EMBEDDING_DIMENSIONS` | Re-index all — dimension mismatch will cause errors |
| Adding a new processor (e.g. non-Heartland) | Add new processor-specific KB docs and re-index |

---

## Expanding the KB for New Processors

This KB is Heartland-specific. If TRACE is extended to process contracts from other payment
processors (e.g. Fiserv, TSYS, Worldpay), add new `.txt` files for each processor:

```
kb/documents/
    heartland_playbook.txt          ← existing
    heartland_fee_dictionary.txt    ← existing
    heartland_pricing_models.txt    ← existing
    heartland_merchant_types.txt    ← existing
    fiserv_playbook.txt             ← new processor
    fiserv_fee_dictionary.txt       ← new processor
    ...
```

Vector Search retrieves the most semantically relevant chunks regardless of which file they
came from — the correct processor's reference material will naturally rank higher for contracts
from that processor.
