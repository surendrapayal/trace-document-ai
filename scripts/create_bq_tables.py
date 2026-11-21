"""
One-time script to create BigQuery tables for TRACE.
Run this before using STORAGE_BACKEND=bigquery.

Usage:
    python scripts/create_bq_tables.py
"""

from google.cloud import bigquery
from trace_ai.config import config

client = bigquery.Client(project=config.GCP_PROJECT_ID)
dataset_ref = f"{config.GCP_PROJECT_ID}.{config.BIGQUERY_DATASET}"

# ── create dataset if it doesn't exist ───────────────────────────────────────

dataset = bigquery.Dataset(dataset_ref)
dataset.location = config.GCP_REGION
client.create_dataset(dataset, exists_ok=True)
print(f"Dataset ready: {dataset_ref}")

# ── contracts table ───────────────────────────────────────────────────────────
# Nested models (processor_info, company_information, etc.) are stored as
# JSON strings — bigquery_client.py serialises them with json.dumps().

contracts_schema = [
    bigquery.SchemaField("contract_id", "STRING", mode="REQUIRED"),

    # ProcessorInfo
    bigquery.SchemaField("processor_info", "JSON"),

    # CompanyInformation
    bigquery.SchemaField("company_information", "JSON"),

    # MerchantDetails
    bigquery.SchemaField("merchant_details", "JSON"),

    # CreditCardPricing (includes card_rates, recurring_fees, amex_details)
    bigquery.SchemaField("credit_card_pricing", "JSON"),

    # ProcessingDetails
    bigquery.SchemaField("processing_details", "JSON"),

    # List[OwnerOfficer]
    bigquery.SchemaField("owners_officers", "JSON"),

    # BankingInformation
    bigquery.SchemaField("banking_information", "JSON"),

    # Top-level scalar fields
    bigquery.SchemaField("confidence_score", "FLOAT64"),
    bigquery.SchemaField("extraction_status", "STRING"),
    bigquery.SchemaField("extracted_at", "STRING"),
    bigquery.SchemaField("reviewed_by", "STRING"),
    bigquery.SchemaField("review_notes", "STRING"),

    # Set by bigquery_client.upsert_contract
    bigquery.SchemaField("curated_gcs_uri", "STRING"),
    bigquery.SchemaField("updated_at", "STRING"),
    bigquery.SchemaField("reviewed_at", "STRING"),
]

contracts_table = bigquery.Table(f"{dataset_ref}.{config.BIGQUERY_TABLE_CONTRACTS}", schema=contracts_schema)
contracts_table.clustering_fields = ["extraction_status"]

# ── audit_events table ────────────────────────────────────────────────────────

audit_schema = [
    bigquery.SchemaField("contract_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("stage", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("event", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("details", "JSON"),
    bigquery.SchemaField("timestamp", "STRING", mode="REQUIRED"),
]

audit_table = bigquery.Table(f"{dataset_ref}.{config.BIGQUERY_TABLE_AUDIT}", schema=audit_schema)

# ── create ────────────────────────────────────────────────────────────────────

for table in (contracts_table, audit_table):
    created = client.create_table(table, exists_ok=True)
    print(f"Table ready: {created.full_table_id}")

print("\nDone. Add to .env:")
print(f"  BIGQUERY_DATASET={config.BIGQUERY_DATASET}")
print(f"  BIGQUERY_TABLE_CONTRACTS={config.BIGQUERY_TABLE_CONTRACTS}")
print(f"  BIGQUERY_TABLE_AUDIT={config.BIGQUERY_TABLE_AUDIT}")
