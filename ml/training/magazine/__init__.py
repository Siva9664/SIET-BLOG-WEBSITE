"""
SIET Magazine Training Dataset Builder Package.
"""

from .schemas import (
    DocumentRecord,
    PageData,
    PhotoItem,
    StorySegment,
    ExampleRecord,
    AdminFeedbackRecord,
    QualityReport,
    StoryType,
    PhotoConfidence,
    LayoutIntent,
    PageType,
)
from .ingestion import DocumentIngestion
from .segmenter import StorySegmenter
from .photo_associator import PhotoAssociator
from .example_builder import ExampleBuilder
from .grounding import GroundingAuditor
from .deduplicator import Deduplicator
from .splitter import DatasetSplitter
from .stats import StatsAggregator, DatasetStatistics
from .quality_gates import QualityGateManager


def get_builder(*args, **kwargs):
    from .build_dataset import MagazineDatasetBuilder
    return MagazineDatasetBuilder(*args, **kwargs)


__all__ = [
    "DocumentRecord",
    "PageData",
    "PhotoItem",
    "StorySegment",
    "ExampleRecord",
    "AdminFeedbackRecord",
    "QualityReport",
    "StoryType",
    "PhotoConfidence",
    "LayoutIntent",
    "PageType",
    "DocumentIngestion",
    "StorySegmenter",
    "PhotoAssociator",
    "ExampleBuilder",
    "GroundingAuditor",
    "Deduplicator",
    "DatasetSplitter",
    "StatsAggregator",
    "DatasetStatistics",
    "QualityGateManager",
    "MagazineDatasetBuilder",
]
