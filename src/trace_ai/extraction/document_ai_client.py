from google.cloud import documentai
from trace_ai.config import config
from trace_ai.common.gcs_client import download_bytes
from trace_ai.common.logger import log
from trace_ai.extraction.extraction_models import ExtractionResult, KeyValuePair, ExtractedTable


def _get_client() -> documentai.DocumentProcessorServiceClient:
    opts = {"api_endpoint": f"{config.DOCUMENT_AI_LOCATION}-documentai.googleapis.com"}
    return documentai.DocumentProcessorServiceClient(client_options=opts)


def _processor_name() -> str:
    return (
        f"projects/{config.GCP_PROJECT_ID}"
        f"/locations/{config.DOCUMENT_AI_LOCATION}"
        f"/processors/{config.DOCUMENT_AI_FORM_PROCESSOR_ID}"
    )


def _extract_text_from_layout(document: documentai.Document, layout) -> str:
    text = ""
    for segment in layout.text_anchor.text_segments:
        start = int(segment.start_index)
        end = int(segment.end_index)
        text += document.text[start:end]
    return text.strip()


def process_document(gcs_uri: str, contract_id: str) -> ExtractionResult:
    log("Submitting to Document AI", severity="DEBUG", gcs_uri=gcs_uri)

    bucket_name = gcs_uri.replace("gs://", "").split("/")[0]
    blob_name = "/".join(gcs_uri.replace("gs://", "").split("/")[1:])
    pdf_bytes = download_bytes(bucket_name, blob_name)

    client = _get_client()
    raw_document = documentai.RawDocument(content=pdf_bytes, mime_type="application/pdf")
    process_options = documentai.ProcessOptions(
        ocr_config=documentai.OcrConfig(enable_native_pdf_parsing=True)
    )
    request = documentai.ProcessRequest(
        name=_processor_name(),
        raw_document=raw_document,
        process_options=process_options,
    )
    result = client.process_document(request=request)
    document = result.document

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

    log("Document AI extraction complete", page_count=len(document.pages), key_value_pairs_count=len(key_value_pairs), tables_count=len(tables))

    return ExtractionResult(
        full_text=document.text,
        key_value_pairs=key_value_pairs,
        tables=tables,
        page_count=len(document.pages),
    )
