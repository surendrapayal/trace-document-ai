from pydantic import BaseModel


class KeyValuePair(BaseModel):
    key: str
    value: str
    confidence: float = 0.0


class ExtractedTable(BaseModel):
    headers: list[str]
    rows: list[list[str]]


class ExtractionResult(BaseModel):
    full_text: str
    key_value_pairs: list[KeyValuePair]
    tables: list[ExtractedTable]
    page_count: int
