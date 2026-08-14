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

# Verify / Create default Super Admin user (admin@siet.ac.in / Admin@123)
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

## 🔐 Default Super Admin Credentials

When the backend starts up or when `scripts/check_admin.py` is executed, the following default super administrator account is guaranteed to exist:
- **Email**: `admin@siet.ac.in`
- **Password**: `Admin@123`
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
