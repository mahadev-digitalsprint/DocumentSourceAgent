# 📊 FinWatch — Financial Document Intelligence & Website Monitoring

> Automatically discovers, downloads, classifies, and extracts metadata from financial PDF documents across company investor-relations websites. Monitors pages for changes and sends daily email digests.

---

## 🏗 Architecture

```
finwatch/
├── backend/                  # FastAPI + LangGraph agents
│   ├── app/
│   │   ├── agents/           # 8 pipeline agents (crawl → email)
│   │   ├── api/              # REST endpoints (companies, documents, jobs, …)
│   │   ├── workflow/         # LangGraph DAG wiring
│   │   ├── models.py         # SQLAlchemy ORM
│   │   ├── database.py       # PostgreSQL engine
│   │   ├── config.py         # Settings (reads from .env)
│   │   ├── tasks.py          # Celery tasks
│   │   └── main.py           # FastAPI app
│   └── .env                  # ← secrets go here (never commit)
└── frontend/                 # Streamlit multi-page app
    ├── Home.py               # Dashboard landing page (combined)
    ├── api_client.py         # Shared HTTP client → port 8080
    └── pages/
        ├── 2_Companies.py    # Add / manage companies
        ├── 3_WebWatch.py     # Page-change monitor
        ├── 4_Documents.py    # Financial & non-financial docs
        ├── 5_Metadata.py     # LLM-extracted metadata
        ├── 6_Changes.py      # 24h change log
        ├── 7_Email_Alerts.py # Email digest config
        ├── 8_Settings.py     # System settings
        └── 9_Analytics.py    # Charts & insights
```

---

## ⚙️ Prerequisites

| Requirement | Version | Notes |
|------------|---------|-------|
| Python | 3.11+ | |
| PostgreSQL | 14+ | Azure PostgreSQL or local |
| Redis | 7+ | Only needed for scheduled/async jobs |
| Azure OpenAI **or** OpenAI | — | LLM extraction |
| Tavily API key | — | PDF discovery |
| Firecrawl API key | — | Deep crawl (optional, gracefully skipped if no credits) |

---

## 🚀 Quick Start (Local — No Docker)

### 1 · Clone & enter

```bash
git clone https://github.com/mahadev-digitalsprint/DocumentSourceAgent.git
cd DocumentSourceAgent/finwatch
```

### 2 · Create & activate virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3 · Install dependencies

```bash
pip install -r backend/requirements.txt
pip install streamlit pandas openpyxl plotly requests
```

### 4 · Configure environment variables

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` and fill in:

```env
# ── Database ──────────────────────────────────────────────
DATABASE_URL=postgresql://user:password@host:5432/finwatch

# ── LLM (use one of the two) ──────────────────────────────
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=your-azure-openai-key
AZURE_OPENAI_DEPLOYMENT=gpt-4o

# OR plain OpenAI:
OPENAI_API_KEY=sk-...

# ── Crawling ──────────────────────────────────────────────
TAVILY_API_KEY=tvly-...
FIRECRAWL_API_KEY=fc-...          # optional

# ── Email (Office365) ─────────────────────────────────────
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=your@email.com
SMTP_PASSWORD=your-password
EMAIL_FROM=your@email.com
```

### 5 · Start the backend

```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

✅ API docs live at: **http://127.0.0.1:8080/docs**

### 6 · Start the frontend (new terminal)

```bash
cd frontend
python -m streamlit run Home.py --server.port 8501
```

✅ Dashboard live at: **http://localhost:8501**

---

## 🐳 Docker Compose (Recommended for production)

```bash
cd finwatch
docker-compose up --build
```

| Service | URL |
|---------|-----|
| FastAPI backend | http://localhost:8080 |
| Streamlit frontend | http://localhost:8501 |
| Celery worker | (background) |
| Redis | localhost:6379 |

---

## 🔄 Pipeline Agents

The pipeline runs as a **LangGraph DAG** with 8 nodes:

```
M1 Crawl → M2 Download → M3 OCR → M4 Classify → M5 WebWatch → M6 Extract → M7 Excel → M8 Email
```

| Agent | What it does |
|-------|-------------|
| **M1 — Crawl** | Discovers PDF URLs via 5 strategies: Firecrawl, Tavily, SEC EDGAR, BeautifulSoup, Regex |
| **M2 — Download** | Downloads each PDF, checks for duplicates via SHA-256 hash |
| **M3 — OCR** | Extracts text; runs Tesseract OCR on scanned/image PDFs |
| **M4 — Classify** | Assigns `FINANCIAL\|TYPE` or `NON_FINANCIAL\|TYPE` from 18 document types |
| **M5 — WebWatch** | Snapshots IR pages, detects added/deleted/changed pages |
| **M6 — Extract** | LLM extracts 15-field financial or 13-field non-financial metadata |
| **M7 — Excel** | Generates 7-sheet styled Excel workbook |
| **M8 — Email** | Sends HTML digest email via Office365 SMTP |

