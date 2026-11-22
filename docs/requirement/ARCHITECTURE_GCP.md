# TRACE Platform — GCP Architecture Diagram

## Full System Architecture

```mermaid
flowchart TD
    %% ─── EXTERNAL ACTORS ───────────────────────────────────────────
    USER(["👤 Contract Uploader\n(Business User / System)"])
    ANALYST(["👤 Contract Review Analyst\n(HITL Reviewer)"])
    CONSUMER(["👤 Business Consumer\n(Downstream System)"])

    %% ─── STAGE 1: INGEST ────────────────────────────────────────────
    subgraph INGEST["① INGEST LAYER"]
        GCS_RAW[("GCS\nskumar_trace_ai/raw/\n(Landing Prefix)")]
        PIPELINE["trace_ai.pipeline\n(Python Orchestrator)"]
    end

    %% ─── STAGE 2: EXTRACT ───────────────────────────────────────────
    subgraph EXTRACT["② EXTRACTION LAYER"]
        DOC_AI["Document AI\n(OCR + Form Parser)"]
        DLP["Cloud DLP\n(PII Detection & Masking)"]
        GCS_PROC[("GCS\nskumar_trace_ai/processing/\n(OCR Artifacts)")]
    end

    %% ─── STAGE 3: INTELLIGENCE ──────────────────────────────────────
    subgraph INTELLIGENCE["③ INTELLIGENCE LAYER"]
        VECTOR_SEARCH["Vertex AI\nVector Search\n(RAG Index)"]
        GEMINI["Vertex AI Gemini\n(7 Extraction Prompts)"]
    end

    %% ─── STAGE 4: NORMALIZE & VALIDATE ─────────────────────────────
    subgraph VALIDATE["④ NORMALIZE & VALIDATE LAYER"]
        SCHEMA["Canonical Schema\nNormalization (Pydantic)"]
        LLM_JUDGE["Vertex AI Gemini\n(LLM-as-a-Judge)"]
        CONFIDENCE{"Confidence\nScore"}
    end

    %% ─── STAGE 5: DELIVER ───────────────────────────────────────────
    subgraph DELIVER["⑤ DELIVER LAYER"]
        CLOUD_RUN["Cloud Run\n(FastAPI Review App)"]
        GCS_OUT[("GCS\nskumar_trace_ai/curated/\n(JSON Output)")]
        STORAGE_BACKEND[("Firestore or BigQuery\n(Audit & Contract State)")]
    end

    %% ─── CROSS-CUTTING: SECURITY & OBSERVABILITY ────────────────────
    subgraph SECURITY["🔒 SECURITY & OBSERVABILITY"]
        IAM["Cloud IAM\n(RBAC)"]
        SSO["Google Workspace SSO\n/ Identity Platform"]
        LOGGING["Cloud Audit Logs\n+ Structured JSON Logs"]
        MONITORING["Cloud Monitoring\n(Alerts & Metrics)"]
    end

    %% ─── KNOWLEDGE BASE (RAG SOURCE) ────────────────────────────────
    subgraph KB["📚 KNOWLEDGE BASE"]
        GCS_KB[("GCS\nskumar_trace_ai/kb/\n(Playbooks / Fee Dicts)")]
        EMBED["Vertex AI\nEmbeddings API"]
    end

    %% ─── FLOW ───────────────────────────────────────────────────────

    USER -->|"Upload PDF"| GCS_RAW
    GCS_RAW -->|"GCS URI passed to"| PIPELINE

    PIPELINE -->|"Submit Document"| DOC_AI
    DOC_AI -->|"Raw Text + Tables"| DLP
    DLP -->|"Masked Content"| GCS_PROC
    GCS_PROC -->|"Structured Content"| GEMINI

    GCS_KB -->|"Chunk & Embed"| EMBED
    EMBED -->|"Index Vectors"| VECTOR_SEARCH
    VECTOR_SEARCH -->|"Contextual Grounding"| GEMINI

    GEMINI -->|"Raw Extracted JSON"| SCHEMA
    SCHEMA -->|"ContractRecord"| LLM_JUDGE
    LLM_JUDGE -->|"Score"| CONFIDENCE

    CONFIDENCE -->|"score ≥ 0.85\n✅ Approved"| GCS_OUT
    CONFIDENCE -->|"score 0.60–0.85\n⚠️ Review Required"| CLOUD_RUN
    CONFIDENCE -->|"score < 0.60\n❌ Rejected"| PIPELINE

    CLOUD_RUN -->|"Reviewer UI"| ANALYST
    ANALYST -->|"Approve / Reject"| CLOUD_RUN
    CLOUD_RUN -->|"Approved Output"| GCS_OUT
    CLOUD_RUN -->|"Review Decision"| STORAGE_BACKEND

    PIPELINE -->|"Audit Event per Stage"| STORAGE_BACKEND
    LLM_JUDGE -->|"Confidence Score"| STORAGE_BACKEND
    GCS_OUT -->|"Read JSON Output"| CONSUMER

    IAM -.->|"Access Control"| GCS_RAW
    IAM -.->|"Access Control"| GCS_OUT
    IAM -.->|"Access Control"| GEMINI
    SSO -.->|"Authenticate"| CLOUD_RUN
    LOGGING -.->|"Capture Logs"| PIPELINE
    LOGGING -.->|"Capture Logs"| GEMINI
    MONITORING -.->|"Monitor"| PIPELINE
```

---

## Component Interaction Summary

### Data Flow (Happy Path)

