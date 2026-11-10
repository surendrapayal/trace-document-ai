"""
TRACE Pipeline — Full contract processing pipeline.

Pipeline starts from a GCS URI (PDF already uploaded to raw zone).
For uploading a local PDF first, use ingestion/upload_handler.py separately.

Usage:
    python -m trace_ai.pipeline --gcs-uri gs://trace-raw/contracts/CNT-XXX/contract.pdf --contract-id CNT-XXX

    # Or upload + process in one call:
    python -m trace_ai.pipeline --local-pdf /path/to/contract.pdf
"""

import argparse
import json
import sys

from trace_ai.common.logging_client import log
from trace_ai.extraction.document_ai_client import process_document
from trace_ai.extraction.dlp_client import mask_pii
from trace_ai.intelligence.rag_client import query as rag_query
from trace_ai.intelligence.gemini_client import extract_all
from trace_ai.normalization.normalizer import normalize
from trace_ai.validation.llm_judge_client import evaluate
from trace_ai.validation.confidence_scorer import route
from trace_ai.delivery.gcs_writer import write as gcs_write
from trace_ai.delivery.storage_backend import upsert_contract, write_audit_event


def run(gcs_uri: str, contract_id: str) -> dict:
    log("pipeline", contract_id, "Pipeline started", gcs_uri=gcs_uri)

    # ── Stage 1: Document AI OCR ──────────────────────────────────────────────
    write_audit_event(contract_id, "extraction", "document_ai_started")
    extraction_result = process_document(gcs_uri, contract_id)
    write_audit_event(contract_id, "extraction", "document_ai_complete", {
        "page_count": extraction_result.page_count
    })

    # ── Stage 2: DLP PII Masking ──────────────────────────────────────────────
    write_audit_event(contract_id, "extraction", "dlp_started")
    masked_text, pii_types = mask_pii(extraction_result.full_text, contract_id)
    write_audit_event(contract_id, "extraction", "dlp_complete", {"pii_types": pii_types})

    # ── Stage 3: RAG Context Retrieval ────────────────────────────────────────
    write_audit_event(contract_id, "intelligence", "rag_query_started")
    rag_context = rag_query(masked_text, contract_id)
    write_audit_event(contract_id, "intelligence", "rag_query_complete")

    # ── Stage 4: Gemini Extraction ────────────────────────────────────────────
    write_audit_event(contract_id, "intelligence", "gemini_extraction_started")
    raw_extracted = extract_all(masked_text, rag_context, contract_id)
    write_audit_event(contract_id, "intelligence", "gemini_extraction_complete")

    # ── Stage 5: Normalization ────────────────────────────────────────────────
    write_audit_event(contract_id, "normalization", "normalization_started")
    raw_extracted["contract_id"] = contract_id
    contract_record = normalize(raw_extracted, contract_id)
    write_audit_event(contract_id, "normalization", "normalization_complete")

    # ── Stage 6: LLM Judge Validation ────────────────────────────────────────
    write_audit_event(contract_id, "validation", "llm_judge_started")
    validation_result = evaluate(
        contract_text=masked_text,
        extracted_json=contract_record.model_dump_json(),
        contract_id=contract_id,
    )
    extraction_status = route(validation_result, contract_id)
    write_audit_event(contract_id, "validation", "llm_judge_complete", {
        "confidence_score": validation_result.overall_confidence,
        "verdict": extraction_status,
        "issues": validation_result.issues,
        "critical_failures": validation_result.critical_failures,
    })

    contract_record.confidence_score = validation_result.overall_confidence
    contract_record.extraction_status = extraction_status

    # ── Stage 7: Delivery ─────────────────────────────────────────────────────
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

    upsert_contract(contract_record, curated_uri)

    result = {
        "contract_id": contract_id,
        "extraction_status": extraction_status,
        "confidence_score": validation_result.overall_confidence,
        "curated_gcs_uri": curated_uri,
        "issues": validation_result.issues,
    }

    log("pipeline", contract_id, "Pipeline complete", **result)
    return result


def main():
    parser = argparse.ArgumentParser(description="TRACE Contract Processing Pipeline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--gcs-uri", help="GCS URI of PDF already in raw bucket")
    group.add_argument("--local-pdf", help="Local PDF path — uploads to GCS raw then processes")
    parser.add_argument("--contract-id", help="Contract ID (auto-generated if not provided)")
    args = parser.parse_args()

    if args.local_pdf:
        from trace_ai.ingestion.upload_handler import upload_contract
        upload_result = upload_contract(args.local_pdf, args.contract_id)
        gcs_uri = upload_result["gcs_uri"]
        contract_id = upload_result["contract_id"]
    else:
        gcs_uri = args.gcs_uri
        if not args.contract_id:
            print("--contract-id is required when using --gcs-uri", file=sys.stderr)
            sys.exit(1)
        contract_id = args.contract_id

    result = run(gcs_uri, contract_id)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
