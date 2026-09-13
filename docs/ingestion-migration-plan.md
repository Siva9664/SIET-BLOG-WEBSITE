# Deterministic Ingestion Migration Plan

## Audit scope

This audit covers the committed document intelligence, magazine, and template
engine code. No separate architecture document was present in the repository,
so the target design below follows the agreed ingestion, analysis, and
training-data workflow.

## Classification

| Area | Decision | Reason |
| --- | --- | --- |
| documents/models.py | Keep | SourceDocument and DocumentChunk are the established persistence and provenance contract. |
| documents/provenance.py | Keep | Retrieval citations already expose document, page, section, and offsets. |
| documents/chunker.py | Rewrite | Reworked to preserve correct offsets for repeated paragraphs and long windows. |
| documents/parser.py | Rewrite as adapter | Now delegates to the structured ingestion layer while preserving its public span API. |
| documents/router.py | Keep and extend | Existing upload and RAG endpoints remain; upload now accepts PPTX and HTML and reports structure. |
| documents/embeddings.py and retriever.py | Keep for transition | They are independent of parsing. Runtime provider calls should be replaced only after a configured local embedding endpoint is available. |
| documents/reranker.py | Rewrite after local model deployment | Its optional LLM rerank invokes the legacy magazine AI service. The deterministic fallback remains viable until the workstation service replaces it. |
| template_engine/analyzer.py | Keep, scope explicitly | It analyses DOCX output templates and should not be used as a general source-document analyzer. |
| template_engine/composer.py and router.py | Keep | They serve the separate output-template workflow. Replace the hard-coded local template fallback before deployment. |
| magazine/file_parser.py | Rewrite in a later adapter pass | It duplicates PDF and DOCX extraction and persists extracted image binaries. It needs a media-storage adapter before it can safely use shared ingestion. |
| magazine/ai_service.py and orchestrator.py | Keep until replacement | These are legacy Gemini/OpenAI generation paths. Do not remove them until a trained workstation model endpoint has been integrated and accepted. |
| magazine/pipeline.py, renderer.py, validator.py, visual_analyzer.py | Keep | These provide issue rendering and validation rather than source document parsing. |

No module is deleted in this change. Removing a live path before its local
replacement is accepted would break the current magazine workflow.

## Target flow

1. Ingestion parses PDF, DOCX, PPTX, HTML, or text into ordered blocks plus
   image references.
2. Analysis derives heading hierarchy, table summaries, and image-caption
   links without model calls.
3. The compatibility adapter converts those blocks into the existing
   page-aware chunks used by the RAG persistence and retrieval APIs.
4. The dataset script serializes chunks with provenance, calls Gemini once per
   chunk only when a key is supplied, and rejects candidates whose evidence is
   not found in the source.
5. A deterministic 25 percent review sample is emitted for human review.
   Final JSONL generation refuses to proceed until enough reviews are marked
   completed.

## Local dataset workflow

Place real source documents in a private directory outside version control,
for example backend/training-data/sources. Source documents and generated
JSONL must not be committed.

    cd backend
    PYTHONPATH=. .venv/bin/python scripts/prepare_fact_dataset.py prepare-chunks training-data/sources --output training-data/source_chunks.jsonl
    PYTHONPATH=. .venv/bin/python scripts/prepare_fact_dataset.py generate-candidates --chunks training-data/source_chunks.jsonl --output training-data/fact_candidates.jsonl
    PYTHONPATH=. .venv/bin/python scripts/prepare_fact_dataset.py prepare-review --candidates training-data/fact_candidates.jsonl --output training-data/fact_review.jsonl --fraction 0.25

Review each selected record by setting review.status to completed and every
fact decision to accept, reject, or edit. An edited fact must retain exact
evidence copied from its source passage.

    PYTHONPATH=. .venv/bin/python scripts/prepare_fact_dataset.py finalize --candidates training-data/fact_candidates.jsonl --reviews training-data/fact_review.jsonl --output training-data/fact_extraction.jsonl

Finalize writes fact_extraction.jsonl alongside deterministic train,
validation, and evaluation JSONL splits. These outputs are training inputs,
not quality or benchmark results.

## Workstation handoff

After the review gate passes, transfer the finalized directory to the
workstation with the existing SSH configuration. Fine-tuning happens only on
the RTX 5070 workstation; the laptop workflow performs parsing, review, and
one-off cloud dataset generation only.
