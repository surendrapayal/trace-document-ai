# TRACE — Pipeline Code Walkthrough

Line-by-line explanation of every pipeline stage module.

---

## Table of Contents

1. [pipeline.py — Orchestrator](#1-pipelinepy--orchestrator)
2. [upload_handler.py — Stage 0 Ingestion](#2-upload_handlerpy--stage-0-ingestion)
3. [document_ai_client.py — Stage 1 OCR](#3-document_ai_clientpy--stage-1-ocr)
4. [dlp_client.py — Stage 2 DLP PII Masking](#4-dlp_clientpy--stage-2-dlp-pii-masking)
5. [rag_client.py — Stage 3 RAG Retrieval](#5-rag_clientpy--stage-3-rag-retrieval)
6. [gemini_client.py — Stage 4 Gemini Extraction](#6-gemini_clientpy--stage-4-gemini-extraction)
7. [normalizer.py — Stage 5 Normalization](#7-normalizerpy--stage-5-normalization)
8. [llm_judge_client.py — Stage 6 LLM Judge](#8-llm_judge_clientpy--stage-6-llm-judge)
9. [confidence_scorer.py — Stage 6 Confidence Routing](#9-confidence_scorerpy--stage-6-confidence-routing)
10. [gcs_writer.py — Stage 7 Delivery](#10-gcs_writerpy--stage-7-delivery)
11. [storage_backend.py — Stage 7 Operational Store](#11-storage_backendpy--stage-7-operational-store)

---

## 1. `pipeline.py` — Orchestrator

**Location**: `src/trace_ai/pipeline.py`
**Role**: Wires all 7 stages together. Also the CLI entry point.

---

### Imports

```python
import argparse
import json
import sys
```
Standard library — `argparse` parses CLI flags, `json` serializes/deserializes stage outputs, `sys` is used to write errors to stderr and exit.

```python
from trace_ai.common.logger import log, set_context, clear_context
from trace_ai.extraction.document_ai_client import process_document_cached
from trace_ai.extraction.dlp_client import mask_pii_cached
from trace_ai.intelligence.rag_client import query as rag_query
from trace_ai.intelligence.gemini_client import extract_all
from trace_ai.normalization.normalizer import normalize
from trace_ai.normalization.schema import ContractRecord
from trace_ai.validation.llm_judge_client import evaluate
from trace_ai.validation.confidence_scorer import route
from trace_ai.delivery.gcs_writer import write as gcs_write
from trace_ai.delivery.storage_backend import upsert_contract, write_audit_event
```
Each import brings in exactly one function from each stage module. `rag_query` is aliased to avoid collision with Python's built-in `query`. `gcs_write` is aliased to avoid collision with the built-in `write`. `process_document_cached` and `mask_pii_cached` are the caching wrappers — they check GCS before calling the APIs.

---

### Stage Functions

#### `run_ocr(gcs_uri, contract_id) -> dict`

```python
def run_ocr(gcs_uri: str, contract_id: str) -> dict:
    write_audit_event(contract_id, "extraction", "document_ai_started")
```
Writes an audit event to Firestore/BigQuery before the stage begins — every stage is bookended by audit events so the full pipeline timeline is traceable.

```python
    result, cache_hit = process_document_cached(gcs_uri, contract_id)
```
Calls `process_document_cached()` which first checks whether `processing/contracts/<contract_id>/ocr.json` already exists in GCS. If it does, the result is loaded from GCS and Document AI is not called. If not, Document AI is called and the result is written to GCS for future reuse. Returns `(ExtractionResult, cache_hit: bool)`.

```python
    write_audit_event(contract_id, "extraction", "document_ai_complete", {
        "page_count": result.page_count,
        "cache_hit": cache_hit,
    })
```
Writes the completion audit event including `page_count` and `cache_hit` — so the audit trail shows whether Document AI was actually called or the cached result was used.

```python
    return {
        "full_text": result.full_text,
        "key_value_pairs": [kv.model_dump() for kv in result.key_value_pairs],
        "tables": [t.model_dump() for t in result.tables],
        "page_count": result.page_count,
    }
```
Converts the Pydantic `ExtractionResult` to a plain dict so it can be serialized to JSON for `--output`. Only `full_text` is used by downstream stages.

---

#### `run_dlp(full_text, contract_id) -> dict`

```python
def run_dlp(full_text: str, contract_id: str) -> dict:
    write_audit_event(contract_id, "extraction", "dlp_started")
    (masked_text, pii_types), cache_hit = mask_pii_cached(full_text, contract_id)
    write_audit_event(contract_id, "extraction", "dlp_complete", {
        "pii_types": pii_types,
        "cache_hit": cache_hit,
    })
    return {"masked_text": masked_text, "pii_types": pii_types}
```
`mask_pii_cached()` first checks whether `processing/contracts/<contract_id>/masked.json` already exists in GCS. If it does, the masked text and PII types are loaded from GCS and Cloud DLP is not called. If not, DLP is called and the result is written to GCS. Returns `((masked_text, pii_types), cache_hit: bool)`. The `cache_hit` flag is recorded in the audit event. `masked_text` is what every downstream stage (RAG, Gemini, LLM Judge) receives — raw PII never reaches an LLM. The `masked.json` file in GCS is also a durable compliance artifact proving PII was removed before any LLM call.

---

#### `run_rag(masked_text, contract_id) -> dict`

```python
def run_rag(masked_text: str, contract_id: str) -> dict:
    write_audit_event(contract_id, "intelligence", "rag_query_started")
    rag_context = rag_query(masked_text, contract_id)
    write_audit_event(contract_id, "intelligence", "rag_query_complete")
    return {"rag_context": rag_context}
```
Passes `masked_text` to `rag_client.query()` which embeds the text, queries Vector Search, and fetches matching KB chunks. Returns `rag_context` — a single string of concatenated knowledge base chunks that will be injected into every Gemini prompt.

---

#### `run_extract(masked_text, rag_context, contract_id) -> dict`

```python
def run_extract(masked_text: str, rag_context: str, contract_id: str) -> dict:
    write_audit_event(contract_id, "intelligence", "gemini_extraction_started")
    raw_extracted = extract_all(masked_text, rag_context, contract_id)
    write_audit_event(contract_id, "intelligence", "gemini_extraction_complete")
    return raw_extracted
```
Passes both `masked_text` and `rag_context` to `gemini_client.extract_all()` which runs 7 sequential Gemini prompt calls. Returns `raw_extracted` — a dict with 7 keys, one per contract section. This dict is returned directly as the stage output.

---

#### `run_normalize(raw_extracted, contract_id) -> dict`

```python
def run_normalize(raw_extracted: dict, contract_id: str) -> dict:
    write_audit_event(contract_id, "normalization", "normalization_started")
    raw_extracted["contract_id"] = contract_id
```
Injects `contract_id` into the raw dict before passing to the normalizer — the normalizer needs it to construct the `ContractRecord`.

```python
    contract_record = normalize(raw_extracted, contract_id)
    write_audit_event(contract_id, "normalization", "normalization_complete")
    return json.loads(contract_record.model_dump_json())
```
`normalize()` maps the raw Gemini dict to a fully-typed `ContractRecord` Pydantic model. `model_dump_json()` serializes it to a JSON string, then `json.loads()` converts it back to a plain dict — this round-trip ensures all Pydantic types (enums, datetimes) are serialized to their string representations before being passed between stages.

---

#### `run_judge(masked_text, contract_record_dict, contract_id) -> dict`

```python
def run_judge(masked_text: str, contract_record_dict: dict, contract_id: str) -> dict:
    write_audit_event(contract_id, "validation", "llm_judge_started")
    contract_record = ContractRecord(**contract_record_dict)
```
Re-hydrates the plain dict back into a typed `ContractRecord` Pydantic model — needed because `evaluate()` calls `model_dump_json()` on it.

```python
    validation_result = evaluate(
        contract_text=masked_text,
        extracted_json=contract_record.model_dump_json(),
        contract_id=contract_id,
    )
```
Calls `llm_judge_client.evaluate()` with the masked contract text (source of truth) and the extracted JSON (what was extracted). Gemini reads both side-by-side and scores the extraction quality.

```python
    extraction_status = route(validation_result, contract_id)
```
Calls `confidence_scorer.route()` which applies threshold logic to `validation_result.overall_confidence` and returns one of `"Approved"`, `"Review Required"`, or `"Rejected"`.

```python
    write_audit_event(contract_id, "validation", "llm_judge_complete", {
        "confidence_score": validation_result.overall_confidence,
        "verdict": extraction_status,
        "issues": validation_result.issues,
        "critical_failures": validation_result.critical_failures,
    })
    return {
        "overall_confidence": validation_result.overall_confidence,
        "verdict": extraction_status,
        "field_scores": validation_result.field_scores.model_dump(),
        "issues": validation_result.issues,
        "critical_failures": validation_result.critical_failures,
    }
```
Audit event captures the full judge result. Return dict includes per-section `field_scores` (serialized via `model_dump()`), the list of `issues` (non-critical discrepancies), and `critical_failures` (fields that failed completely).

---

#### `run_deliver(contract_record_dict, judge_result, contract_id) -> dict`

```python
def run_deliver(contract_record_dict: dict, judge_result: dict, contract_id: str) -> dict:
    contract_record = ContractRecord(**contract_record_dict)
    extraction_status = judge_result["verdict"]
    contract_record.confidence_score = judge_result["overall_confidence"]
    contract_record.extraction_status = extraction_status
    contract_record.field_scores = judge_result["field_scores"]
    contract_record.judge_issues = judge_result["issues"]
```
Re-hydrates the `ContractRecord` from the plain dict. Stamps it with four fields from the judge result:
- `confidence_score` -- the overall 0.0-1.0 score
- `extraction_status` -- Approved, Review Required, or Rejected
- `field_scores` -- per-section scores dict e.g. `{"credit_card_pricing": 0.54, ...}`. Stored as JSON in Firestore/BigQuery and surfaced in review.html as section-level score badges
- `judge_issues` -- list of specific discrepancies flagged by the judge. Displayed at the top of review.html so reviewers know exactly what to fix

```python
    curated_uri = None

    if extraction_status == ExtractionStatus.APPROVED:
        curated_uri = gcs_write(contract_record)
        write_audit_event(contract_id, "delivery", "written_to_curated", {"gcs_uri": curated_uri})
    elif extraction_status == ExtractionStatus.REVIEW_REQUIRED:
        log("Routed to human review queue", severity="WARNING")
        write_audit_event(contract_id, "delivery", "routed_to_review_queue")
    elif extraction_status == ExtractionStatus.REJECTED:
        log("Contract rejected -- manual intervention required", severity="ERROR")
        write_audit_event(contract_id, "delivery", "rejected")
```
Note the severity levels: `REVIEW_REQUIRED` uses `WARNING` and `REJECTED` uses `ERROR`.
Three routing branches. Only `APPROVED` triggers a GCS write -- `curated_uri` stays `None` for the other two. Each branch writes its own audit event.

```python
    upsert_contract(contract_record, curated_uri)
```
Called for ALL statuses — every contract is written to the operational store (Firestore or BigQuery) regardless of outcome. This is what populates the review queue for `"Review Required"` contracts.

```python
    return {
        "contract_id": contract_id,
        "extraction_status": extraction_status,
        "confidence_score": judge_result["overall_confidence"],
        "curated_gcs_uri": curated_uri,
        "issues": judge_result["issues"],
    }
```
Final pipeline output. `curated_gcs_uri` is `None` for non-approved contracts.

---

### Full Pipeline `run()`

```python
def run(gcs_uri: str, contract_id: str, file_hash: str | None = None) -> dict:
    import uuid
    set_context(contract_id=contract_id, request_id=uuid.uuid4().hex[:8].upper(), stage="pipeline")
    log("Pipeline started", gcs_uri=gcs_uri)

    try:
        ocr_result       = run_ocr(gcs_uri, contract_id)
        dlp_result       = run_dlp(ocr_result["full_text"], contract_id)
        rag_result       = run_rag(dlp_result["masked_text"], contract_id)
        extract_result   = run_extract(dlp_result["masked_text"], rag_result["rag_context"], contract_id)
        normalize_result = run_normalize(extract_result, contract_id)
        if file_hash:
            normalize_result["file_hash"] = file_hash
        normalize_result["source_pdf_uri"] = gcs_uri
        normalize_result["page_count"] = ocr_result["page_count"]
        judge_result     = run_judge(dlp_result["masked_text"], normalize_result, contract_id)
        result           = run_deliver(normalize_result, judge_result, contract_id)
    except Exception as e:
        log("Pipeline failed", severity="ERROR", error=str(e))
        raise
    finally:
        clear_context()

    set_context(stage="pipeline")
    log("Pipeline complete", **result)
    return result
```
Three changes vs the stage functions above:

- `file_hash: str | None = None` — optional third parameter. When a local PDF was uploaded, `upload_contract()` returns the hash and `main()` passes it here. For `--gcs-uri` runs the hash is `None` (bytes not available locally).
- `set_context(contract_id=..., request_id=...)` — stamps every log line in this pipeline run with the contract ID and a short random request ID for traceability across stages.
- `if file_hash: normalize_result["file_hash"] = file_hash` — injects the hash into the normalize stage output dict before it is passed to `run_judge()` and `run_deliver()`. This is how `file_hash` ends up on the `ContractRecord` and gets persisted to Firestore/BigQuery.
- `try/except/finally` — catches any stage failure, logs it with `severity="ERROR"`, re-raises so the caller sees the exception, and always calls `clear_context()` to reset the MDC logger state.

Note that `dlp_result["masked_text"]` is passed to three separate stages — RAG, Gemini extraction, and LLM Judge. The judge needs the original masked text as the source of truth to compare against the extraction.

---

### CLI Helpers

```python
def _read(path: str) -> dict:
    with open(path) as f:
        return json.load(f)

def _write(data: dict, path: str | None) -> None:
    out = json.dumps(data, indent=2)
    if path:
        with open(path, "w") as f:
            f.write(out)
    else:
        print(out)
```
`_read()` loads a JSON file from disk — used to read `--input` files between individual stage runs. `_write()` writes stage output to `--output` file if provided, otherwise prints to stdout. Both are used only in the CLI path, not in the full `run()` pipeline.

---

### `main()` — CLI Entry Point

```python
parser = argparse.ArgumentParser(description="TRACE Contract Processing Pipeline")

source = parser.add_mutually_exclusive_group()
source.add_argument("--gcs-uri", ...)
source.add_argument("--local-pdf", ...)
```
`--gcs-uri` and `--local-pdf` are mutually exclusive — you can only provide one. This is enforced by argparse at parse time.

```python
parser.add_argument("--stage", choices=["ingest","ocr","dlp","rag","extract","normalize","judge","deliver"], ...)
```
`--stage` restricts input to the 8 valid stage names. If omitted, the full pipeline runs.

```python
# GCS folder — run full pipeline for every PDF under the prefix
if args.gcs_uri and args.gcs_uri.endswith("/") and not args.stage:
    from trace_ai.common.gcs_client import list_blobs
    uri = args.gcs_uri[len("gs://"):]
    bucket_name, prefix = uri.split("/", 1)
    blobs = [b for b in list_blobs(bucket_name, prefix) if b.endswith(".pdf")]
    ...
    for blob in sorted(blobs):
        cid = f"CNT-{uuid.uuid4().hex[:12].upper()}"
        result = run(f"gs://{bucket_name}/{blob}", cid, None)
```
GCS folder support — a trailing `/` on `--gcs-uri` signals a folder run. `list_blobs()` lists all blobs under the prefix, filtered to `.pdf` only. Each blob gets a fresh `uuid4` contract ID. `file_hash` is `None` for GCS folder runs — the PDF bytes are not downloaded locally so no hash is computed.

```python
if args.local_pdf and args.stage != "ingest":
    if os.path.isdir(args.local_pdf):
        # Folder — run full pipeline for every PDF sequentially
        for pdf in sorted(Path(args.local_pdf).glob("*.pdf")):
            upload_result = upload_contract(str(pdf))
            result = run(upload_result["gcs_uri"], upload_result["contract_id"], upload_result.get("file_hash"))
            ...
    upload_result = upload_contract(args.local_pdf, contract_id)
    gcs_uri = upload_result["gcs_uri"]
    contract_id = upload_result["contract_id"]
    file_hash = upload_result.get("file_hash")
```
Local folder support — `os.path.isdir()` detects a folder path. Each PDF is uploaded individually via `upload_contract()` (which includes hash computation and duplicate check), then the full pipeline runs for each. `upload_result.get("file_hash")` passes the hash into `run()` so it is stored on the `ContractRecord`. The `args.stage != "ingest"` guard prevents double-uploading — the `ingest` stage handles its own upload logic separately.

```python
if not args.stage:
    result = run(gcs_uri, contract_id, file_hash)
    print(json.dumps(result, indent=2))
    return
```
If no `--stage` flag, runs the full pipeline passing `file_hash` through. Prints the final result as JSON.

The remaining `elif args.stage == "..."` blocks each validate their required flags (`--contract-id`, `--input`, etc.), read input files via `_read()`, call the corresponding `run_*()` function, and write output via `_write()`.

---

## 2. `upload_handler.py` — Stage 0 Ingestion

**Location**: `src/trace_ai/ingestion/upload_handler.py`
**Role**: Validates and uploads a local PDF to GCS raw zone. Generates `contract_id`.

---

```python
import hashlib
import os
import uuid
from pathlib import Path
from trace_ai.common.gcs_client import upload
from trace_ai.config import config
from trace_ai.common.logger import log
```
`hashlib` computes the SHA256 file hash for duplicate detection. `uuid` generates the unique contract ID. `upload` is the shared GCS helper. File size limit is read from `config.MAX_FILE_SIZE_BYTES` (default 50 MB, configurable via `MAX_FILE_SIZE_BYTES` env var in MB).

---

### `_compute_hash(local_path) -> str`

```python
def _compute_hash(local_path: str) -> str:
    h = hashlib.sha256()
    with open(local_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
```
Computes a SHA256 hash of the PDF bytes in 64KB streaming chunks — memory usage stays flat regardless of file size. The two-argument `iter()` calls the lambda repeatedly until it returns `b""` (EOF). Returns a 64-character lowercase hex string e.g. `a3f9b2c1d4e5...`. Used for duplicate detection.

---

### `upload_contract(local_path, contract_id) -> dict`

```python
def upload_contract(local_path: str, contract_id: str | None = None) -> dict:
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"File not found: {local_path}")
```
First guard — fails fast if the file doesn't exist before any GCP calls are made.

```python
    if not local_path.lower().endswith(".pdf"):
        raise ValueError(f"Only PDF files are supported. Got: {local_path}")
```
Second guard — enforces PDF-only. `.lower()` makes the check case-insensitive so `.PDF` also passes.

```python
    file_size = os.path.getsize(local_path)
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File exceeds 50MB limit: {file_size} bytes")
```
Third guard — checks file size before uploading. Avoids wasting bandwidth on oversized files.

```python
    file_hash = _compute_hash(local_path)

    if config.DUPLICATE_CHECK_ENABLED:
        from trace_ai.delivery.storage_backend import get_contract_by_hash
        existing = get_contract_by_hash(file_hash)
        if existing:
            raise ValueError(
                f"Duplicate contract detected — already processed as {existing['contract_id']} "
                f"(status: {existing.get('extraction_status', 'unknown')}). "
                f"Set DUPLICATE_CHECK_ENABLED=false to reprocess."
            )
```
Computes the SHA256 hash then checks for duplicates when `DUPLICATE_CHECK_ENABLED=true` (default). The import of `get_contract_by_hash` is deferred inside the `if` block — avoids importing the storage backend when duplicate checking is disabled. If a match is found, raises `ValueError` with the existing `contract_id` and status so the caller knows exactly which contract already processed this file.

```python
    if not contract_id:
        contract_id = f"CNT-{uuid.uuid4().hex[:12].upper()}"
```
Auto-generates a contract ID if one wasn't provided. `uuid4()` generates a random UUID, `.hex` strips the dashes to get a 32-char hex string, `[:12]` takes the first 12 characters, `.upper()` makes it uppercase. Result: `CNT-A3F9B2C1D4E5`.

```python
    blob_name = f"{config.GCS_RAW_PREFIX}/contracts/{contract_id}/{os.path.basename(local_path)}"
    gcs_uri = upload(local_path, config.GCS_BUCKET, blob_name)
```
Constructs the GCS blob path: `raw/contracts/CNT-XXX/contract.pdf`. `os.path.basename()` extracts just the filename from the full local path. `upload()` performs the actual GCS upload and returns the full `gs://` URI.

```python
    log("Contract uploaded to GCS raw zone", gcs_uri=gcs_uri, file_size_bytes=file_size, file_hash=file_hash)
    return {"contract_id": contract_id, "gcs_uri": gcs_uri, "file_size_bytes": file_size, "file_hash": file_hash}
```
Logs the upload with `file_hash` as structured metadata. Returns four values — `contract_id`, `gcs_uri`, `file_size_bytes`, and `file_hash`. The `file_hash` is passed through `pipeline.run()` and injected into `normalize_result` so it is stored on the `ContractRecord` and persisted to Firestore/BigQuery.

---

### `upload_contracts_from_folder(folder_path) -> list[dict]`

```python
def upload_contracts_from_folder(folder_path: str) -> list[dict]:
    path = Path(folder_path)
    if not path.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder_path}")
```
Uses `pathlib.Path` for cleaner directory operations. Fails fast if the path isn't a directory.

```python
    pdf_files = sorted(path.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in: {folder_path}")
```
`glob("*.pdf")` finds all PDF files in the folder (non-recursive). `sorted()` ensures deterministic processing order. Raises if no PDFs found.

```python
    results = []
    for pdf in pdf_files:
        try:
            result = upload_contract(str(pdf))
            results.append(result)
        except Exception as e:
            log(f"Failed to upload {pdf.name}", severity="ERROR", error=str(e))
            results.append({"file": pdf.name, "error": str(e)})
```
Processes each PDF independently. If one fails, the error is logged and appended to results as `{"file": ..., "error": ...}` — the loop continues rather than aborting the entire batch. This means a partial batch upload is possible and each file's outcome is visible in the output.

---

## 3. `document_ai_client.py` — Stage 1 OCR

**Location**: `src/trace_ai/extraction/document_ai_client.py`
**Role**: Downloads PDF from GCS, submits to Document AI Form Parser, extracts text, key-value pairs, and tables.

---

```python
from google.cloud import documentai
from trace_ai.config import config
from trace_ai.common.gcs_client import download_bytes
from trace_ai.common.logger import log
from trace_ai.extraction.extraction_models import ExtractionResult, KeyValuePair, ExtractedTable
```
`documentai` is the Google Cloud Document AI client library. `download_bytes` fetches raw bytes from GCS. `ExtractionResult`, `KeyValuePair`, `ExtractedTable` are the Pydantic output models defined in `extraction_models.py`.

---

### `_get_client() -> DocumentProcessorServiceClient`

```python
def _get_client() -> documentai.DocumentProcessorServiceClient:
    opts = {"api_endpoint": f"{config.DOCUMENT_AI_LOCATION}-documentai.googleapis.com"}
    return documentai.DocumentProcessorServiceClient(client_options=opts)
```
Document AI uses a regional endpoint — the client must be pointed at the correct region. `config.DOCUMENT_AI_LOCATION` is `"us"` (short format, not `us-central1`). This builds the endpoint URL as `us-documentai.googleapis.com`. A new client is created on each call — Document AI clients are lightweight and stateless.

---

### `_processor_name() -> str`

```python
def _processor_name() -> str:
    return (
        f"projects/{config.GCP_PROJECT_ID}"
        f"/locations/{config.DOCUMENT_AI_LOCATION}"
        f"/processors/{config.DOCUMENT_AI_FORM_PROCESSOR_ID}"
    )
```
Builds the fully-qualified Document AI processor resource name that the API requires. Format: `projects/<id>/locations/us/processors/<processor_id>`. The processor ID comes from the GCP console where the Form Parser was created manually.

---

### `_extract_text_from_layout(document, layout) -> str`

```python
def _extract_text_from_layout(document: documentai.Document, layout) -> str:
    text = ""
    for segment in layout.text_anchor.text_segments:
        start = int(segment.start_index)
        end = int(segment.end_index)
        text += document.text[start:end]
    return text.strip()
```
Document AI stores all text in a single `document.text` string. Individual fields and cells don't contain their own text — instead they hold `text_anchor.text_segments` which are `(start_index, end_index)` pointers into the master text string. This function resolves those pointers by slicing `document.text`. Multiple segments are concatenated (handles multi-line fields). `.strip()` removes leading/trailing whitespace.

---

### `process_document(gcs_uri, contract_id) -> ExtractionResult`

```python
def process_document(gcs_uri: str, contract_id: str) -> ExtractionResult:
    log("Submitting to Document AI", gcs_uri=gcs_uri)

    bucket_name = gcs_uri.replace("gs://", "").split("/")[0]
    blob_name = "/".join(gcs_uri.replace("gs://", "").split("/")[1:])
    pdf_bytes = download_bytes(bucket_name, blob_name)
```
Parses the GCS URI to extract bucket name and blob path. `replace("gs://", "")` strips the scheme, `split("/")[0]` gets the bucket, `split("/")[1:]` gets all path segments which are re-joined with `/`. Then downloads the raw PDF bytes from GCS.

```python
    client = _get_client()
    raw_document = documentai.RawDocument(content=pdf_bytes, mime_type="application/pdf")
    process_options = documentai.ProcessOptions(
        ocr_config=documentai.OcrConfig(enable_native_pdf_parsing=True)
    )
```
`RawDocument` wraps the PDF bytes with its MIME type. `enable_native_pdf_parsing=True` tells Document AI to use the embedded text layer for digital PDFs instead of running OCR — this gives higher accuracy for digital PDFs. For scanned PDFs with no text layer, it automatically falls back to OCR.

```python
    request = documentai.ProcessRequest(
        name=_processor_name(),
        raw_document=raw_document,
        process_options=process_options,
    )
    result = client.process_document(request=request)
    document = result.document
```
Builds and submits the processing request. `result.document` is the Document AI `Document` proto containing all extracted content.

```python
    key_value_pairs = []
    for page in document.pages:
        for field in page.form_fields:
            key_text = _extract_text_from_layout(document, field.field_name)
            value_text = _extract_text_from_layout(document, field.field_value)
            if key_text:
                key_value_pairs.append(
                    KeyValuePair(key=key_text, value=value_text, confidence=field.field_value.confidence)
                )
```
Iterates every page, then every form field on that page. `field.field_name` and `field.field_value` are layout objects — `_extract_text_from_layout()` resolves them to strings. `if key_text` skips empty keys. `confidence` comes from the field value's confidence score (0.0–1.0).

```python
    tables: list[ExtractedTable] = []
    for page in document.pages:
        for table in page.tables:
            headers = []
            if table.header_rows:
                for cell in table.header_rows[0].cells:
                    headers.append(_extract_text_from_layout(document, cell.layout))
            rows = []
            for body_row in table.body_rows:
                row = [_extract_text_from_layout(document, cell.layout) for cell in body_row.cells]
                rows.append(row)
            tables.append(ExtractedTable(headers=headers, rows=rows))
```
Iterates every table on every page. `header_rows[0]` takes only the first header row (most tables have one). Each cell's layout is resolved to text. Body rows are extracted as lists of strings. Each table becomes an `ExtractedTable(headers=[...], rows=[[...], [...]])`.

```python
    return ExtractionResult(
        full_text=document.text,
        key_value_pairs=key_value_pairs,
        tables=tables,
        page_count=len(document.pages),
    )
```
`document.text` is the complete OCR'd text of the entire document — all pages concatenated. This is the primary output used by all downstream stages.

---