### Running the pipeline

**From the Dashboard UI** → click **▶ Start Pipeline** (requires Redis + Celery)

**Via API (no Celery needed)**:
```bash
# Run for one company
curl -X POST http://localhost:8080/api/jobs/run-direct/1

# Run for all active companies
curl -X POST http://localhost:8080/api/jobs/run-all-direct
```

**Via Celery (production)**:
```bash
# Start worker
celery -A app.celery_app worker --loglevel=info

# Start beat scheduler (hourly WebWatch + daily digest)
celery -A app.celery_app beat --loglevel=info
```

---

## 📄 API Reference

Full interactive docs: **http://localhost:8080/docs**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/companies/` | List all companies |
| POST | `/api/companies/` | Add single company |
| POST | `/api/companies/bulk` | Add multiple companies |
| DELETE | `/api/companies/{id}` | Delete company |
| PATCH | `/api/companies/{id}/toggle` | Toggle active/inactive |
| GET | `/api/documents/` | List documents (filters: company_id, doc_type, status) |
| GET | `/api/documents/metadata/` | List all extracted metadata |
| GET | `/api/documents/changes/` | Document change log |
| GET | `/api/webwatch/snapshots` | Page snapshots |
| GET | `/api/webwatch/changes` | WebWatch page changes |
| POST | `/api/jobs/run-direct/{company_id}` | Run pipeline (no Celery) |
| POST | `/api/jobs/run-all-direct` | Run all companies (no Celery) |
| POST | `/api/jobs/run/{company_id}` | Queue via Celery |
| POST | `/api/jobs/run-all` | Queue all via Celery |

---

## 📋 Adding Companies

**Single**: Companies page → tab "Single Company" → fill name + URL → Add

**Multiple at once**: Companies page → tab "Multiple Companies" → fill the form rows → Add All

**CSV Upload**: Companies page → tab "Bulk CSV Upload"

CSV format:
```csv
company_name,website_url,crawl_depth
ICICI Bank,https://www.icicibank.com/investor-relations,3
Infosys,https://www.infosys.com/investors,3
TCS,https://www.tcs.com/investors,3
```

> ⚠️ Always enter **Company Name** as a readable name (e.g. `ICICI Bank`), not a domain (`www.icici.bank.in`). The crawler auto-cleans domain-style names but proper names give better search results.

---

## 🗂 Document Classification

Documents are classified into **18 types** in two categories:

**Financial** (10 types): `ANNUAL_REPORT · QUARTERLY_RESULTS · HALF_YEAR_RESULTS · EARNINGS_RELEASE · INVESTOR_PRESENTATION · FINANCIAL_STATEMENT · IPO_PROSPECTUS · RIGHTS_ISSUE · DIVIDEND_NOTICE · CONCALL_TRANSCRIPT`

**Non-Financial** (8 types): `ESG_REPORT · CORPORATE_GOVERNANCE · PRESS_RELEASE · REGULATORY_FILING · LEGAL_DOCUMENT · HR_PEOPLE · PRODUCT_BROCHURE · OTHER`

Stored as `CATEGORY|TYPE`, e.g. `FINANCIAL|ANNUAL_REPORT`.

---

## 🛠 Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Cannot connect to backend (port 8080)` | Run `uvicorn` in the `backend/` directory |
| `Celery not available: 503` | Use `/jobs/run-direct` endpoints; or start Redis + Celery worker |
| `[EDGAR] Could not resolve CIK` | EDGAR only indexes US-registered companies; non-US companies use Tavily + BS4 strategies |
| `[FIRECRAWL] Skipped (insufficient credits)` | Normal — other 4 strategies still run |
| PDF count = 0 | Check the company URL points to an investor-relations page with PDFs |
| DB tables missing | Backend auto-creates tables on startup via `models.Base.metadata.create_all` |

---

## 🔐 Security

- All secrets in `backend/.env` — **never committed** (in `.gitignore`)
- `.env.example` provided as a template
- CORS allows all origins (restrict in production)

---

## 📦 Tech Stack

`FastAPI` · `LangGraph` · `SQLAlchemy` · `PostgreSQL` · `Celery` · `Redis` · `Azure OpenAI` · `Streamlit` · `Pandas` · `openpyxl` · `Firecrawl` · `Tavily` · `BeautifulSoup4` · `pdfminer` · `Tesseract OCR`