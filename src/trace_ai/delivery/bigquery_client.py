from google.cloud import bigquery
from trace_ai.config import config
from trace_ai.common.logger import log
from trace_ai.normalization.schema import ContractRecord, ExtractionStatus
from datetime import datetime, timezone
from enum import Enum
import json

_client = bigquery.Client(project=config.GCP_PROJECT_ID)
_dataset = config.BIGQUERY_DATASET


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _table(name: str) -> str:
    tables = {
        "contracts": config.BIGQUERY_TABLE_CONTRACTS,
        "audit_events": config.BIGQUERY_TABLE_AUDIT,
    }
    return f"{config.GCP_PROJECT_ID}.{_dataset}.{tables[name]}"


def upsert_contract(record: ContractRecord, gcs_uri: str | None = None) -> None:
    data = record.model_dump()
    if gcs_uri:
        data["curated_gcs_uri"] = gcs_uri
    data["updated_at"] = _now()

    # Nested dicts/lists go to JSON columns: pass as STRING and convert with PARSE_JSON
    row = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in data.items()}
    json_cols = {k for k, v in data.items() if isinstance(v, (dict, list))}

    def _ref(k: str) -> str:
        return f"PARSE_JSON(@{k})" if k in json_cols else f"@{k}"

    def _param(k: str, v) -> bigquery.ScalarQueryParameter:
        if isinstance(v, bool):
            return bigquery.ScalarQueryParameter(k, "BOOL", v)
        if isinstance(v, int):
            return bigquery.ScalarQueryParameter(k, "INT64", v)
        if isinstance(v, float):
            return bigquery.ScalarQueryParameter(k, "FLOAT64", v)
        if isinstance(v, Enum):
            return bigquery.ScalarQueryParameter(k, "STRING", v.value)
        return bigquery.ScalarQueryParameter(k, "STRING", str(v) if v is not None else None)

    merge_sql = f"""
        MERGE `{_table("contracts")}` T
        USING (SELECT @contract_id AS contract_id) S
        ON T.contract_id = S.contract_id
        WHEN MATCHED THEN UPDATE SET {", ".join(f"T.{k} = {_ref(k)}" for k in row)}
        WHEN NOT MATCHED THEN INSERT ({", ".join(row)}) VALUES ({", ".join(_ref(k) for k in row)})
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[_param(k, v) for k, v in row.items()])
    _client.query(merge_sql, job_config=job_config).result()
    log("Contract upserted to BigQuery", severity="DEBUG")


def write_audit_event(contract_id: str, stage: str, event: str, details: dict | None = None) -> None:
    row = {
        "contract_id": contract_id,
        "stage": stage,
        "event": event,
        "details": json.dumps(details or {}),
        "timestamp": _now(),
    }
    _client.insert_rows_json(_table("audit_events"), [row])
    log("Audit event written", severity="DEBUG", event=event, audit_stage=stage)


def get_contract(contract_id: str) -> dict | None:
    query = f"SELECT * FROM `{_table('contracts')}` WHERE contract_id = @contract_id LIMIT 1"
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("contract_id", "STRING", contract_id)]
    )
    rows = list(_client.query(query, job_config=job_config).result())
    return dict(rows[0]) if rows else None


def get_contract_by_hash(file_hash: str) -> dict | None:
    query = f"SELECT * FROM `{_table('contracts')}` WHERE file_hash = @file_hash LIMIT 1"
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("file_hash", "STRING", file_hash)]
    )
    rows = list(_client.query(query, job_config=job_config).result())
    return dict(rows[0]) if rows else None


def get_pending_review() -> list[dict]:
    query = f"SELECT * FROM `{_table('contracts')}` WHERE extraction_status = '{ExtractionStatus.REVIEW_REQUIRED.value}'"
    return [dict(row) for row in _client.query(query).result()]


def list_contracts(status: str | None = None) -> list[dict]:
    if status:
        query = f"SELECT * FROM `{_table('contracts')}` WHERE extraction_status = @status"
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("status", "STRING", status)]
        )
        rows = _client.query(query, job_config=job_config).result()
    else:
        rows = _client.query(f"SELECT * FROM `{_table('contracts')}`").result()
    return [dict(row) for row in rows]


def update_review_decision(contract_id: str, reviewer: str, decision: str, notes: str) -> None:
    sql = f"""
        UPDATE `{_table("contracts")}`
        SET extraction_status = @decision,
            reviewed_by = @reviewer,
            review_notes = @notes,
            reviewed_at = @reviewed_at
        WHERE contract_id = @contract_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("decision", "STRING", decision),
            bigquery.ScalarQueryParameter("reviewer", "STRING", reviewer),
            bigquery.ScalarQueryParameter("notes", "STRING", notes),
            bigquery.ScalarQueryParameter("reviewed_at", "STRING", _now()),
            bigquery.ScalarQueryParameter("contract_id", "STRING", contract_id),
        ]
    )
    _client.query(sql, job_config=job_config).result()
    write_audit_event(contract_id, "review", "human_review_decision", {
        "reviewer": reviewer, "decision": decision, "notes": notes,
    })
    log("Review decision recorded", decision=decision, reviewer=reviewer)
