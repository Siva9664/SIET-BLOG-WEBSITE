"""Photo analysis, curation, and slot assignment for magazine generation.

Analyzes uploaded event photos for resolution, aspect ratio, sharpness,
and assigns them to optimal magazine layout slots (hero_cover, feature_story, gallery).
"""

from __future__ import annotations

import io
import math
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from PIL import Image, ImageFilter, ImageStat

from app.core.logging import logger


@dataclass(slots=True)
class PhotoAnalysis:
    id: str
    url: str
    local_path: str | None
    width: int
    height: int
    aspect_ratio: float
    orientation: str  # "landscape" | "portrait" | "square" | "panoramic"
    sharpness_score: float  # 0.0 to 100.0
    brightness: float  # 0.0 to 255.0
    contrast: float  # standard deviation of grayscale pixels
    recommended_slot: str  # "hero_cover" | "feature_story" | "gallery" | "secondary"
    exposure_status: str = "normal"  # "underexposed" | "normal" | "overexposed"
    quality_score: float = 0.5  # 0.0 to 1.0 composite photographic quality
    perceptual_hash: str = ""  # 64-bit dHash string
    is_duplicate: bool = False
    duplicate_of: str | None = None
    caption: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_dhash(img: Image.Image) -> str:
    """Computes a 64-bit difference hash (dHash) for near-duplicate image detection."""
    try:
        gray = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        pixels = list(gray.tobytes())
        diff = []
        for row in range(8):
            for col in range(8):
                idx = row * 9 + col
                diff.append(pixels[idx] < pixels[idx + 1])
        decimal_val = 0
        for bit in diff:
            decimal_val = (decimal_val << 1) | int(bit)
        return f"{decimal_val:016x}"
    except Exception:
        return "0000000000000000"


def hamming_distance(hash1: str, hash2: str) -> int:
    """Calculates bit difference between two hex dHash strings."""
    try:
        val1 = int(hash1, 16)
        val2 = int(hash2, 16)
        return bin(val1 ^ val2).count("1")
    except Exception:
        return 64


def compute_quality_score(
    width: int,
    height: int,
    sharpness: float,
    brightness: float,
    contrast: float,
    aspect_ratio: float,
) -> tuple[float, str]:
    """
    Computes a composite photographic quality score from 0.0 to 1.0.

    Evaluates:
    - resolution: benchmarked to 1080p full HD
    - sharpness: edge contrast variance
    - brightness/exposure: penalty for extreme darkness (<50) or overexposure (>215)
    - contrast: tonal range depth
    - aspect ratio: penalty for awkward extreme crops
    """
    # 1. Resolution score (0.0 to 1.0)
    pixel_count = width * height
    res_score = min(1.0, pixel_count / (1920.0 * 1080.0))
    if pixel_count < 300 * 300:
        res_score = max(0.1, res_score * 0.5)

    # 2. Sharpness score (0.0 to 1.0)
    sharp_score = min(1.0, sharpness / 65.0)

    # 3. Exposure / Brightness (0.0 to 1.0) and status
    if brightness < 45.0:
        exposure_status = "underexposed"
        exposure_score = max(0.1, brightness / 45.0 * 0.5)
    elif brightness > 220.0:
        exposure_status = "overexposed"
        exposure_score = max(0.1, (255.0 - brightness) / 35.0 * 0.5)
    else:
        exposure_status = "normal"
        # Optimal brightness centered around 125-135
        exposure_score = max(0.5, 1.0 - (abs(brightness - 130.0) / 130.0) * 0.5)

    # 4. Contrast score (0.0 to 1.0)
    contrast_score = min(1.0, contrast / 50.0)

    # 5. Aspect ratio penalty for extreme panorama or ribbon crops
    aspect_penalty = 0.0
    if aspect_ratio > 2.5 or aspect_ratio < 0.4:
        aspect_penalty = 0.15

    composite = (
        (res_score * 0.35)
        + (sharp_score * 0.30)
        + (exposure_score * 0.20)
        + (contrast_score * 0.15)
    ) - aspect_penalty

    return round(max(0.05, min(0.99, composite)), 3), exposure_status


def detect_duplicates(
    analyses: List[PhotoAnalysis],
    threshold_dist: int = 8,
) -> List[PhotoAnalysis]:
    """Identifies and flags near-duplicate photos using pairwise dHash comparison."""
    n = len(analyses)
    for i in range(n):
        if analyses[i].is_duplicate:
            continue
        for j in range(i + 1, n):
            if analyses[j].is_duplicate:
                continue
            h1 = analyses[i].perceptual_hash
            h2 = analyses[j].perceptual_hash
            if not h1 or not h2 or h1 == "0000000000000000" or h2 == "0000000000000000":
                continue

            # Degenerate check: if both hashes have very few set bits (<4) or almost all set bits (>60),
            # this indicates flat solid-color images lacking gradient/texture.
            # Avoid false-positive duplicate matches across distinct solid-color images.
            count1 = bin(int(h1, 16)).count("1")
            count2 = bin(int(h2, 16)).count("1")
            if (count1 < 4 or count1 > 60) and (count2 < 4 or count2 > 60):
                if h1 != h2 or analyses[i].aspect_ratio != analyses[j].aspect_ratio or analyses[i].width != analyses[j].width:
                    continue

            dist = hamming_distance(h1, h2)
            if dist <= threshold_dist:
                # Mark the lower quality or later photo as duplicate
                if analyses[i].quality_score >= analyses[j].quality_score:
                    analyses[j].is_duplicate = True
                    analyses[j].duplicate_of = analyses[i].id
                else:
                    analyses[i].is_duplicate = True
                    analyses[i].duplicate_of = analyses[j].id
                    break
    return analyses


