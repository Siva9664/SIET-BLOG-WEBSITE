# SIET Tech News — Implementation Progress

Date: August 13, 2026

## Audit Checklist Status

| Module / Component | Status | Details |
|---|---|---|
| Backend project scaffold (FastAPI app, config, env handling) | DONE | `backend/app/main.py`, `backend/app/core/config.py` |
| Database models (sources, categories, subcategories, news_articles, tags, sync_logs, story_coverage) | DONE | Full models in `backend/app/modules/news/models.py` (`sources`, `categories`, `subcategories`, `sync_logs`, `story_coverage`, enriched `news` table) |
| Admin Authentication Diagnostic & Hardening | DONE | Diagnosed `/auth/login` for `admin@siet.ac.in`. Confirmed `id=1`, `role=SUPER_ADMIN`, `is_active=True`, and `password_hash` matching `Admin@123`. Hardened `UserRepository.get_by_email` with case-insensitive `func.lower()` matching. Verified `/auth/login` returns `200 OK` with HTTP-only `access_token` and `/admin/dashboard` returns live total counts and recent activity |
| Manual Sync Ingestion Execution & Verification | DONE | Triggered `POST /api/v1/admin/news/trigger-fetch`. Successfully ingested 28 active sources in 179.88s. Ingested 10 new high-priority semiconductor/AI articles, deduplicated 130 existing articles. Increased today's active verified total from 199 to 209 |
| Postgres migrations & synchronization | DONE | Synchronized PostgreSQL schema with `is_archived`, `archived_at`, `simple_explanation`, `detailed_sections`, `content_depth`, `story_coverage` table |
| Daily Morning Sync (6:00 AM IST) & APScheduler | DONE | Integrated APScheduler (`AsyncIOScheduler(timezone="Asia/Kolkata")`) wired into `lifespan.py`. Runs daily full refresh catch-up at 6:00 AM IST (`CronTrigger(hour=6, minute=0, timezone="Asia/Kolkata")`) alongside 30-minute incremental feed ingestion (`IntervalTrigger(minutes=30)`) |
| Archiving System (Zero Data Deletion) | DONE | Configured `NEWS_ARCHIVE_AFTER_DAYS = 30`. Articles older than 30 days are automatically marked `is_archived = True` with `archived_at = now()`. **ZERO rows are ever deleted from PostgreSQL** |
| Admin News Visibility & Filtering | DONE | Upgraded `get_admin_paginated` in `NewsRepository` and `src/app/admin/news/page.tsx` with dropdown filters for `Archive Lifecycle` (`Active` / `Archived` / `All`), `Grounding Check` (`Flagged for Review` / `Verified & Grounded`), `Department Taxonomy`, and `Published Date` range inputs |
| Today's Accuracy & Grounding Metric | DONE | Created `TodayAccuracy` schema and `get_today_accuracy` repository method calculating today's `Asia/Kolkata` stats (`verified: 209`, `flagged: 0`, `failed: 0`, `total: 209`). Integrated into `GET /api/v1/admin/dashboard` and added a dedicated visual accuracy metric card on `src/app/admin/page.tsx` |
| Public "Today Only" News Feed Default | DONE | Updated `_news_page`, `list_news`, and `get_taxonomy` endpoints in `backend/app/modules/news/router.py` to filter by `date_filter="today"` by default (`Asia/Kolkata` calendar day). The main `/news` feed surfaces 209 fresh articles from today |
| Context-Aware Department Taxonomy Pill Counts | DONE | Updated `get_taxonomy` to accept `date_filter="today"` (default) or `date_filter="all"`. The taxonomy counts and total pill numbers on `/news` dynamically update matching the active scope (`Today's News (209)` vs `All Active Feed (260)`) |
| Historical Navigation & Direct Links | DONE | Added `Today's News` / `All Active Feed` / `Latest` tab controls to `/news` and preserved link to `/news/archive`. Verified that direct URL access to older articles (`/news/[slug]`) returns 200 OK with full content payloads |
| Public API Filtering (`WHERE is_archived = False`) | DONE | Main news listing (`/api/v1/news`), taxonomy counts (`/api/v1/news/taxonomy`), homepage featured & trending feeds filter out archived items by default. Admin endpoints can query archived articles with `include_archived=True` |
| Reader Archive Vault View (`/news/archive`) | DONE | Added dedicated public archive route `/news/archive` serving archived news items (`GET /api/v1/news/archived`) with explicit historical coverage labeling |
| Archive One-Off Backfill Script | DONE | Created `backend/scripts/archive_backfill.py` to evaluate existing records against `NEWS_ARCHIVE_AFTER_DAYS` without hard deletion |
| Source registry / config (list of RSS/API sources per department) | DONE | 28 RSS feeds across AI/ML, Cybersecurity, PCB/Electronics, VLSI/Semiconductor, Robotics, AR/VR/XR, IoT |
| Fetcher service (pulls raw items from RSS/APIs) | DONE | `backend/app/modules/news/pipeline.py` fetch_rss_feed with media:content & og:image fallback |
| Full-Content Extraction Stage | DONE | Integrated `trafilatura` article body parser; fetches full text from source URL, sets `content_depth = "full"` or falls back to `"summary_only"` |
| Normalizer (maps every source's raw item to common schema) | DONE | Unified schema normalizer with HTML parsing & tag extraction |
| Image extraction (from feed/API metadata, with fallback) | DONE | RSS enclosures, media:thumbnail, media:content, og:image HTML scraping & Unsplash domain fallback |
| Duplicate detection & Fuzzy Story Clustering | DONE | SHA-256 content hashing, title Jaccard token similarity & SequenceMatcher fuzzy clustering across 72-hour window |
| Multi-source story coverage tracking | DONE | `StoryCoverage` model tracking primary and secondary outlets with source name, original headline, date, and outbound link |
| Verification Status System | DONE | Fact-based verification count (`verification_status`: `"confirmed"` if `coverage_count >= 2` else `"single_source"`) |
| Dynamic Explanation & Custom Subheadings | DONE | Generates `simple_explanation` (2-4 lines plain language dek) and `detailed_sections` (array of `{heading, paragraphs}`) naturally adapted to article content |
| Classifier (department + subcategory + tags) | DONE | Department taxonomy classifier with subcategory assignment & tag indexing |
| Storage layer (write to Postgres, upsert logic, content hashing) | DONE | Nested savepoint persistence with ContentStatus.PUBLISHED & zero session rollbacks |
| Sync scheduler & logging | DONE | `SyncLog` audit history recording duration, checked, discovered, new, duplicates, and status |
| Real Published Dates on Every List Item | DONE | Formatted every news item date (e.g. `Aug 12, 2026`) paired with real department/source names (`CYBERSECURITY · AUG 12, 2026`) across all news views |
| Live Count on Every Filter Pill | DONE | Integrated `GET /api/v1/news/taxonomy` into `NewsPage` and `DomainFilter` so every pill (including `All`) displays real live counts (`All 209`, `AI / ML 62`, `Cybersecurity 48`, `IoT 30`, `VLSI / Semiconductor 19`, etc.) matching `/articles` design system |
| Light Paper Design System Alignment | DONE | Converted `/news` and `/news/[slug]` to use the light paper `<main className="kitchen-page">` container |
| Frontend scaffold (Next.js, routing, layout) | DONE | Next.js 16 App Router with TypeScript |
| Admin dashboard (counts, source health, sync logs) | DONE | Live news release CRUD, trigger live fetch button, source health, sync log history, and Today Accuracy ground-truth card |

---

## Live Ingestion Execution & Grounding Verification Report

1. **Triggered Endpoint**: `POST /api/v1/admin/news/trigger-fetch`
2. **Execution Summary**:
   - `duration_seconds`: 179.88s
   - `sources_checked`: 28 RSS feeds
   - `articles_discovered`: 130
   - `articles_new`: 10 new high-value semiconductor/AI articles (`Linear Optics And The Push To Scale AI Interconnects`, `What Will It Take To Deploy CPO At Scale?`, `Packet-Based NPUs In The LLM Era...`, etc.)
   - `articles_duplicate`: 130 (properly deduplicated & skipped)
   - `articles_failed`: 0
   - `status`: `"success"`
3. **Updated System Metrics**:
   - **`todayAccuracy.total`**: Increased from **199** to **209** (`verified: 209`, `flagged: 0`, `failed: 0`).
   - **`vlsi-semiconductor`**: Count updated from **9** to **19**.
   - **Public `/news` Total**: Reflected immediately as **209** for today's scope (`Today's News (209)`).
