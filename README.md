# SalaryLens AI by CodeSec

Production AI-Powered Bank Statement Salary Detection and Verification Backend.

SalaryLens AI automates the analysis of customer bank statement PDFs (3-month or 6-month) to detect recurring salary transactions, validate incoming credit streams with authoritative Python financial logic, retrieve grounded evidence through RAG, and execute structured AI evaluations using the Jev decision engine via OpenRouter.

---

## Architecture & Technology Stack

- **Runtime & Language:** Python 3.12+
- **Web Framework:** FastAPI (with Pydantic v2 validation)
- **Database ORM & Migrations:** SQLAlchemy 2.x (Async + Sync) & Alembic
- **Primary Data Store:** PostgreSQL with pgvector extension (SQLite fallback for quick local testing)
- **Caching & Broker:** Redis 7
- **Background Tasks:** Celery 5.3+
- **Document Processing:** PyMuPDF (fitz) for PDF extraction and raster rendering
- **AI Integration:** OpenRouter API (`httpx`) with token tracking, cost control, and demo mode
- **Financial Validation Engine:** Pure Python with `Decimal` for currency precision
- **Containerization:** Docker & Docker Compose

---

## Project Structure

```
salarylens-ai/
├── app/
│   ├── main.py                          # FastAPI app entrypoint, middleware, lifecycle
│   ├── api/
│   │   ├── dependencies.py              # DB session, JWT auth, tenant isolation, RBAC
│   │   └── routes/
│   │       ├── health.py                # Health check and readiness probes
│   │       ├── auth.py                  # Authentication and tenant login
│   │       ├── statements.py            # PDF upload, status, results, reviews
│   │       ├── admin.py                 # Admin models catalog and usage stats
│   │       └── dashboard.py             # Next.js aggregate metrics
│   ├── core/
│   │   ├── config.py                    # Pydantic v2 BaseSettings configuration
│   │   ├── security.py                  # Bcrypt hashing & JWT token handling
│   │   └── logging.py                   # Structured JSON logging & sensitive data filter
│   ├── db/
│   │   ├── base.py                      # SQLAlchemy DeclarativeBase, GUID type, timestamps
│   │   └── session.py                   # Async & Sync engine / session managers
│   ├── models/                          # 13 SQLAlchemy database models
│   │   ├── user.py                      # User model
│   │   ├── organization.py              # Tenant organization model
│   │   ├── membership.py                # User-Organization RBAC membership
│   │   ├── statement.py                 # Bank statement upload records
│   │   ├── transaction.py               # Extracted bank statement transactions
│   │   ├── salary_candidate.py          # Salary candidate groups & candidates
│   │   ├── analysis_run.py              # Analysis runs and decision evidence
│   │   ├── model_usage.py               # Per-call OpenRouter token & cost tracking
│   │   ├── human_review.py              # Manual review audit records
│   │   ├── audit.py                     # Security and data governance events
│   │   ├── employer_alias.py            # Tenant-isolated employer aliases
│   │   └── retention.py                 # Data retention purge records
│   ├── schemas/                         # Pydantic v2 API schemas
│   ├── services/
│   │   ├── document_processing/         # PDF validation, text extraction, scan detection
│   │   ├── openrouter/                  # Resilient OpenRouter client & pricing registry
│   │   ├── transaction_extraction/      # Salary Finder model integration
│   │   ├── salary_detection/            # Python authoritative Decimal financial validator
│   │   ├── retrieval/                   # PostgreSQL RAG & pgvector similarity
│   │   ├── decision_engine/             # Jev model decision engine
│   │   └── cost_tracking/               # AI budget enforcement & cost auditing
│   └── workers/
│       ├── celery_app.py                # Celery instance configuration
│       └── tasks.py                     # Background asynchronous pipeline tasks
├── alembic/                             # Alembic database migrations
├── storage/                             # Private local document storage
│   ├── uploads/                         # Encrypted/private uploaded PDFs
│   └── renders/                         # Scanned page raster images
├── fixtures/                            # Synthetic bank statements & expected outcomes
├── tests/                               # Comprehensive pytest suite
├── .env.example                         # Complete configuration template
├── Dockerfile                           # Multi-stage production container
├── docker-compose.yml                   # Postgres, Redis, API, and Worker orchestration
└── pyproject.toml                       # Python package dependencies & tools
```

