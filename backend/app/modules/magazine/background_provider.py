"""
Background Image Pool Provider for Magazine Generation.

Provides local high-resolution background images for magazine covers and section pages
sourced from backend/app/static/magazine-backgrounds/manifest.json.
Supports non-repeating random selection within issue generation and live API fallback.
"""
import os
import json
import random
from typing import Dict, Any, Set, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MANIFEST_PATH = os.path.join(BASE_DIR, "static", "magazine-backgrounds", "manifest.json")

# Category mapping from department slugs or section topics to pool buckets
CATEGORY_MAP = {
    "ai-ml": "ai-lab",
    "ai-lab": "ai-lab",
    "robotics": "robotics",
    "cybersecurity": "cybersecurity",
    "pcb-electronics": "electronics-vlsi",
    "vlsi-semiconductor": "electronics-vlsi",
    "electronics-vlsi": "electronics-vlsi",
    "ar-vr-xr": "ar-vr-xr",
    "iot": "iot",
    "general-tech": "general-tech",
    "general": "general-tech",
}

# Live fallback URLs in case local pool or category is unavailable
FALLBACK_URLS = {
    "ai-lab": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=1920&q=80",
    "robotics": "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?auto=format&fit=crop&w=1920&q=80",
    "cybersecurity": "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?auto=format&fit=crop&w=1920&q=80",
    "electronics-vlsi": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1920&q=80",
    "ar-vr-xr": "https://images.unsplash.com/photo-1593508512255-86ab42a8e620?auto=format&fit=crop&w=1920&q=80",
    "iot": "https://images.unsplash.com/photo-1558346490-a72e53ae2d4f?auto=format&fit=crop&w=1920&q=80",
    "general-tech": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1920&q=80",
}


def load_manifest() -> list[dict]:
    """Loads local background image manifest from disk."""
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def get_random_background(
    category: str = "general-tech",
    used_ids: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    Selects a random, non-repeating background image from the local pool manifest.

    Args:
        category: Requested department or image category bucket.
        used_ids: Optional set of image IDs already selected in the current issue session.

    Returns:
        Dict containing image metadata (id, url_path, local_path, photographer, category, etc.).
    """
    if used_ids is None:
        used_ids = set()

    bucket = CATEGORY_MAP.get(category.lower().strip(), "general-tech")
    manifest = load_manifest()

    # Filter items matching category bucket
    candidates = [item for item in manifest if item.get("category") == bucket]

    # If no items for specific bucket, try general-tech
    if not candidates and bucket != "general-tech":
        candidates = [item for item in manifest if item.get("category") == "general-tech"]

    # Filter out already used IDs in current issue session
    available = [item for item in candidates if item.get("id") not in used_ids]

    # Reset pool if all candidates in category were used
    if not available and candidates:
        available = candidates

    if available:
        selected = random.choice(available)
        image_id = selected.get("id", "")
        if image_id:
            used_ids.add(image_id)
        
        return {
            "id": selected.get("id"),
            "category": selected.get("category"),
            "url_path": selected.get("url_path"),
            "local_path": selected.get("local_path"),
            "filename": selected.get("filename"),
            "photographer": selected.get("unsplash_photographer", "Unsplash Contributor"),
            "photo_url": selected.get("unsplash_photo_url", ""),
            "is_fallback": False,
        }

    # Live API / CDN fallback if local manifest is missing
    fallback_url = FALLBACK_URLS.get(bucket, FALLBACK_URLS["general-tech"])
    return {
        "id": f"fallback_{bucket}",
        "category": bucket,
        "url_path": fallback_url,
        "local_path": None,
        "filename": None,
        "photographer": "Unsplash Contributor",
        "photo_url": fallback_url,
        "is_fallback": True,
    }
