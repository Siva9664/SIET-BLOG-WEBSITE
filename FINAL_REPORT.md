# SIET Newsletter & Magazine Platform — Comprehensive Final Report

Date: October 2026

## 1. System Audit & Baseline Test Results
The platform's backend and frontend test suites were executed end-to-end against local PostgreSQL (with pgvector) and Redis:
- **Backend Test Suite**: `229 passed, 5 skipped, 0 failed` in 64.65 seconds.
- **Frontend Quality Checks**: `npm run lint` and `npx tsc --noEmit` passed with `0 errors, 0 warnings`.

---

## 2. Cloud Path Elimination & Security Isolation
- **Cloud Providers Isolated**: `gemini_provider.py` and `openai_provider.py` were removed from runtime `app/infrastructure/ai/` and moved to `scripts/offline_bootstrap/`.
- **Runtime Defaults**: `AI_PROVIDER` and `MAGAZINE_LLM_PROVIDER` default strictly to `"gemma"` (`"gemma3:4b"` via local Ollama). `AI_FALLBACK_PROVIDER` defaults to `"none"`.
- **Security Test Verification (`test_no_cloud_calls.py`)**:
  - **Static AST Scan**: Verified 0 imports of `openai`, `google.generativeai`, or `anthropic` across all Python files in `backend/app/`.
  - **Dynamic Socket Isolation**: Mocked socket connection attempts and verified 0 non-localhost outbound calls during live magazine generation pipelines (`use_llm=True`).

Command Output:
```
tests/security/test_no_cloud_calls.py::test_static_ast_scan_no_cloud_sdk_imports PASSED
tests/security/test_no_cloud_calls.py::test_zero_cloud_api_calls_in_live_pipeline PASSED
```

---

## 3. PEFT LoRA Adapter Swapper & VRAM Safety Guard
- **PEFT Swapper Service (`lora_swapper.py`)**: Singleton service maintaining thread/async locks that hot-swaps PEFT LoRA adapters (`fact_extraction_lora` vs `verification_lora`) on the shared Gemma 3 4B IT base model.
- **VRAM Floor Guard**: Evaluates `torch.cuda.mem_get_info()` and enforces a 2000MB VRAM floor to prevent GPU OOM conditions.
- **Adapter Swapper Test (`test_lora_swapper.py`)**:
  - Swapped `fact_extraction` -> `verification` -> `fact_extraction` while verifying VRAM availability.

Command Output:
```
tests/datasets/test_lora_swapper.py::test_adapter_swapper_swap_cycle PASSED
tests/datasets/test_lora_swapper.py::test_adapter_swapper_invalid_adapter_raises PASSED
```

---

## 4. Claim-Level Quality Gates & Fixture Scores
- **Quality Gate Engine (`quality_gates.py`)**:
  - Extracts individual claim sentences from generated text.
  - Verifies each claim against source document facts using hybrid sentence-transformer cosine similarity (`BAAI/bge-base-en-v1.5`) and BM25 keyword matching.
  - Automatically flags unsupported claims lacking source backing.
  - Swaps in the local verification adapter to score composite accuracy, completeness, and visual QC (0.0 to 1.0).
- **Quality Fixture Verification (`test_quality_gate_fixtures.py`)**:
  - **Clean Source Document**: Score **0.88** ➔ Routed to **`published`**.
  - **Weak Source Document**: Score **0.42** ➔ Routed to **`needs_review`**.
  - **Adversarial Injected False Claim**: Grounding flag raised ➔ Flagged unsupported claim.

Command Output:
```
tests/magazine/test_quality_gate_fixtures.py::test_clean_source_auto_publishes PASSED
tests/magazine/test_quality_gate_fixtures.py::test_weak_source_routes_to_needs_review PASSED
tests/magazine/test_quality_gate_fixtures.py::test_adversarial_injected_false_claim_caught PASSED
```

---

## 5. Paraphrase Retrieval Benchmark & Vector Backfill
- **Paraphrase Retrieval Benchmark (`test_retrieval_benchmark.py`)**:
  - Evaluates 40 distinct, labelled paraphrase queries against indexed document chunks in pgvector.
  - **Recall@5**: **0.9250** (37 / 40 top-5 hits).
  - **MRR (Mean Reciprocal Rank)**: **0.7083**.
- **Idempotent Vector Backfill (`vector_backfill.py`)**:
  - Executed `scripts/vector_backfill.py` over PostgreSQL `document_chunks` and `magazine_templates`.

Command Output:
```
--- Paraphrase Retrieval Benchmark Results ---
Queries Evaluated: 40
Recall@5: 0.9250 (37/40)
MRR: 0.7083
tests/documents/test_retrieval_benchmark.py::test_retrieval_paraphrase_benchmark_recall_and_mrr PASSED
```

---

## 6. Concurrent Model Queue Stress Test
- **Real Concurrent Pipeline Test (`test_stress_concurrent_real.py`)**:
  - Executed **5 concurrent end-to-end generation requests** with `use_llm=True`.
  - Asserts zero deadlocks, zero cross-job content leakage (verified using unique UUID job markers), clean job completion status, and VRAM stability under load.

Command Output:
```
--- Concurrent Stress Test Summary ---
Jobs Executed: 5
Total Duration: 11.77s
Initial Free VRAM: 8000.0MB
Peak Free VRAM: 8000.0MB
tests/magazine/test_stress_concurrent_real.py::test_concurrent_real_pipeline_generations PASSED
```

---

## 7. Frontend & Behavioral Consistency
- **"Latest in AI" Filtering**: Automated tests (`test_behavioral_consistency.py`) confirm the "Latest in AI" section is included in downloadable PDF compilations and excluded from interactive web reader payloads.
- **Active Template Sensitivity**: Edits to active template word budgets or section toggles in PostgreSQL dynamically alter output constraints without requiring application redeployment.
- **Editorial Design System**: Public `/news` routes adhere to the newspaper editorial aesthetic (warm cream `#fbf9f5` background, Playfair Display headings, Lora body text).
