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
from trace_ai.common.logging_client import log
from trace_ai.extraction.document_ai_client import process_document
from trace_ai.extraction.dlp_client import mask_pii
from trace_ai.intelligence.rag_client import query as rag_query
from trace_ai.intelligence.gemini_client import extract_all
from trace_ai.normalization.normalizer import normalize
from trace_ai.normalization.schema import ContractRecord
from trace_ai.validation.llm_judge_client import evaluate
from trace_ai.validation.confidence_scorer import route
from trace_ai.delivery.gcs_writer import write as gcs_write
from trace_ai.delivery.storage_backend import upsert_contract, write_audit_event
```
Each import brings in exactly one function from each stage module. `rag_query` is aliased to avoid collision with Python's built-in `query`. `gcs_write` is aliased to avoid collision with the built-in `write`.

---

### Stage Functions

#### `run_ocr(gcs_uri, contract_id) -> dict`

```python
def run_ocr(gcs_uri: str, contract_id: str) -> dict:
    write_audit_event(contract_id, "extraction", "document_ai_started")
```
Writes an audit event to Firestore/BigQuery before the stage begins — every stage is bookended by audit events so the full pipeline timeline is traceable.

```python
    result = process_document(gcs_uri, contract_id)
```
Calls `document_ai_client.process_document()` — downloads the PDF from GCS and submits it to Document AI. Returns an `ExtractionResult` Pydantic model.

```python
    write_audit_event(contract_id, "extraction", "document_ai_complete", {"page_count": result.page_count})
```
Writes the completion audit event, including `page_count` as metadata so you can see how many pages were processed.

```python
    return {
        "full_text": result.full_text,
        "key_value_pairs": [kv.model_dump() for kv in result.key_value_pairs],
        "tables": [t.model_dump() for t in result.tables],
        "page_count": result.page_count,
    }
```
Converts the Pydantic `ExtractionResult` to a plain dict so it can be serialized to JSON for `--output`. `model_dump()` converts each nested Pydantic model to a dict. Only `full_text` is used by downstream stages — `key_value_pairs` and `tables` are captured for completeness.

---

#### `run_dlp(full_text, contract_id) -> dict`

```python
def run_dlp(full_text: str, contract_id: str) -> dict:
    write_audit_event(contract_id, "extraction", "dlp_started")
    masked_text, pii_types = mask_pii(full_text, contract_id)
    write_audit_event(contract_id, "extraction", "dlp_complete", {"pii_types": pii_types})
    return {"masked_text": masked_text, "pii_types": pii_types}
```
Passes `full_text` from Stage 1 into `mask_pii()`. Returns two values — `masked_text` (PII replaced with mask characters) and `pii_types` (list of detected PII type names e.g. `["US_SOCIAL_SECURITY_NUMBER", "DATE_OF_BIRTH"]`). Both are stored in the output dict. `masked_text` is what every downstream stage (RAG, Gemini, LLM Judge) receives — raw PII never reaches an LLM.

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
```
Re-hydrates the `ContractRecord` and stamps it with the judge's `confidence_score` and `extraction_status` — these two fields were set to defaults (`0.0`, `"Pending"`) by the normalizer and are now overwritten with the real values.

```python
    curated_uri = None

    if extraction_status == "Approved":
        curated_uri = gcs_write(contract_record)
        write_audit_event(contract_id, "delivery", "written_to_curated", {"gcs_uri": curated_uri})
    elif extraction_status == "Review Required":
        log("pipeline", contract_id, "Routed to human review queue")
        write_audit_event(contract_id, "delivery", "routed_to_review_queue")
    elif extraction_status == "Rejected":
        log("pipeline", contract_id, "Contract rejected — manual intervention required", severity="WARNING")
        write_audit_event(contract_id, "delivery", "rejected")
```
Three routing branches. Only `"Approved"` triggers a GCS write — `curated_uri` stays `None` for the other two. Each branch writes its own audit event.

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
def run(gcs_uri: str, contract_id: str) -> dict:
    log("pipeline", contract_id, "Pipeline started", gcs_uri=gcs_uri)

    ocr_result     = run_ocr(gcs_uri, contract_id)
    dlp_result     = run_dlp(ocr_result["full_text"], contract_id)
    rag_result     = run_rag(dlp_result["masked_text"], contract_id)
    extract_result = run_extract(dlp_result["masked_text"], rag_result["rag_context"], contract_id)
    normalize_result = run_normalize(extract_result, contract_id)
    judge_result   = run_judge(dlp_result["masked_text"], normalize_result, contract_id)
    result         = run_deliver(normalize_result, judge_result, contract_id)

    log("pipeline", contract_id, "Pipeline complete", **result)
    return result
```
Calls each stage function in sequence, threading outputs into the next stage's inputs. Note that `dlp_result["masked_text"]` is passed to three separate stages — RAG (line 4), Gemini extraction (line 5), and LLM Judge (line 7). The judge needs the original masked text as the source of truth to compare against the extraction.

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
if args.local_pdf and args.stage != "ingest":
    upload_result = upload_contract(args.local_pdf, contract_id)
    gcs_uri = upload_result["gcs_uri"]
    contract_id = upload_result["contract_id"]
```
When `--local-pdf` is given for any stage other than `ingest`, the file is uploaded first and the returned `gcs_uri` and `contract_id` are used for the rest of the run. The `args.stage != "ingest"` guard prevents double-uploading — the `ingest` stage handles its own upload logic below.

```python
if not args.stage:
    # Full pipeline
    result = run(gcs_uri, contract_id)
    print(json.dumps(result, indent=2))
    return
```
If no `--stage` flag, runs the full pipeline and prints the final result.

The remaining `elif args.stage == "..."` blocks each validate their required flags (`--contract-id`, `--input`, etc.), read input files via `_read()`, call the corresponding `run_*()` function, and write output via `_write()`.

---

## 2. `upload_handler.py` — Stage 0 Ingestion

**Location**: `src/trace_ai/ingestion/upload_handler.py`
**Role**: Validates and uploads a local PDF to GCS raw zone. Generates `contract_id`.

---

```python
import os
import uuid
from pathlib import Path
from trace_ai.common.gcs_client import upload
from trace_ai.config import config
from trace_ai.common.logging_client import log

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
```
`uuid` generates the unique contract ID. `upload` is the shared GCS helper. `MAX_FILE_SIZE_BYTES` is a module-level constant — 50MB expressed as bytes via multiplication for readability.

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
    log("ingestion", contract_id, "Contract uploaded to GCS raw zone", gcs_uri=gcs_uri)
    return {"contract_id": contract_id, "gcs_uri": gcs_uri, "file_size_bytes": file_size}
```
Logs the upload with the GCS URI as structured metadata. Returns all three values the caller needs — `contract_id` to track the contract, `gcs_uri` to pass to Stage 1 OCR, `file_size_bytes` for audit purposes.

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
            log("ingestion", "batch", f"Failed to upload {pdf.name}", severity="ERROR", error=str(e))
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
from trace_ai.common.logging_client import log
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
    log("extraction", contract_id, "Submitting to Document AI", gcs_uri=gcs_uri)

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
