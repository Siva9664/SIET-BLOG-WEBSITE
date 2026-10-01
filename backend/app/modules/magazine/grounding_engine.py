"""Complete Document Grounding Engine and Section-Specific RAG Retriever.

Chunks entire documents with page, section, and char offset provenance.
Provides hybrid semantic + keyword retrieval for every magazine section.
Guarantees zero reliance on head-truncation (no [:4500]).
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.logging import logger
from app.modules.documents.chunker import chunk_document_spans
from app.modules.documents.embeddings import _cosine_similarity, embed_texts


@dataclass
class GroundedChunk:
    chunk_id: int
    text: str
    page_number: int
    section_label: str
    char_start: int
    char_end: int
    source_filename: str
    embedding: Optional[List[float]] = None
    score: float = 0.0
    semantic_score: float = 0.0
    keyword_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if "embedding" in d:
            del d["embedding"]
        return d


def _compute_keyword_overlap(query: str, text: str) -> float:
    """Calculates term overlap score between query and candidate text."""
    clean_q = re.sub(r"[^\w\s]", " ", query.lower())
    clean_text = re.sub(r"[^\w\s]", " ", text.lower())

    q_terms = [t for t in clean_q.split() if len(t) > 2]
    if not q_terms:
        return 0.0

    matched = sum(1 for t in q_terms if t in clean_text)
    coverage = matched / len(q_terms)
    phrase_bonus = 0.3 if clean_q in clean_text else 0.0
    return min(1.0, coverage * 0.7 + phrase_bonus)


class DocumentGroundingIndex:
    """
    In-memory / DB-grounded index for an uploaded document.
    Chunks the full document, computes embeddings, and provides section-scoped retrieval.
    """

    def __init__(self, filename: str = "document"):
        self.filename = filename
        self.chunks: List[GroundedChunk] = []
        self._indexed = False

    @classmethod
    def from_document_data(
        cls,
        extracted_text: str,
        filename: str = "document",
        spans: Optional[List[Dict[str, Any]]] = None,
        target_chunk_size: int = 400,
        overlap_size: int = 60,
    ) -> "DocumentGroundingIndex":
        """
        Creates an index from document spans or raw text, chunking the ENTIRE document.
        Never truncates text.
        """
        index = cls(filename=filename)

        raw_spans = spans or []
        if not raw_spans:
            # If no structured spans provided, create span from full text
            raw_spans = [{
                "page_number": 1,
                "section_label": "main_content",
                "text": extracted_text,
                "char_start": 0,
                "char_end": len(extracted_text),
            }]

        doc_chunks = chunk_document_spans(
            raw_spans,
            target_chunk_size=target_chunk_size,
            overlap_size=overlap_size,
        )

        for idx, c in enumerate(doc_chunks):
            g_chunk = GroundedChunk(
                chunk_id=idx + 1,
                text=c["text"],
                page_number=c.get("page_number", 1),
                section_label=c.get("section_label") or f"section_{idx + 1}",
                char_start=c.get("char_start", 0),
                char_end=c.get("char_end", len(c["text"])),
                source_filename=filename,
            )
            index.chunks.append(g_chunk)

        logger.info(
            f"[GroundingIndex] Built index with {len(index.chunks)} chunks from full document "
            f"'{filename}' ({len(extracted_text)} characters, {max((c.page_number for c in index.chunks), default=1)} pages)."
        )
        return index

    async def index_embeddings(self) -> None:
        """Computes embeddings for all chunks in the document."""
        if not self.chunks or self._indexed:
            return

        texts = [c.text for c in self.chunks]
        try:
            vectors = await embed_texts(texts)
            for c, vec in zip(self.chunks, vectors):
                c.embedding = vec
            self._indexed = True
            logger.info(f"[GroundingIndex] Indexed {len(vectors)} chunk embeddings for '{self.filename}'.")
        except Exception as e:
            logger.warning(f"[GroundingIndex] Vector embedding failed ({e}); falling back to lexical retrieval.")
            self._indexed = False

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.10,
        filter_section: Optional[str] = None,
    ) -> List[GroundedChunk]:
        """
        Retrieves top_k relevant chunks using hybrid semantic and keyword search.
        Preserves page numbers, source filename, and character offsets.
        """
        if not self.chunks:
            return []

        # Ensure embeddings are ready if available
        if not self._indexed:
            await self.index_embeddings()

        query_vec: Optional[List[float]] = None
        if self._indexed:
            try:
                from app.modules.documents.embeddings import embed_text
                query_vec = await embed_text(query)
            except Exception as e:
                logger.warning(f"[GroundingIndex] Query embedding failed: {e}")
                query_vec = None

        scored_chunks: List[GroundedChunk] = []

        for chunk in self.chunks:
            if filter_section and filter_section.lower() not in chunk.section_label.lower():
                continue

            sem_score = 0.0
            if query_vec and chunk.embedding:
                sem_score = _cosine_similarity(query_vec, chunk.embedding)

            kw_score = _compute_keyword_overlap(query, chunk.text)

            # Combined score: 60% semantic + 40% keyword if vector available, else 100% keyword
            if query_vec and chunk.embedding:
                combined_score = (sem_score * 0.60) + (kw_score * 0.40)
            else:
                combined_score = kw_score

            if combined_score >= min_score or len(self.chunks) <= top_k:
                chunk_copy = GroundedChunk(
                    chunk_id=chunk.chunk_id,
                    text=chunk.text,
                    page_number=chunk.page_number,
                    section_label=chunk.section_label,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    source_filename=chunk.source_filename,
                    score=round(combined_score, 4),
                    semantic_score=round(sem_score, 4),
                    keyword_score=round(kw_score, 4),
                )
                scored_chunks.append(chunk_copy)

        scored_chunks.sort(key=lambda c: c.score, reverse=True)
        top_matches = scored_chunks[:top_k]

        # If zero matches above min_score, fallback to top chunks by keyword or position
        if not top_matches and self.chunks:
            top_matches = [
                GroundedChunk(
                    chunk_id=c.chunk_id,
                    text=c.text,
                    page_number=c.page_number,
                    section_label=c.section_label,
                    char_start=c.char_start,
                    char_end=c.char_end,
                    source_filename=c.source_filename,
                    score=0.1,
                )
                for c in self.chunks[:top_k]
            ]

        return top_matches

    async def retrieve_for_sections(
        self,
        event_name: str,
        department_or_lab: str,
        event_date: str = "",
    ) -> Dict[str, List[GroundedChunk]]:
        """
        Retrieves dedicated, grounded chunks for every magazine section:
        introduction, project, achievement, event, research, gallery, closing.
        """
        section_queries = {
            "introduction": f"{event_name} overview theme opening keynote objective {department_or_lab}",
            "writeup": f"{event_name} technical methodology project demonstration results implementation {department_or_lab}",
            "projects": f"{event_name} prototype project demonstration hardware software model architecture team lead",
            "achievements": f"{event_name} award prize winner rank recognition achievement 1st place honor cash prize certificate",
            "events": f"{event_name} session workshop seminar hackathon presentation schedule date timeline conference",
            "research": f"{event_name} research paper publication dataset algorithm findings IEEE analysis",
            "gallery": f"{event_name} demonstration laboratory exhibition ceremony photo group faculty students",
            "closing": f"{event_name} conclusion future scope next steps vote of thanks summary",
        }

        results: Dict[str, List[GroundedChunk]] = {}
        for sec, query in section_queries.items():
            chunks = await self.retrieve(query=query, top_k=4, min_score=0.12)
            results[sec] = chunks

        return results

    def format_grounding_block_for_prompt(
        self,
        section_chunks: Dict[str, List[GroundedChunk]],
    ) -> str:
        """
        Formats retrieved chunks into clear, cited grounding context for Qwen.
        Each passage includes [Source Chunk #, Page #, Section].
        """
        lines = ["=== FACTUAL SOURCE PASSAGES (GROUND TRUTH) ==="]
        seen_chunk_ids: Set[int] = set()

        for sec_name, chunks in section_chunks.items():
            sec_header = sec_name.upper().replace("_", " ")
            lines.append(f"\n--- Grounding for Section: {sec_header} ---")
            if not chunks:
                lines.append("(No specific source passages found for this section in the document)")
                continue

            for c in chunks:
                lines.append(
                    f"[Chunk #{c.chunk_id} | Page {c.page_number} | {c.section_label}] "
                    f"(Score: {c.score:.2f})\n{c.text}\n"
                )
                seen_chunk_ids.add(c.chunk_id)

        return "\n".join(lines)