```mermaid
sequenceDiagram
    actor User
    participant GCS_Raw as GCS Raw Zone
    participant Pipeline as trace_ai.pipeline
    participant DocAI as Document AI
    participant DLP as Cloud DLP
    participant VectorSearch as Vector Search (RAG)
    participant Gemini as Vertex AI Gemini
    participant LLMJudge as LLM-as-a-Judge
    participant StorageBackend as storage_backend (Firestore or BigQuery)
    participant GCS_Out as GCS Curated Zone

    User->>GCS_Raw: Upload contract PDF
    GCS_Raw->>Pipeline: GCS URI passed to pipeline
    Pipeline->>DocAI: Submit document for OCR
    DocAI-->>Pipeline: Structured text + tables
    Pipeline->>DLP: Scan & mask PII
    DLP-->>Pipeline: Masked content
    Pipeline->>VectorSearch: Query RAG context
    VectorSearch-->>Gemini: Relevant grounding chunks
    Pipeline->>Gemini: Extract all sections (7 prompts)
    Gemini-->>Pipeline: Raw extracted JSON
    Pipeline->>LLMJudge: Validate extraction quality
    LLMJudge-->>Pipeline: Confidence score + verdict
    Pipeline->>StorageBackend: Write audit event at each stage
    Pipeline->>GCS_Out: Store validated JSON output
```

---

### Human Review Flow (Low Confidence Path)

```mermaid
sequenceDiagram
    participant Pipeline as trace_ai.pipeline
    participant StorageBackend as storage_backend (Firestore or BigQuery)
    participant CloudRun as Cloud Run (FastAPI Review App)
    actor Analyst as Contract Review Analyst
    participant GCS_Out as GCS Curated Zone

    Pipeline->>StorageBackend: Write contract with status=Review Required
    CloudRun->>StorageBackend: GET /queue — fetch pending contracts
    CloudRun->>Analyst: Display contract + extracted data
    Analyst->>CloudRun: Approve / Reject decision
    CloudRun->>StorageBackend: Log reviewer decision + audit record
    CloudRun->>GCS_Out: Write approved JSON output
```

---

## Stage-by-Stage Component Map

| Stage | Component | Role | Interacts With |
|-------|-----------|------|----------------|
| Ingest | GCS Raw Zone | Landing bucket for uploaded PDFs | trace_ai.pipeline |
| Ingest | trace_ai.pipeline | Python orchestrator — wires all 7 stages | All modules |
| Extract | Document AI | OCR, table & key-value extraction | Cloud DLP |
| Extract | Cloud DLP | PII detection & masking | Vertex AI Gemini |
| Extract | GCS Processing Zone | Stores OCR artifacts | Vertex AI Gemini |
| Intelligence | Vertex AI Vector Search | RAG index — contextual grounding | Vertex AI Gemini |
| Intelligence | Vertex AI Gemini | LLM extraction — 7 prompts (sections + LLM judge) | Canonical Schema |
| Normalize | Pydantic ContractRecord | Maps raw Gemini output to canonical schema | LLM-as-a-Judge |
| Validate | Vertex AI Gemini (LLM Judge) | Secondary Gemini call scores extraction quality | Confidence routing |
| Deliver | GCS Curated Zone | Final JSON output storage | Business Consumer |
| Deliver | Cloud Run (FastAPI Review App) | Jinja2 UI for analyst review and approval | storage_backend, GCS Curated |
| Deliver | Firestore or BigQuery (via storage_backend) | Audit trail, contract state, confidence scores | pipeline, Cloud Run |
| Security | Cloud IAM | RBAC for all GCP resources | All services |
| Security | Google Workspace SSO | Authenticates human users to review app | Cloud Run |
| Security | Cloud Audit Logs | Immutable activity log | All services |
| Security | Cloud Monitoring | Metrics, alerts, pipeline health | pipeline |

---

## Storage Zone Layout

```mermaid
graph LR
    subgraph GCS["Google Cloud Storage — skumar_trace_ai"]
        RAW[("raw/\n• Original PDFs")]
        PROC[("processing/\n• OCR outputs\n• DLP artifacts")]
        CURATED[("curated/\n• Final validated\n  JSON outputs")]
        KB[("kb/\n• documents/\n• chunks/")]
    end

    subgraph VECTOR["Vertex AI Vector Search"]
        IDX[("Vector Index\n• Embeddings\n• Playbooks\n• Fee dictionaries")]
    end

    subgraph FS["Operational Store (Firestore or BigQuery)"]
        CONTRACTS[("contracts\n• ContractRecord\n• confidence_score\n• extraction_status")]
        AUDIT[("audit_events\n• stage events\n• HITL decisions")]
    end

    RAW -->|"Document AI"| PROC
    PROC -->|"Gemini + Validate"| CURATED
    KB -->|"kb_indexer embeds"| IDX
    IDX -->|"RAG Grounding"| PROC
```

---

## Security Boundary

```mermaid
graph TD
    subgraph VPC["VPC Service Controls Perimeter"]
        GCS_ALL["GCS (All Zones)"]
        DOCAI["Document AI"]
        DLP["Cloud DLP"]
        VERTEX["Vertex AI (Gemini + Vector Search)"]
        FIRESTORE_BQ["Firestore or BigQuery\n(via STORAGE_BACKEND)"]
        CLOUDRUN["Cloud Run"]
    end

    IAM["Cloud IAM\n(Service Accounts + RBAC)"]
    SSO["Google Workspace SSO"]
    CMEK["Cloud KMS\n(CMEK Encryption)"]
    AUDIT["Cloud Audit Logs"]

    IAM -->|"Controls access to"| VPC
    SSO -->|"Authenticates users to"| VPC
    CMEK -->|"Encrypts data in"| VPC
    AUDIT -->|"Logs all activity in"| VPC
```
