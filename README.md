# SIET News / Articles / Magazine Portal

Welcome to the **SIET News / Articles / Magazine Portal** codebase for **Sri Shakthi Institute of Engineering and Technology**. This repository contains a Next.js 15 frontend and a FastAPI (Python 3.12) backend using Vertical-Slice Architecture and PostgreSQL.

---

## 🏗 System Architecture Overview

```
SIET-BLOG-WEBSITE/
├── src/                # Next.js 15 App Router Frontend
├── backend/            # FastAPI Async Backend (Python 3.12)
│   ├── app/
│   │   ├── core/       # Settings, Database Engine, Security, Lifespan, Scheduler
│   │   ├── modules/    # Vertical Slices (admin, analysis, articles, auth, contact, datasets, documents, domains, engagement, health, ingestion, internal, magazine, media, news, search, settings, tags, template_engine)
│   │   ├── infrastructure/ # External services (Email, Storage, Search)
│   │   └── shared/     # Base repositories, middleware, pagination, types
│   ├── scripts/        # Operational CLI scripts (check_admin, seed, sync_db, fetch_todays_news)
│   └── tests/          # Pytest Async Test Suite
├── public/             # Static Assets & Fallback Logo
└── package.json        # Frontend Dependencies & Scripts
```

---

## 🚀 Quick Start Guide

### Prerequisites
- **Node.js**: v18.0.0+
- **Python**: 3.11+
- **PostgreSQL**: Running locally or via Docker

---

## 🔹 Backend Setup & Running (FastAPI)

### 1. Navigate & Setup Environment
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` inside `backend/`:
```bash
cp .env.example .env
```
Ensure your database connection URL is properly configured:
```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/siet_db
ENV=development
```

### 3. Initialize & Synchronize Database
Run database schema synchronization and default admin creation:
```bash
# Apply schema migrations
PYTHONPATH=. ./venv/bin/alembic upgrade head

# Synchronize missing columns and tables
PYTHONPATH=. ./venv/bin/python scripts/sync_db.py

# Verify / Create default Super Admin user (admin@siet.ac.in)
PYTHONPATH=. ./venv/bin/python scripts/check_admin.py

# (Optional) Seed sample data and initial tech news
PYTHONPATH=. ./venv/bin/python scripts/seed.py
PYTHONPATH=. ./venv/bin/python scripts/fetch_todays_news.py
```

### 4. Run Backend Development Server
```bash
PYTHONPATH=. ./venv/bin/uvicorn app.main:app --reload --port 8000
```
- **API Base URL**: `http://localhost:8000/api/v1`
- **Swagger Documentation**: `http://localhost:8000/docs`
- **ReDoc Documentation**: `http://localhost:8000/redoc`

### 5. Running the Backend Test Suite
The testing suite executes asynchronously against an isolated database environment:
```bash
cd backend
PYTHONPATH=. ./venv/bin/pytest tests -v
```

---

## 🔹 Frontend Setup & Running (Next.js)

### 1. Install Dependencies
Run from the root project directory:
```bash
npm install
```

### 2. Configure Environment Variables
Create `.env.local` in the root directory:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

### 3. Run Development Server
```bash
npm run dev
```
- **Frontend App URL**: `http://localhost:3000`

### 4. Code Quality & Linting
```bash
npm run lint
```

---

## 🗝 Operational CLI Scripts

All CLI scripts are executed from the `backend/` folder with `PYTHONPATH=.`:

| Script | Command | Purpose |
| :--- | :--- | :--- |
| **Check Admin** | `PYTHONPATH=. ./venv/bin/python scripts/check_admin.py` | Validates & creates initial Super Admin account |
| **Sync Database** | `PYTHONPATH=. ./venv/bin/python scripts/sync_db.py` | Ensures all schema tables and columns are created |
| **Seed Data** | `PYTHONPATH=. ./venv/bin/python scripts/seed.py` | Seeds default administrative users and domain tags |
| **Fetch News** | `PYTHONPATH=. ./venv/bin/python scripts/fetch_todays_news.py` | Ingests latest tech RSS news feeds into PostgreSQL |

---

## 🔐 Administrative User Accounts

Initial administrative accounts can be verified or initialized via `scripts/check_admin.py`:
- **Default Email**: `admin@siet.ac.in`
- **Password**: Configured securely via the `ADMIN_INITIAL_PASSWORD` environment variable or set during deployment. Default or hardcoded production passwords must never be used.
- **Role**: `SUPER_ADMIN`

---

## 🧪 Testing Summary

- **Backend Pytest Suite**: 137 test cases passing across `auth`, `admin`, `health`, `core`, `engagement`, `documents`, `ingestion`, `datasets`, and `magazine` modules.
- **Frontend Linting**: ESLint v9 configuration verified clean (0 errors, 0 warnings).
- **Frontend Type Checking**: TypeScript `tsc --noEmit` verified clean.
- **Frontend Production Build**: 30/30 Next.js routes compiled cleanly.