---

## Quick Start & Local Setup

### 1. Prerequisites
- Python 3.12+
- Docker & Docker Compose (optional for local SQLite development)

### 2. Environment Setup
```bash
# Create and activate virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -e ".[dev]"

# Create your .env file
cp .env.example .env
```

### 3. Run Database Migrations
```bash
alembic upgrade head
```

### 4. Run the Development Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The API is now accessible at:
- **Swagger Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI Schema:** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)
- **Health Check:** [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

---

## Running with Docker Compose (Full Stack: Frontend + Backend + Worker + DB + Redis)

To launch the complete SalaryLens platform (Vite/React Frontend, FastAPI API, Celery Worker, PostgreSQL with pgvector, and Redis):

```bash
docker compose up --build
```

Once up, access the platform at:
- **Web UI & Dashboard:** [http://localhost:3000](http://localhost:3000)
- **FastAPI Swagger Docs:** [http://localhost:3000/docs](http://localhost:3000/docs) (or direct on port 8001: [http://localhost:8001/docs](http://localhost:8001/docs))
- **API Health Check:** [http://localhost:8001/api/v1/health](http://localhost:8001/api/v1/health)

Check service status and logs:
```bash
docker compose ps
docker compose logs -f api frontend
```

---

## Running the Automated Test Suite

```bash
pytest -v
```

---

## Implementation Milestones Completed

- [x] **Phase 1: Project Foundation**
  - Modular clean-architecture backend
  - Pydantic v2 settings with strict production startup validation
  - SQLAlchemy 2.0 with all 13 tenant-isolated data models
  - Alembic migrations
  - Structured logging with sensitive data redaction filter
  - JWT authentication and bcrypt password hashing
  - System health check endpoint (`/api/v1/health`) with live DB and storage probe
  - OpenAPI 3.1 & Swagger/ReDoc documentation
  - Multi-stage Dockerfile & Docker Compose
- [x] **Phase 2: PDF Processing & Document Ingestion**
  - PDF signature (%PDF) validation, size limits (25MB), page limits (60 pages)
  - PyMuPDF text extraction
  - Scanned-document heuristic detection
  - High-resolution page raster rendering (150 DPI) for vision models
  - Private storage manager with strict 0600 file permissions and tenant isolation
- [x] **Phase 3: OpenRouter AI Integration & Salary Finder**
  - Resilient OpenRouter client with exponential backoff retries and timeouts
  - Salary Finder model integration with strict anti-prompt-injection system prompt
  - Strict Pydantic JSON schema validation
  - Token counting, latency tracking, and provider/estimated cost auditing
  - Model pricing registry and per-statement AI budget enforcement ($1.50 cap)
  - Deterministic Demo Mode simulation
- [x] **Phase 4: Authoritative Python Financial Validation**
  - Pure Python financial engine using `Decimal` for all currency calculations
  - Detection of incoming credits, debit/credit direction
  - Day-of-month variation (25th to 31st) and monthly cadence scoring
  - Amount variation analysis (`amount_variation_pct = ((max - min) / avg) * 100`)
  - Missing-month detection across statement span
  - Duplicate transaction detection
  - Reversals and chargeback detection
  - Employer name normalization and alias clustering
- [x] **Phase 5: RAG Evidence Retrieval & Jev Decision Engine**
  - Tenant-isolated structured SQL evidence retriever
  - Configured Jev model evaluation through OpenRouter
  - Authoritative Python grounding verification (rejects hallucinated transaction IDs or invalid months)
  - Automatic fallback to human review on conflicting evidence
- [x] **Phase 6: Background Processing with Celery & Redis**
  - Celery instance configuration and asynchronous pipeline tasks
  - Idempotent processing with status transitions
  - Automated document retention and file purge jobs
- [x] **Phase 7: Security, Multi-Tenant REST API & Dashboard Endpoints**
  - User registration, login, and profile endpoints
  - Statement upload, status check, transaction pagination, analysis restart, and review endpoints
  - Strict tenant isolation (404/403 on cross-tenant access)
  - Admin models catalog (safe metadata without secret exposure) and AI usage analytics
  - Aggregate dashboard summary endpoint for future Next.js integration
- [x] **Phase 8: Comprehensive Verification & 10 Synthetic Fixtures**
  - Generated all 10 required synthetic bank statement PDFs and expected outcome JSONs
  - Automated test suite with 39 passing unit, integration, and evaluation tests
- [x] **Phase 9: Excel Bank Statement Processing Workflow & Token Optimization**
  - **5-Sheet Excel Workbook (`.xlsx`)**:
    1. `Summary`: Statement metadata, page breakdown (native vs OCR), transaction counts, exclusion breakdown by reason, AI token/cost metrics, validation status.
    2. `Bank_Account_holder_info`: Grounded customer/account data (name, mobile, address, PAN, account number) extracted without hallucinations.
    3. `Bank_Txns`: Comprehensive audit sheet preserving ALL extracted transactions (debits and credits), original narrations, amounts, balances, and exclusion reasons.
    4. `Salary_Analysis_Txns`: Filtered, compact dataset containing only candidate salary credits and ambiguous incoming transactions for AI/RAG evidence.
    5. `Salary_Results`: Grouped candidate summaries (averages, median, cadence, salary months) and individual supporting credit transactions.
  - **Deterministic Transaction Filtering (`TransactionFilterService`)**:
    - Direction safeguard: Explicit credit/debit columns, markers, running balances, avoiding crude positive/negative assumptions.
    - Exclusions: ATM, POS, utility bills, EMI, loan repayments, bank fees, irrelevant UPI debits.
    - Preserved: Recurring credits, suspected employer credits, ambiguous incoming deposits, and salary-related reversals/refunds.
    - Mathematical reconciliation: `Total Extracted = Included + Excluded`.
  - **OpenRouter Token Reduction**:
    - AI receives only filtered candidate evidence, grouping related records and omitting full transaction history and sensitive personal data.
    - Financial stats (cadence, missing months, averages) calculated deterministically in Python.
  - **Secure Authenticated Download Endpoint**:
    - `GET /api/v1/statements/{statement_id}/download`
    - Role-based access control, tenant scoping, anti-path-traversal, safe content disposition.
    - Formula injection protection (`=`, `+`, `-`, `@` escaped with `'`).
  - **Idempotency & Partial Failure Handling**:
    - Initial workbook created post-extraction; finalized post-AI. Accessible even if AI classification fails.
    - Synchronized with human reviewer overrides.
- [x] **Phase 10: Indra OCR Migration & Local LLM Benchmarking**
  - **Hybrid Document OCR Pipeline (`HybridDocumentPipeline`)**:
    - Native PyMuPDF extraction fast-path for clean digital statements (< 50ms per document).
    - CPU-native ONNX **Indra OCR** (`indra-ocr`) engine for scanned pages, image-based statements, and distorted/noisy documents.
    - Normalized Document Intermediate Representation (`NormalizedDocument`, `NormalizedPage`, `NormalizedBlock`, `NormalizedLine`).
    - Robust tabular data extraction via `TableParser` supporting Markdown pipes and HTML table cells with numerical overflow protections.
    - Page order preservation, source page tracking, and cross-engine transaction deduplication.
  - **Unified Local LLM Inference Engine (`LocalLLMClient`)**:
    - Local inference via Ollama (`http://localhost:11434`) with Apple Silicon Metal GPU acceleration and token telemetry.
    - GGUF model ingestion from external storage (`/Volumes/ProjectZero/models`).
    - Automatic fallback to OpenRouter (`google/gemma-4-31b-it:free`) on local timeout or memory pressure.
    - Strict deterministic financial grounding: Python `FinancialValidationEngine` serves as the sole mathematical authority for cadence, recurrence, variance, and reversal calculations.
  - **Local Model Benchmark Runner (`scripts/benchmark_models.py`)**:
    - Evaluated 4 parameter tiers across 10 synthetic bank statement fixtures:
      - `qwen2.5:1.5b` (1.5B): 90.0% accuracy, 100% precision/recall, 1,061 ms latency, 1.43 GB VRAM.
      - `qwen3.5-9b-uncensored:latest` (9B, external SSD): 90.0% accuracy, 100% precision/recall, 22,804 ms latency, 6.23 GB VRAM.
      - `llama3.2:3b` (3B): 80.0% accuracy, 100% precision, 85.7% recall, 1,250 ms latency, 3.74 GB VRAM.
      - `gemma4:12b` (12B): 80.0% accuracy, 85.7% precision/recall, 46,182 ms latency, 1.1 GB VRAM.

---

## Local LLM Setup & Indra OCR Integration

### 1. Local LLM Runtime (Ollama)

SalaryLens AI supports zero-cost local LLM inference with Metal GPU offloading via Ollama:

```bash
# Verify Ollama is running
curl -s http://localhost:11434/api/tags

# Pull recommended lightweight model (Tier 1: 1.5B parameters, ~1.0 GB RAM)
ollama pull qwen2.5:1.5b

# Pull balanced model (Tier 2: 3B parameters, ~2.0 GB RAM)
ollama pull llama3.2:3b
```

### 2. Loading Models from External SSD (`/Volumes/ProjectZero/models`)

For deep reasoning models (e.g., Qwen 2.5/3.5 9B/14B Q4_K_M GGUFs) stored on an external SSD:

```bash
# Navigate to the external models directory
cd /Volumes/ProjectZero/models

# Create model from Modelfile pointing to GGUF on SSD
ollama create qwen3.5-9b-uncensored -f Modelfile.qwen3.5-9b

# Verify the model is registered
ollama list
```

### 3. Running Model Benchmarks

A fully automated, reproducible benchmark runner tests all configured models across all 10 standard synthetic bank statement fixtures:

```bash
# Run benchmark across all installed models
python scripts/benchmark_models.py \
  --models qwen2.5:1.5b llama3.2:3b qwen3.5-9b-uncensored:latest gemma4:12b \
  --output benchmark_results.json \
  --report benchmark_report.md
```

### 4. Local Model Benchmark Leaderboard

| Model | Tier | Accuracy | Precision | Recall | Hallucinations | Avg Latency | Peak VRAM | Cost (INR) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **qwen2.5:1.5b** | 1.5B | **90.0%** | **100.0%** | **100.0%** | **0** | **1,061 ms** | **1.43 GB** | **₹ 0.00** |
| **qwen3.5-9b-uncensored** | 9B (SSD) | **90.0%** | **100.0%** | **100.0%** | **0** | 22,804 ms | 6.23 GB | **₹ 0.00** |
| **llama3.2:3b** | 3B | 80.0% | 100.0% | 85.7% | 0 | 1,250 ms | 3.74 GB | **₹ 0.00** |
| **gemma4:12b** | 12B | 80.0% | 85.7% | 85.7% | 0 | 46,182 ms | 1.1 GB | **₹ 0.00** |

### 5. Recommended Production Routing (Hybrid 3-Tier Architecture)

1. **Tier 1 — Fast-Path (Sub-Second):** Native text or Indra OCR + `qwen2.5:1.5b` handles standard recurring salary credits with zero token cost.
2. **Tier 2 — Reasoning Escalation:** When candidate confidence < 0.85, multiple candidate employers exist, or irregular variances are flagged, escalate to `qwen3.5-9b-uncensored:latest` or `gemma4:12b`.
3. **Tier 3 — Cloud Fallback:** If local inference is unreachable or times out, fail over seamlessly to OpenRouter (`google/gemma-4-31b-it:free`).

---

## Excel Workbook Download API

Authorized tenant members (e.g. underwriters, admins, auditors) can download the generated 5-sheet financial workbook:

```http
GET /api/v1/statements/{statement_id}/download
Authorization: Bearer <jwt_token>
```

**Response:**
- Content-Type: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- Content-Disposition: `attachment; filename="SalaryLens_{statement_id}.xlsx"`

---

## Running Migrations & Upgrades

```bash
# Apply pending database schema migrations
alembic upgrade head
```

