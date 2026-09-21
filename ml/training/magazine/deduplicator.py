"""
Deterministic deduplication module for magazine dataset examples,
source text, and embedded photos.
Supports:
- Exact duplicate examples (SHA-256)
- Exact duplicate source texts
- Duplicate photos (SHA-256 and difference perceptual hash)
- Near-duplicate text detection (Word 3-gram Jaccard similarity)
"""

from __future__ import annotations

import re
import io
import json
import hashlib
from typing import List, Set, Dict, Tuple, Optional
from PIL import Image

from .schemas import ExampleRecord, PhotoItem


def normalize_text(text: str) -> str:
    """Normalizes text by lowercasing and collapsing whitespace."""
    return re.sub(r"\s+", " ", text.strip().lower())


def get_word_ngrams(text: str, n: int = 2) -> Set[str]:
    """Generates word n-grams from normalized text."""
    words = normalize_text(text).split()
    if len(words) < n:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


def jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    """Computes Jaccard similarity coefficient between two sets."""
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    return intersection / union if union > 0 else 0.0


def compute_difference_hash(image_bytes: bytes, hash_size: int = 8) -> Optional[str]:
    """
    Computes a difference perceptual hash (dHash) for an image.
    Resizes to (hash_size + 1, hash_size) grayscale and compares adjacent pixels.
    """
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            img = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
            if hasattr(img, "get_flattened_data"):
                pixels = list(img.get_flattened_data())
            else:
                pixels = list(img.getdata())
            # Compare left vs right
            diff = []
            for row in range(hash_size):
                for col in range(hash_size):
                    left = pixels[row * (hash_size + 1) + col]
                    right = pixels[row * (hash_size + 1) + col + 1]
                    diff.append("1" if left > right else "0")
            return "".join(diff)
    except Exception:
        return None



def hamming_distance(hash1: str, hash2: str) -> int:
    """Computes bitwise Hamming distance between two binary hash strings."""
    if len(hash1) != len(hash2):
        return 999
    return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))


class Deduplicator:
    """
    Deterministic deduplication manager for examples, source documents, and images.
    """

    def __init__(self, near_dup_threshold: float = 0.88):
        self.near_dup_threshold = near_dup_threshold
        self.seen_example_hashes: Set[str] = set()
        self.seen_source_hashes: Set[str] = set()
        self.seen_image_sha256: Set[str] = set()
        self.seen_image_dhashes: Dict[str, str] = {}  # photo_id -> dhash
        self.seen_text_ngrams: List[Tuple[str, Set[str]]] = []  # (identifier, ngrams)

    def is_duplicate_example(self, example: ExampleRecord) -> bool:
        """Checks if exact example has already been recorded."""
        # Key on serialized messages content
        key = json.dumps(example.messages, sort_keys=True)
        h = hashlib.sha256(key.encode("utf-8")).hexdigest()
        if h in self.seen_example_hashes:
            return True
        self.seen_example_hashes.add(h)
        return False

    def is_duplicate_source_text(self, text: str) -> bool:
        """Checks if exact source text has been encountered."""
        norm = normalize_text(text)
        h = hashlib.sha256(norm.encode("utf-8")).hexdigest()
        if h in self.seen_source_hashes:
            return True
        self.seen_source_hashes.add(h)
        return False

    def find_near_duplicate_text(self, text: str, text_id: str) -> Optional[str]:
        """
        Checks if text is a near-duplicate of previously seen text (Jaccard similarity >= threshold).
        Returns the ID of matching text or None.
        """
        ngrams = get_word_ngrams(text)
        if not ngrams:
            return None

        for prev_id, prev_ngrams in self.seen_text_ngrams:
            sim = jaccard_similarity(ngrams, prev_ngrams)
            if sim >= self.near_dup_threshold:
                return prev_id

        self.seen_text_ngrams.append((text_id, ngrams))
        return None

    def is_duplicate_image(
        self, photo: PhotoItem, raw_bytes: Optional[bytes] = None
    ) -> Tuple[bool, str]:
        """
        Checks for exact (SHA-256) or perceptual duplicate images.
        Returns (is_duplicate, duplicate_type).
        """
        if photo.sha256 and photo.sha256 in self.seen_image_sha256:
            return True, "exact_sha256"

        if photo.sha256:
            self.seen_image_sha256.add(photo.sha256)

        if raw_bytes:
            dhash = compute_difference_hash(raw_bytes)
            if dhash:
                for prev_id, prev_dhash in self.seen_image_dhashes.items():
                    if hamming_distance(dhash, prev_dhash) <= 3:
                        return True, f"perceptual_near_match:{prev_id}"
                self.seen_image_dhashes[photo.photo_id] = dhash

        return False, "none"

    def filter_examples(
        self, examples: List[ExampleRecord]
    ) -> Tuple[List[ExampleRecord], int]:
        """
        Filters out exact duplicate examples.
        Returns (unique_examples, duplicates_count).
        """
        unique = []
        dup_count = 0
        for ex in examples:
            if self.is_duplicate_example(ex):
                dup_count += 1
            else:
                unique.append(ex)
        return unique, dup_count
