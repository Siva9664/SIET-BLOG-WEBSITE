"""Vision and Multimodal Image-Text Embedding Provider.

Provides local image and text embeddings using SigLIP (or CLIP) to enable
intelligent semantic photo selection and ranking for magazine articles.
"""

from __future__ import annotations

import io
import math
import os
import re
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Union

from PIL import Image

from app.core.config import settings
from app.core.logging import logger


class BaseVisionEmbedder(ABC):
    """Abstract interface for vision and multimodal embedding models."""

    @abstractmethod
    async def embed_image(self, image: Union[Image.Image, str, bytes], context: Optional[str] = None) -> List[float]:
        """Embeds an image into a normalized float vector."""
        pass

    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """Embeds text into a normalized float vector."""
        pass

    @abstractmethod
    async def embed_images(self, images: List[Union[Image.Image, str, bytes]]) -> List[List[float]]:
        """Batch embeds multiple images into normalized float vectors."""
        pass

    @abstractmethod
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Batch embeds multiple texts into normalized float vectors."""
        pass

    def compute_similarity(self, text_embedding: List[float], image_embedding: List[float]) -> float:
        """
        Computes cosine similarity between unit-normalized text and image vectors.
        Returns a float between 0.0 and 1.0.
        """
        if not text_embedding or not image_embedding:
            return 0.0
        if len(text_embedding) != len(image_embedding):
            return 0.0

        dot_product = sum(t * i for t, i in zip(text_embedding, image_embedding))
        # Ensure clamped in [0.0, 1.0]
        return round(max(0.0, min(1.0, float(dot_product))), 4)


def _load_pil_image(image: Union[Image.Image, str, bytes]) -> Image.Image:
    """Safely loads a PIL Image from an Image object, file path, or bytes."""
    if isinstance(image, Image.Image):
        return image.convert("RGB")
    elif isinstance(image, bytes):
        return Image.open(io.BytesIO(image)).convert("RGB")
    elif isinstance(image, str):
        clean_path = image.lstrip("/")
        if os.path.exists(image):
            return Image.open(image).convert("RGB")
        elif os.path.exists(clean_path):
            return Image.open(clean_path).convert("RGB")
        else:
            raise FileNotFoundError(f"Image not found at path: {image}")
    raise TypeError(f"Unsupported image type: {type(image)}")


class SiglipVisionEmbedder(BaseVisionEmbedder):
    """
    Local multimodal embedding provider using SigLIP (or CLIP) from Hugging Face transformers.
    Produces unit-normalized dense vectors for both images and text in the same joint space.
    """

    def __init__(self, model_name: Optional[str] = None, device: Optional[str] = None):
        self.model_name = model_name or getattr(settings, "MAGAZINE_VISION_MODEL", "google/siglip-base-patch16-224")
        self.device = device or getattr(settings, "MAGAZINE_VISION_DEVICE", "cpu")
        self._processor = None
        self._model = None
        self._dim = 768

    def _ensure_loaded(self):
        if self._model is None and not hasattr(self, "_fallback_embedder"):
            logger.info(f"[SiglipVisionEmbedder] Loading vision model: {self.model_name} on {self.device}")
            try:
                import torch
                from transformers import AutoModel, AutoProcessor

                self._processor = AutoProcessor.from_pretrained(self.model_name)
                self._model = AutoModel.from_pretrained(self.model_name)
                self._model.to(self.device)
                self._model.eval()
            except Exception as e:
                logger.warning(
                    f"[SiglipVisionEmbedder] Failed to load {self.model_name}: {e}. "
                    f"Falling back to deterministic MockVisionEmbedder."
                )
                self._fallback_embedder = MockVisionEmbedder()

    async def embed_image(self, image: Union[Image.Image, str, bytes], context: Optional[str] = None) -> List[float]:
        self._ensure_loaded()
        if hasattr(self, "_fallback_embedder"):
            return await self._fallback_embedder.embed_image(image, context)
        results = await self.embed_images([image])
        return results[0] if results else [0.0] * self._dim

    async def embed_images(self, images: List[Union[Image.Image, str, bytes]]) -> List[List[float]]:
        if not images:
            return []

        self._ensure_loaded()
        if hasattr(self, "_fallback_embedder"):
            return await self._fallback_embedder.embed_images(images)

        pil_images = [_load_pil_image(img) for img in images]
        import torch

        inputs = self._processor(images=pil_images, return_tensors="pt").to(self.device)
        with torch.no_grad():
            image_features = self._model.get_image_features(**inputs)
            if hasattr(image_features, "pooler_output") and image_features.pooler_output is not None:
                image_features = image_features.pooler_output
            elif hasattr(image_features, "last_hidden_state"):
                image_features = image_features.last_hidden_state[:, 0]
            # L2 normalize
            image_features = image_features / image_features.norm(p=2, dim=-1, keepdim=True)

        return [[round(float(v), 6) for v in row] for row in image_features.cpu().tolist()]

    async def embed_text(self, text: str) -> List[float]:
        self._ensure_loaded()
        if hasattr(self, "_fallback_embedder"):
            return await self._fallback_embedder.embed_text(text)
        results = await self.embed_texts([text])
        return results[0] if results else [0.0] * self._dim

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        self._ensure_loaded()
        if hasattr(self, "_fallback_embedder"):
            return await self._fallback_embedder.embed_texts(texts)

        safe_texts = [t.strip() if t.strip() else "photo" for t in texts]
        import torch

        inputs = self._processor(
            text=safe_texts,
            padding="max_length",
            truncation=True,
            max_length=64,
            return_tensors="pt",
        ).to(self.device)
        with torch.no_grad():
            text_features = self._model.get_text_features(**inputs)
            if hasattr(text_features, "pooler_output") and text_features.pooler_output is not None:
                text_features = text_features.pooler_output
            elif hasattr(text_features, "last_hidden_state"):
                text_features = text_features.last_hidden_state[:, 0]
            # L2 normalize
            text_features = text_features / text_features.norm(p=2, dim=-1, keepdim=True)

        return [[round(float(v), 6) for v in row] for row in text_features.cpu().tolist()]


class MockVisionEmbedder(BaseVisionEmbedder):
    """
    Fast, deterministic mock vision embedder for test suites and offline verification.
    Computes semantic vector representations based on keyword topics and visual cues.
    """

    TOPIC_SIGNATURES = {
        # Direct robotics hardware & build (indices 0, 1, 5)
        "robotics": {0: 2.2, 1: 1.0, 5: 0.6},
        "robot": {0: 2.0, 1: 0.9, 5: 0.5},
        "quadruped": {0: 1.8, 1: 0.8, 5: 0.4},
        "hardware": {0: 1.2, 1: 0.6},
        "autonomous": {0: 1.2, 1: 0.6},
        "sensor": {0: 0.8, 1: 1.1},
        "lidar": {0: 0.8, 1: 1.1},
        "quadrobo": {0: 1.0, 1: 1.1},

        # Hackathon / competition / team event (indices 1, 2, 5)
        "hackathon": {1: 2.0, 2: 0.8, 5: 0.7},
        "competition": {1: 1.6, 2: 0.7, 5: 0.6},
        "participating": {1: 0.8, 5: 0.6},
        "students": {5: 1.2, 1: 0.7},
        "engineering": {5: 0.9, 0: 0.5, 1: 0.5},
        "team": {5: 0.8, 1: 0.8},

        # Venue / stage / event hall (indices 2, 1, 5)
        "auditorium": {2: 1.6, 1: 1.6, 5: 1.0},
        "venue": {2: 1.5, 1: 1.6, 5: 1.0},
        "stage": {2: 1.3, 1: 1.3, 5: 0.8},
        "seating": {2: 1.0, 1: 0.8, 5: 0.6},
        "keynote": {2: 1.3, 1: 1.2, 5: 0.8},

        # Faculty / research
        "faculty": {3: 2.0, 5: 0.8},
        "professor": {3: 2.0, 5: 0.8},
        "grant": {3: 1.8},
        "research": {3: 1.8},

        # Food / dining / cafeteria (indices 4)
        "food": {4: 2.0},
        "cafeteria": {4: 2.0},
        "dining": {4: 2.0},
        "lunch": {4: 2.0},
        "snacks": {4: 2.0},
    }

    def __init__(self, dim: int = 16):
        self.dim = dim

    def _hash_vector(self, text: str) -> List[float]:
        vec = [0.1] * self.dim
        clean = text.lower()

        matched = False
        for word, sig in self.TOPIC_SIGNATURES.items():
            if word in clean:
                matched = True
                for idx, weight in sig.items():
                    vec[idx % self.dim] += weight

        if not matched:
            # Hash fallback
            h = abs(hash(clean))
            vec[h % self.dim] += 1.0

        # L2 normalize
        mag = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [round(v / mag, 6) for v in vec]

    async def embed_image(self, image: Union[Image.Image, str, bytes], context: Optional[str] = None) -> List[float]:
        text_parts = []
        if context:
            text_parts.append(str(context))
        if isinstance(image, str):
            text_parts.append(os.path.basename(image))
        elif isinstance(image, Image.Image):
            text_parts.append(f"image_{image.width}x{image.height}_{image.format}")
        else:
            text_parts.append("image_bytes")
        meta_str = " ".join(text_parts) if text_parts else "image"
        return self._hash_vector(meta_str)

    async def embed_images(self, images: List[Union[Image.Image, str, bytes]]) -> List[List[float]]:
        return [await self.embed_image(img) for img in images]

    async def embed_text(self, text: str) -> List[float]:
        return self._hash_vector(text)

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [await self.embed_text(t) for t in texts]


_global_vision_embedder: Optional[BaseVisionEmbedder] = None


def get_vision_embedder(provider_type: Optional[str] = None) -> BaseVisionEmbedder:
    """
    Singleton factory for vision embedder.
    If provider_type is 'mock' or USE_MOCK_VISION_EMBEDDER=1, returns MockVisionEmbedder.
    Otherwise returns SiglipVisionEmbedder.
    """
    global _global_vision_embedder

    if provider_type == "mock" or os.getenv("USE_MOCK_VISION_EMBEDDER") == "1":
        return MockVisionEmbedder()

    if _global_vision_embedder is None:
        try:
            _global_vision_embedder = SiglipVisionEmbedder()
        except Exception as e:
            logger.warning(f"[VisionEmbedder] Could not initialize SigLIP: {e}. Falling back to Mock.")
            _global_vision_embedder = MockVisionEmbedder()

    return _global_vision_embedder