def _compute_sharpness(img_gray: Image.Image) -> float:
    """Estimates image sharpness using edge filter variance."""
    try:
        edges = img_gray.filter(ImageFilter.FIND_EDGES)
        stat = ImageStat.Stat(edges)
        variance = stat.var[0] if stat.var else 0.0
        return min(100.0, round(math.sqrt(variance) * 2.5, 2))
    except Exception:
        return 50.0


def analyze_photo(
    image_source: str | bytes | io.BytesIO,
    photo_id: str = "",
    url: str = "",
    caption: str = "",
) -> PhotoAnalysis:
    """Inspects an image file or bytes and computes layout-relevant attributes."""
    local_path = None
    if isinstance(image_source, str):
        clean_path = image_source.lstrip("/")
        if os.path.exists(clean_path):
            local_path = clean_path
            img = Image.open(clean_path)
        elif os.path.exists(image_source):
            local_path = image_source
            img = Image.open(image_source)
        else:
            raise FileNotFoundError(f"Image not found at path: {image_source}")
    elif isinstance(image_source, bytes):
        img = Image.open(io.BytesIO(image_source))
    else:
        img = Image.open(image_source)

    w, h = img.size
    ratio = round(w / max(h, 1), 3)

    if ratio >= 2.0:
        orientation = "panoramic"
    elif ratio >= 1.2:
        orientation = "landscape"
    elif ratio <= 0.85:
        orientation = "portrait"
    else:
        orientation = "square"

    gray = img.convert("L")
    stat = ImageStat.Stat(gray)
    brightness = round(stat.mean[0] if stat.mean else 128.0, 1)
    contrast = round(stat.stddev[0] if stat.stddev else 40.0, 1)
    sharpness = _compute_sharpness(gray)

    quality_score, exposure_status = compute_quality_score(
        width=w,
        height=h,
        sharpness=sharpness,
        brightness=brightness,
        contrast=contrast,
        aspect_ratio=ratio,
    )
    p_hash = compute_dhash(img)

    if orientation in ("landscape", "panoramic") and w >= 800 and sharpness >= 30:
        slot = "hero_cover"
    elif orientation in ("landscape", "square") and w >= 500:
        slot = "feature_story"
    elif orientation == "portrait":
        slot = "portrait_card"
    else:
        slot = "gallery"

    return PhotoAnalysis(
        id=photo_id or f"photo_{w}x{h}",
        url=url,
        local_path=local_path,
        width=w,
        height=h,
        aspect_ratio=ratio,
        orientation=orientation,
        sharpness_score=sharpness,
        brightness=brightness,
        contrast=contrast,
        recommended_slot=slot,
        exposure_status=exposure_status,
        quality_score=quality_score,
        perceptual_hash=p_hash,
        is_duplicate=False,
        duplicate_of=None,
        caption=caption,
    )


def curate_photos_for_magazine(
    photos_input: List[Dict[str, Any]],
    target_page_budget: int = 4,
) -> Dict[str, Any]:
    """Curates and assigns uploaded photos to magazine layout slots."""
    analyzed: List[PhotoAnalysis] = []

    for idx, item in enumerate(photos_input):
        url = item.get("url", "")
        pid = str(item.get("id", f"photo_{idx+1}"))
        cap = str(item.get("caption", ""))
        clean_path = url.lstrip("/")

        try:
            target_path = None
            if url and os.path.exists(url):
                target_path = url
            elif clean_path and os.path.exists(clean_path):
                target_path = clean_path
            elif item.get("local_path") and os.path.exists(item["local_path"]):
                target_path = item["local_path"]

            if target_path:
                analysis = analyze_photo(target_path, photo_id=pid, url=url, caption=cap)
                analyzed.append(analysis)
        except Exception as e:
            logger.warning(f"[PhotoCurator] Could not analyze photo {url}: {e}")

    if not analyzed:
        return {
            "hero_cover": None,
            "feature_story": None,
            "gallery": [],
            "all_analyzed": [],
        }

    def quality_key(p: PhotoAnalysis) -> float:
        return (p.sharpness_score * 0.4) + (p.contrast * 0.3) + (min(p.width, 1920) / 1920.0 * 30.0)

    landscape_pool = [p for p in analyzed if p.orientation in ("landscape", "panoramic")]
    landscape_pool.sort(key=quality_key, reverse=True)

    remaining = list(analyzed)

    hero = None
    if landscape_pool:
        hero = landscape_pool[0]
        remaining.remove(hero)
    elif remaining:
        hero = remaining[0]
        remaining.remove(hero)

    feature = None
    feature_candidates = [p for p in remaining if p.orientation in ("landscape", "square")]
    feature_candidates.sort(key=quality_key, reverse=True)
    if feature_candidates:
        feature = feature_candidates[0]
        remaining.remove(feature)
    elif remaining:
        feature = remaining[0]
        remaining.remove(feature)

    gallery = remaining

    return {
        "hero_cover": hero.to_dict() if hero else None,
        "feature_story": feature.to_dict() if feature else None,
        "gallery": [g.to_dict() for g in gallery],
        "all_analyzed": [a.to_dict() for a in analyzed],
    }
