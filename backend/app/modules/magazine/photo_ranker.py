"""Intelligent Real-Photo Selection and Relevance Ranking Service.

Scores candidate real college photographs against article text using multimodal
SigLIP/CLIP embeddings combined with multi-factor photographic quality evaluation
(resolution, sharpness, exposure, orientation, and near-duplicate suppression).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Union

from app.core.config import settings
from app.core.logging import logger
from app.modules.magazine.photo_curator import (
    PhotoAnalysis,
    analyze_photo,
    detect_duplicates,
)
from app.modules.magazine.vision_embedder import BaseVisionEmbedder, get_vision_embedder


def _extract_article_query(content: Union[str, Dict[str, Any]]) -> str:
    """Extracts a focused semantic query string from article content."""
    if isinstance(content, str):
        return content.strip()
    parts = [
        str(content.get("title", "")).strip(),
        str(content.get("headline", "")).strip(),
        str(content.get("description", "")).strip(),
        str(content.get("section", "")).strip(),
    ]
    # Include beginning of writeup if available
    writeup = str(content.get("writeup", "") or content.get("body", "")).strip()
    if writeup:
        parts.append(writeup[:300])
    return " ".join(p for p in parts if p)


async def rank_photos_for_article(
    article_content: Union[str, Dict[str, Any]],
    photos: List[Dict[str, Any]],
    top_k: int = 5,
    filter_duplicates: bool = True,
    min_quality_threshold: float = 0.20,
    embedder: Optional[BaseVisionEmbedder] = None,
) -> Dict[str, Any]:
    """
    Ranks real photographs by semantic relevance to an article and photographic quality.

    Guarantees:
    - Strictly prefers real uploaded photographs.
    - Zero synthetic/AI generation is triggered when real photographs are present.
    - Near-duplicates are identified and penalized/suppressed.
    """
    if not photos:
        return {
            "ranked_photos": [],
            "selected_hero": None,
            "selected_features": [],
            "selected_gallery": [],
            "duplicates_detected": 0,
        }

    embedder_instance = embedder or get_vision_embedder()
    relevance_weight = getattr(settings, "MAGAZINE_PHOTO_RELEVANCE_WEIGHT", 0.70)
    quality_weight = getattr(settings, "MAGAZINE_PHOTO_QUALITY_WEIGHT", 0.30)

    # 1. Photographic Quality & Attribute Analysis
    analyzed_photos: List[PhotoAnalysis] = []
    for idx, item in enumerate(photos):
        url = str(item.get("url", "")).strip()
        pid = str(item.get("id", f"photo_{idx+1}")).strip()
        caption = str(item.get("caption", "")).strip()
        filename = item.get("filename") or os.path.basename(url) or f"photo_{idx+1}.jpg"

        # Resolve local source path or bytes
        source = item.get("local_path") or item.get("bytes") or url
        try:
            analysis = analyze_photo(source, photo_id=pid, url=url, caption=caption)
            analyzed_photos.append(analysis)
        except Exception as e:
            # If physical image file is not on local disk (e.g. remote URL / metadata-only payload),
            # provide a resilient metadata-based analysis so ranking can still proceed
            logger.info(f"[PhotoRanker] Local file not accessible for {pid} ({url}): {e}. Using metadata representation.")
            width = int(item.get("width", 1920))
            height = int(item.get("height", 1080))
            ratio = round(width / max(height, 1), 3)
            q_score = float(item.get("quality_score", 0.75))
            slot = "hero_cover" if ratio >= 1.3 and width >= 1200 else "feature_story"
            analyzed_photos.append(
                PhotoAnalysis(
                    id=pid,
                    url=url,
                    local_path=None,
                    width=width,
                    height=height,
                    aspect_ratio=ratio,
                    orientation="landscape" if ratio >= 1.2 else "square",
                    sharpness_score=50.0,
                    brightness=128.0,
                    contrast=40.0,
                    recommended_slot=slot,
                    exposure_status="normal",
                    quality_score=q_score,
                    perceptual_hash="0000000000000000",
                    is_duplicate=False,
                    duplicate_of=None,
                    caption=caption,
                )
            )

    if not analyzed_photos:
        return {
            "ranked_photos": [],
            "selected_hero": None,
            "selected_features": [],
            "selected_gallery": [],
            "duplicates_detected": 0,
        }

    # 2. Near-Duplicate Detection & Flagging
    detect_duplicates(analyzed_photos)
    duplicates_count = sum(1 for p in analyzed_photos if p.is_duplicate)

    # 3. Generate Multimodal Embeddings
    query_text = _extract_article_query(article_content)
    text_embedding = await embedder_instance.embed_text(query_text)

    # 4. Compute Image-Text Similarity and Combined Score
    ranked_items: List[Dict[str, Any]] = []

    for photo in analyzed_photos:
        # Resolve image representation for embedding
        img_source = photo.local_path or photo.url or photo.id
        context_text = f"{photo.caption} {os.path.basename(photo.url or '')} {photo.id}".strip()
        try:
            # Pass contextual metadata (caption, filename) alongside visual image source
            img_embedding = await embedder_instance.embed_image(img_source, context=context_text)
        except Exception:
            # Fallback to caption/filename representation if file I/O unavailable
            img_embedding = await embedder_instance.embed_text(context_text)

        # Cosine similarity between text query and image
        relevance_score = embedder_instance.compute_similarity(text_embedding, img_embedding)

        # Combined composite score
        combined = (relevance_score * relevance_weight) + (photo.quality_score * quality_weight)

        # Heavy duplicate penalty to suppress redundant photos
        if photo.is_duplicate and filter_duplicates:
            combined = round(combined * 0.40, 4)
        else:
            combined = round(combined, 4)

        # Build human-readable match reason
        reasons = []
        if relevance_score >= 0.85:
            reasons.append(f"Strong semantic alignment ({relevance_score:.2f}) with article content")
        elif relevance_score >= 0.65:
            reasons.append(f"Moderate semantic relevance ({relevance_score:.2f})")
        else:
            reasons.append(f"Baseline contextual match ({relevance_score:.2f})")

        if photo.quality_score >= 0.75:
            reasons.append(f"high quality {photo.orientation} ({photo.width}x{photo.height}, sharp)")
        elif photo.quality_score < 0.40:
            reasons.append(f"lower resolution/exposure quality ({photo.quality_score:.2f})")

        if photo.is_duplicate:
            reasons.append(f"flagged as near-duplicate of {photo.duplicate_of}")

        ranked_items.append({
            "photo_id": photo.id,
            "filename": os.path.basename(photo.url or "") or f"{photo.id}.jpg",
            "url": photo.url,
            "local_path": photo.local_path,
            "relevance_score": relevance_score,
            "quality_score": photo.quality_score,
            "combined_score": combined,
            "is_duplicate": photo.is_duplicate,
            "duplicate_of": photo.duplicate_of,
            "orientation": photo.orientation,
            "recommended_slot": photo.recommended_slot,
            "quality": {
                "width": photo.width,
                "height": photo.height,
                "aspect_ratio": photo.aspect_ratio,
                "orientation": photo.orientation,
                "sharpness": photo.sharpness_score,
                "brightness": photo.brightness,
                "contrast": photo.contrast,
                "exposure_status": photo.exposure_status,
                "quality_score": photo.quality_score,
            },
            "match_reason": "; ".join(reasons),
        })

    # Sort descending by combined score
    ranked_items.sort(key=lambda x: x["combined_score"], reverse=True)

    # 5. Slot Assignment for Layout (Hero, Feature, Gallery)
    # Prefer non-duplicate landscape/panoramic for hero
    hero_candidate = None
    feature_candidates = []
    gallery_candidates = []

    for item in ranked_items:
        if item["is_duplicate"] and filter_duplicates:
            continue
        if hero_candidate is None and item["orientation"] in ("landscape", "panoramic"):
            hero_candidate = item
        elif len(feature_candidates) < 2 and item["orientation"] in ("landscape", "square"):
            feature_candidates.append(item)
        else:
            gallery_candidates.append(item)

    if hero_candidate is None and ranked_items:
        # Fallback hero to highest ranked non-duplicate
        non_dups = [x for x in ranked_items if not x["is_duplicate"]]
        hero_candidate = non_dups[0] if non_dups else ranked_items[0]

    return {
        "ranked_photos": ranked_items[:top_k] if top_k else ranked_items,
        "selected_hero": hero_candidate,
        "selected_features": feature_candidates,
        "selected_gallery": gallery_candidates,
        "duplicates_detected": duplicates_count,
    }
