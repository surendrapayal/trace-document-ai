"""
TRACE Pipeline — Full contract processing pipeline.

Pipeline starts from a GCS URI (PDF already uploaded to raw zone).
For uploading a local PDF first, use ingestion/upload_handler.py separately.

Full pipeline usage:
    python -m trace_ai.pipeline --gcs-uri gs://trace-raw/contracts/CNT-XXX/contract.pdf --contract-id CNT-XXX
    python -m trace_ai.pipeline --local-pdf /path/to/contract.pdf

Individual stage usage:
    python -m trace_ai.pipeline --stage ocr       --gcs-uri gs://... --contract-id CNT-XXX --output stage1.json
    python -m trace_ai.pipeline --stage dlp       --contract-id CNT-XXX --input stage1.json --output stage2.json
    python -m trace_ai.pipeline --stage rag       --contract-id CNT-XXX --input stage2.json --output stage3.json
    python -m trace_ai.pipeline --stage extract   --contract-id CNT-XXX --input stage2.json --rag-input stage3.json --output stage4.json
    python -m trace_ai.pipeline --stage normalize --contract-id CNT-XXX --input stage4.json --output stage5.json
    python -m trace_ai.pipeline --stage judge     --contract-id CNT-XXX --input stage5.json --masked-text-input stage2.json --output stage6.json
    python -m trace_ai.pipeline --stage deliver   --contract-id CNT-XXX --input stage5.json --judge-input stage6.json
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
from trace_ai.normalization.schema import ContractRecord
from trace_ai.validation.llm_judge_client import evaluate
from trace_ai.validation.confidence_scorer import route
from trace_ai.delivery.gcs_writer import write as gcs_write
from trace_ai.delivery.storage_backend import upsert_contract, write_audit_event


# ── Individual stage functions ────────────────────────────────────────────────

def run_ocr(gcs_uri: str, contract_id: str) -> dict:
    write_audit_event(contract_id, "extraction", "document_ai_started")
    result = process_document(gcs_uri, contract_id)
    write_audit_event(contract_id, "extraction", "document_ai_complete", {"page_count": result.page_count})
    return {
        "full_text": result.full_text,
        "key_value_pairs": [kv.model_dump() for kv in result.key_value_pairs],
        "tables": [t.model_dump() for t in result.tables],
        "page_count": result.page_count,
    }


def run_dlp(full_text: str, contract_id: str) -> dict:
    write_audit_event(contract_id, "extraction", "dlp_started")
    masked_text, pii_types = mask_pii(full_text, contract_id)
    write_audit_event(contract_id, "extraction", "dlp_complete", {"pii_types": pii_types})
    return {"masked_text": masked_text, "pii_types": pii_types}


def run_rag(masked_text: str, contract_id: str) -> dict:
    write_audit_event(contract_id, "intelligence", "rag_query_started")
    rag_context = rag_query(masked_text, contract_id)
    write_audit_event(contract_id, "intelligence", "rag_query_complete")
    return {"rag_context": rag_context}


def run_extract(masked_text: str, rag_context: str, contract_id: str) -> dict:
    write_audit_event(contract_id, "intelligence", "gemini_extraction_started")
    raw_extracted = extract_all(masked_text, rag_context, contract_id)
    write_audit_event(contract_id, "intelligence", "gemini_extraction_complete")
    return raw_extracted


def run_normalize(raw_extracted: dict, contract_id: str) -> dict:
    write_audit_event(contract_id, "normalization", "normalization_started")
    raw_extracted["contract_id"] = contract_id
    contract_record = normalize(raw_extracted, contract_id)
    write_audit_event(contract_id, "normalization", "normalization_complete")
    return json.loads(contract_record.model_dump_json())


def run_judge(masked_text: str, contract_record_dict: dict, contract_id: str) -> dict:
    write_audit_event(contract_id, "validation", "llm_judge_started")
    contract_record = ContractRecord(**contract_record_dict)
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
    return {
        "overall_confidence": validation_result.overall_confidence,
        "verdict": extraction_status,
        "field_scores": validation_result.field_scores.model_dump(),
        "issues": validation_result.issues,
        "critical_failures": validation_result.critical_failures,
    }


def run_deliver(contract_record_dict: dict, judge_result: dict, contract_id: str) -> dict:
    contract_record = ContractRecord(**contract_record_dict)
    extraction_status = judge_result["verdict"]
    contract_record.confidence_score = judge_result["overall_confidence"]
    contract_record.extraction_status = extraction_status

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

    return {
        "contract_id": contract_id,
        "extraction_status": extraction_status,
        "confidence_score": judge_result["overall_confidence"],
        "curated_gcs_uri": curated_uri,
        "issues": judge_result["issues"],
    }


# ── Full pipeline ─────────────────────────────────────────────────────────────

def run(gcs_uri: str, contract_id: str) -> dict:
    log("pipeline", contract_id, "Pipeline started", gcs_uri=gcs_uri)

    ocr_result = run_ocr(gcs_uri, contract_id)
    dlp_result = run_dlp(ocr_result["full_text"], contract_id)
    rag_result = run_rag(dlp_result["masked_text"], contract_id)
    extract_result = run_extract(dlp_result["masked_text"], rag_result["rag_context"], contract_id)
    normalize_result = run_normalize(extract_result, contract_id)
    judge_result = run_judge(dlp_result["masked_text"], normalize_result, contract_id)
    result = run_deliver(normalize_result, judge_result, contract_id)

    log("pipeline", contract_id, "Pipeline complete", **result)
    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

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


def main():
    parser = argparse.ArgumentParser(description="TRACE Contract Processing Pipeline")

    source = parser.add_mutually_exclusive_group()
    source.add_argument("--gcs-uri", help="GCS URI of PDF already in raw bucket")
    source.add_argument("--local-pdf", help="Local PDF path — uploads to GCS raw then processes")

    parser.add_argument("--contract-id", help="Contract ID (auto-generated if not provided)")
    parser.add_argument("--stage", choices=["ocr", "dlp", "rag", "extract", "normalize", "judge", "deliver"],
                        help="Run a single stage instead of the full pipeline")
    parser.add_argument("--input", dest="input_file", help="Path to JSON output from the previous stage")
    parser.add_argument("--rag-input", dest="rag_input_file", help="Path to RAG stage JSON output (required for --stage extract)")
    parser.add_argument("--masked-text-input", dest="masked_text_input_file", help="Path to DLP stage JSON output (required for --stage judge)")
    parser.add_argument("--judge-input", dest="judge_input_file", help="Path to judge stage JSON output (required for --stage deliver)")
    parser.add_argument("--output", dest="output_file", help="Path to write stage output JSON (prints to stdout if omitted)")

    args = parser.parse_args()

    # ── Resolve contract_id and gcs_uri ──
    contract_id = args.contract_id
    gcs_uri = args.gcs_uri

    if args.local_pdf:
        from trace_ai.ingestion.upload_handler import upload_contract
        upload_result = upload_contract(args.local_pdf, contract_id)
        gcs_uri = upload_result["gcs_uri"]
        contract_id = upload_result["contract_id"]

    if not args.stage:
        # Full pipeline
        if not gcs_uri:
            print("--gcs-uri or --local-pdf is required for full pipeline", file=sys.stderr)
            sys.exit(1)
        if not contract_id:
            print("--contract-id is required when using --gcs-uri", file=sys.stderr)
            sys.exit(1)
        result = run(gcs_uri, contract_id)
        print(json.dumps(result, indent=2))
        return

    # ── Individual stages ──
    if not contract_id:
        print("--contract-id is required for individual stages", file=sys.stderr)
        sys.exit(1)

    if args.stage == "ocr":
        if not gcs_uri:
            print("--gcs-uri or --local-pdf is required for --stage ocr", file=sys.stderr)
            sys.exit(1)
        _write(run_ocr(gcs_uri, contract_id), args.output_file)

    elif args.stage == "dlp":
        if not args.input_file:
            print("--input (OCR stage output) is required for --stage dlp", file=sys.stderr)
            sys.exit(1)
        _write(run_dlp(_read(args.input_file)["full_text"], contract_id), args.output_file)

    elif args.stage == "rag":
        if not args.input_file:
            print("--input (DLP stage output) is required for --stage rag", file=sys.stderr)
            sys.exit(1)
        _write(run_rag(_read(args.input_file)["masked_text"], contract_id), args.output_file)

    elif args.stage == "extract":
        if not args.input_file or not args.rag_input_file:
            print("--input (DLP stage output) and --rag-input (RAG stage output) are required for --stage extract", file=sys.stderr)
            sys.exit(1)
        masked_text = _read(args.input_file)["masked_text"]
        rag_context = _read(args.rag_input_file)["rag_context"]
        _write(run_extract(masked_text, rag_context, contract_id), args.output_file)

    elif args.stage == "normalize":
        if not args.input_file:
            print("--input (extract stage output) is required for --stage normalize", file=sys.stderr)
            sys.exit(1)
        _write(run_normalize(_read(args.input_file), contract_id), args.output_file)

    elif args.stage == "judge":
        if not args.input_file or not args.masked_text_input_file:
            print("--input (normalize stage output) and --masked-text-input (DLP stage output) are required for --stage judge", file=sys.stderr)
            sys.exit(1)
        masked_text = _read(args.masked_text_input_file)["masked_text"]
        _write(run_judge(masked_text, _read(args.input_file), contract_id), args.output_file)

    elif args.stage == "deliver":
        if not args.input_file or not args.judge_input_file:
            print("--input (normalize stage output) and --judge-input (judge stage output) are required for --stage deliver", file=sys.stderr)
            sys.exit(1)
        _write(run_deliver(_read(args.input_file), _read(args.judge_input_file), contract_id), args.output_file)


if __name__ == "__main__":
    main()
