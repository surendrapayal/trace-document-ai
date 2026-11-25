import io
import json
from google.cloud import documentai
from pypdf import PdfReader, PdfWriter
from trace_ai.config import config
from trace_ai.common.gcs_client import download_bytes, upload_json, blob_exists, download_json
from trace_ai.common.logger import log
from trace_ai.extraction.extraction_models import ExtractionResult, KeyValuePair, ExtractedTable

_PAGE_CHUNK_SIZE = 15


def _get_client() -> documentai.DocumentProcessorServiceClient:
    opts = {"api_endpoint": f"{config.DOCUMENT_AI_LOCATION}-documentai.googleapis.com"}
    return documentai.DocumentProcessorServiceClient(client_options=opts)


def _processor_name() -> str:
    return (
        f"projects/{config.GCP_PROJECT_ID}"
        f"/locations/{config.DOCUMENT_AI_LOCATION}"
        f"/processors/{config.DOCUMENT_AI_FORM_PROCESSOR_ID}"
    )


def _split_pdf(pdf_bytes: bytes) -> list[bytes]:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    chunks = []
    for start in range(0, len(reader.pages), _PAGE_CHUNK_SIZE):
        writer = PdfWriter()
        for page in reader.pages[start:start + _PAGE_CHUNK_SIZE]:
            writer.add_page(page)
        buf = io.BytesIO()
        writer.write(buf)
        chunks.append(buf.getvalue())
    return chunks


def _extract_text_from_layout(document: documentai.Document, layout) -> str:
    text = ""
    for segment in layout.text_anchor.text_segments:
        start = int(segment.start_index)
        end = int(segment.end_index)
        text += document.text[start:end]
    return text.strip()


def _process_chunk(client, chunk_bytes: bytes) -> documentai.Document:
    raw_document = documentai.RawDocument(content=chunk_bytes, mime_type="application/pdf")
    process_options = documentai.ProcessOptions(
        ocr_config=documentai.OcrConfig(
            enable_native_pdf_parsing=True,
            enable_image_quality_scores=True,
        )
    )
    request = documentai.ProcessRequest(
        name=_processor_name(),
        raw_document=raw_document,
        process_options=process_options,
    )
    return client.process_document(request=request).document


def _parse_document(document: documentai.Document) -> tuple[list[KeyValuePair], list[ExtractedTable]]:
    key_value_pairs = []
    for page in document.pages:
        for field in page.form_fields:
            key_text = _extract_text_from_layout(document, field.field_name)
            value_text = _extract_text_from_layout(document, field.field_value)
            if key_text:
                key_value_pairs.append(
                    KeyValuePair(
                        key=key_text,
                        value=value_text,
                        confidence=field.field_value.confidence,
                    )
                )
    tables = []
    for page in document.pages:
        for table in page.tables:
            headers = []
            if table.header_rows:
                for cell in table.header_rows[0].cells:
                    headers.append(_extract_text_from_layout(document, cell.layout))
            rows = [
                [_extract_text_from_layout(document, cell.layout) for cell in body_row.cells]
                for body_row in table.body_rows
            ]
            tables.append(ExtractedTable(headers=headers, rows=rows))
    return key_value_pairs, tables


def process_document(gcs_uri: str, contract_id: str) -> ExtractionResult:
    log("Submitting to Document AI", severity="DEBUG", gcs_uri=gcs_uri)

    bucket_name = gcs_uri.replace("gs://", "").split("/")[0]
    blob_name = "/".join(gcs_uri.replace("gs://", "").split("/")[1:])
    pdf_bytes = download_bytes(bucket_name, blob_name)

    chunks = _split_pdf(pdf_bytes)
    client = _get_client()

    if len(chunks) > 1:
        log("PDF split into chunks", severity="DEBUG", chunk_count=len(chunks))

    full_text_parts, all_kvps, all_tables, total_pages = [], [], [], 0
    for i, chunk in enumerate(chunks):
        document = _process_chunk(client, chunk)
        full_text_parts.append(document.text)
        kvps, tables = _parse_document(document)
        all_kvps.extend(kvps)
        all_tables.extend(tables)
        total_pages += len(document.pages)
        log("Chunk processed", severity="DEBUG", chunk=i + 1, pages=len(document.pages))

    log("Document AI extraction complete", page_count=total_pages, key_value_pairs_count=len(all_kvps), tables_count=len(all_tables))

    return ExtractionResult(
        full_text="\n".join(full_text_parts),
        key_value_pairs=all_kvps,
        tables=all_tables,
        page_count=total_pages,
    )


def process_document_cached(gcs_uri: str, contract_id: str) -> tuple[ExtractionResult, bool]:
    """Returns (ExtractionResult, cache_hit). Reads from GCS processing zone if available,
    otherwise calls Document AI and writes the result to GCS for future reuse."""
    blob_name = f"{config.GCS_PROCESSING_PREFIX}/contracts/{contract_id}/ocr.json"

    if blob_exists(config.GCS_BUCKET, blob_name):
        log("OCR cache hit -- loading from GCS processing zone", contract_id=contract_id)
        data = download_json(config.GCS_BUCKET, blob_name)
        result = ExtractionResult(
            full_text=data["full_text"],
            key_value_pairs=[KeyValuePair(**kv) for kv in data["key_value_pairs"]],
            tables=[ExtractedTable(**t) for t in data["tables"]],
            page_count=data["page_count"],
        )
        return result, True

    result = process_document(gcs_uri, contract_id)

    payload = json.dumps({
        "full_text": result.full_text,
        "key_value_pairs": [kv.model_dump() for kv in result.key_value_pairs],
        "tables": [t.model_dump() for t in result.tables],
        "page_count": result.page_count,
    })
    upload_json(payload, config.GCS_BUCKET, blob_name)
    log("OCR result cached to GCS processing zone", contract_id=contract_id, blob=blob_name)

    return result, False
