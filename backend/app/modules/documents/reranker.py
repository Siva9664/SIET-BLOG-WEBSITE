import json
import re
from typing import Any, Dict, List

from app.core.logging import logger
from app.modules.documents.provenance import confidence_band
from app.modules.magazine.ai_service import _call_llm


async def rerank(
    query: str,
    candidates: List[Dict[str, Any]],
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    """
    Reranks top-N candidate passages using batched relevance scoring.
    Attaches final score and updated confidence_band while keeping original semantic_score & keyword_score.
    """
    if not candidates:
        return []

    # If candidates list is short, cap top_n
    top_candidates = candidates[: max(top_n * 2, 10)]

    # Attempt Batched LLM Reranking Pass
    reranked_scores: Dict[int, float] = {}
    try:
        passages_formatted = []
        for idx, c in enumerate(top_candidates):
            text_snippet = c["text"].replace("\n", " ")[:250]
            passages_formatted.append(f"[{idx+1}] {text_snippet}")

        prompt = f"""You are a relevance scoring engine for document search.
Query: "{query}"

Score each passage from 0.00 (completely irrelevant) to 1.00 (highly relevant).
Respond ONLY with a JSON list of floats matching the passage order, e.g. [0.92, 0.85, 0.40].

Passages:
{ chr(10).join(passages_formatted) }
"""
        llm_response = await _call_llm(prompt)
        if llm_response:
            match = re.search(r"\[\s*[\d\.\s,\n]+\s*\]", llm_response)
            if match:
                scores_array = json.loads(match.group(0))
                if isinstance(scores_array, list) and len(scores_array) == len(top_candidates):
                    for idx, s in enumerate(scores_array):
                        reranked_scores[idx] = max(0.0, min(1.0, float(s)))
    except Exception as e:
        logger.warning(f"LLM Reranker batched call failed/skipped: {e}. Using deterministic hybrid cross-scoring.")

    final_results: List[Dict[str, Any]] = []

    for idx, c in enumerate(top_candidates):
        sem_score = c.get("semantic_score", 0.0)
        kw_score = c.get("keyword_score", 0.0)
        base_score = c.get("score", 0.0)

        if idx in reranked_scores:
            llm_score = reranked_scores[idx]
            # Blend LLM relevance with base hybrid score (0.6 LLM + 0.4 base)
            final_score = (llm_score * 0.6) + (base_score * 0.4)
        else:
            # Deterministic hybrid blend
            final_score = (sem_score * 0.5) + (kw_score * 0.5)

        clean_score = round(float(final_score), 4)

        result_item = dict(c)
        result_item["score"] = clean_score
        result_item["confidence_band"] = confidence_band(clean_score)
        final_results.append(result_item)

    final_results.sort(key=lambda x: x["score"], reverse=True)
    return final_results[:top_n]
