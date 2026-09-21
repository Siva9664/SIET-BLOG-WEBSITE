# SIET News / Articles / Magazine Portal Backend

This repository contains the backend implementation for the SIET News / Articles / Magazine Portal. It is structured using Clean Architecture and Vertical-Slice Architecture principles with FastAPI, Async SQLAlchemy, PostgreSQL, and Pydantic v2.

---

## 🛠 Tech Stack
- **FastAPI**: Asynchronous web framework.
- **SQLAlchemy (Async)**: Asynchronous ORM with `asyncpg`.
- **Alembic**: Async database migration engine.
- **PostgreSQL**: Primary SQL Database.
- **Pydantic v2**: Data validation and settings management (`ConfigDict`).
- **Pytest Async**: Full test suite with isolated `db_session` fixture.
- **APScheduler**: Automated background news sync and archiving jobs.
- **Meilisearch / R2**: Search indexer and cloud storage integrations (optional).

---

## 📂 Project Structure
The project follows a Clean Vertical-Slice architecture layout:
```
backend/
├── app/
│   ├── core/             # Application lifecycle, config, DB engine, logging, security, scheduler
│   ├── shared/           # Common middleware, pagination utility, custom responses, errors, base repository
│   ├── infrastructure/   # Interfaces for email provider, storage, and search
│   └── modules/          # Vertical slices
│       ├── admin/        # Admin control panel & user management
│       ├── articles/     # Academic articles & publication logic
│       ├── auth/         # Complete Authentication flow (JWT, OAuth/Password hashing)
│       ├── domains/      # News & Article domain categories
│       ├── health/       # Health checks for system resources (DB, storage, search)
│       ├── magazine/     # Student magazine entries & project showcases
│       ├── news/         # News items & RSS aggregation
│       └── tags/         # Content tagging and categorization
├── scripts/              # Operational CLI management scripts
├── tests/                # Pytest async test suite (20/20 passing)
└── docker-compose.yml    # Container orchestration runtime
```

---

## 📐 Architecture & Communication Rules
- **Vertical Slices**: Each module boundary contains all layers (`Router`, `Service`, `Repository`, `Models`, `Schemas`) necessary for its domain.
- **Layering Constraints**:
  - `Router` calls `Service` only. Router never directly queries the database.
  - `Service` executes business logic and calls `Repository` or other module services.
  - `Repository` executes database query operations. A repository never calls another repository.
  - Cross-module communication always routes through another module's `Service` dependency.

---

## 🚀 Setup & Running Locally

### 1. Requirements
- Python 3.11+
- PostgreSQL database

### 2. Configure Environment
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Ensure your `DATABASE_URL` is set in `.env`:
```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/siet_db
ENV=development
```

### 3. Database Migration & Initialization
From the `backend/` directory, run:
```bash
# Activate virtual environment
source venv/bin/activate

# Apply Alembic schema migrations
PYTHONPATH=. ./venv/bin/alembic upgrade head

# Synchronize database schema columns
PYTHONPATH=. ./venv/bin/python scripts/sync_db.py

# Verify / Create default Super Admin user (admin@siet.ac.in)
PYTHONPATH=. ./venv/bin/python scripts/check_admin.py

# (Optional) Seed sample records & fetch RSS news
PYTHONPATH=. ./venv/bin/python scripts/seed.py
PYTHONPATH=. ./venv/bin/python scripts/fetch_todays_news.py
```

### 4. Start Development Server
```bash
PYTHONPATH=. ./venv/bin/uvicorn app.main:app --reload --port 8000
```
- **API Base URL**: `http://localhost:8000/api/v1`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`
- **ReDoc API Documentation**: `http://localhost:8000/redoc`

### 5. Run Testing Suite
```bash
PYTHONPATH=. ./venv/bin/pytest tests -v
```

---

## 🔐 Administrative User Accounts

When the backend starts up or when `scripts/check_admin.py` is executed, the initial super administrator account is guaranteed to exist:
- **Email**: `admin@siet.ac.in`
- **Password**: Configured securely via the `ADMIN_INITIAL_PASSWORD` environment variable. Never expose default credentials in production.
- **Role**: `SUPER_ADMIN`

---

## 🛠 Useful Management Commands

| Action | Command |
| :--- | :--- |
| **Run Pytest** | `PYTHONPATH=. ./venv/bin/pytest tests -v` |
| **Run Alembic Migrations** | `PYTHONPATH=. ./venv/bin/alembic upgrade head` |
| **Check Admin User** | `PYTHONPATH=. ./venv/bin/python scripts/check_admin.py` |
| **Sync DB Columns** | `PYTHONPATH=. ./venv/bin/python scripts/sync_db.py` |
| **Seed Database** | `PYTHONPATH=. ./venv/bin/python scripts/seed.py` |
| **Fetch Latest News** | `PYTHONPATH=. ./venv/bin/python scripts/fetch_todays_news.py` |
| **Test Login Script** | `PYTHONPATH=. ./venv/bin/python scripts/test_login.py` |
| **Qwen3 14B Smoke Test** | `PYTHONPATH=. ./venv/bin/python scripts/smoke_test_qwen.py` |

---

## 🤖 Editorial Intelligence (Local Qwen3 14B & Fallback Providers)

The backend features an Editorial Intelligence service layer located in `app/infrastructure/ai/` designed for document understanding, classification, summarization, rewriting, headline generation, photo captioning, and structured editorial JSON generation.

### 1. Architectural Guardrails
- **Physical Layout Isolation**: Qwen acts exclusively as the editorial intelligence model. Physical magazine layout rendering remains deterministic and template-driven.
- **Strict Grounding Rule**: Generation is constrained to supplied source and RAG passages. The provider strictly forbids hallucinating or inventing names, dates, stats, or events. Missing fields must be represented as null/empty.
- **Structured Output**: Native JSON schema constrained decoding with Pydantic validation and bounded retry.
- **Observable Fallback**: Dynamic routing where primary provider (`qwen`) failures or timeouts observably fall back to the configured fallback provider (`gemini` or `openai`), and finally to deterministic rule-based generators without crashing.

### 2. Local Ollama & Model Setup
Install Ollama and pull the required Qwen3 14B model:
```bash
# Start Ollama service (runs on port 11434 by default)
ollama serve

# Verify or pull Qwen3 14B
ollama run qwen3:14b
```

### 3. Environment Configuration
Configure the AI provider in `.env`:
```env
# AI & Editorial Intelligence Provider Settings
AI_PROVIDER="qwen"                  # Primary provider: qwen, gemini, openai
AI_FALLBACK_PROVIDER="gemini"        # Fallback provider: gemini, openai, none
OLLAMA_BASE_URL="http://localhost:11434"
OLLAMA_MODEL="qwen3:14b"
OLLAMA_TIMEOUT=60.0

# Optional Fallback API Keys
GEMINI_API_KEY=""                    # Optional fallback Google Gemini API Key
GEMINI_MODEL="gemini-1.5-flash"
OPENAI_API_KEY=""                    # Optional fallback OpenAI API Key
OPENAI_MODEL="gpt-3.5-turbo"
```

### 4. Running AI Tests & Smoke Test
```bash
# Run AI unit tests (mocked HTTP, no live server required)
PYTHONPATH=. ./venv/bin/pytest tests/ai/ -v

# Run live Qwen3 14B smoke test with synthetic college event report
PYTHONPATH=. ./venv/bin/python scripts/smoke_test_qwen.py
```
