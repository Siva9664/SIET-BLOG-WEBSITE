"""
Dataset statistics generator for SIET Magazine Builder.
Aggregates metrics on source documents, pages, stories, photos,
tasks, story types, templates, departments, splits, and quality audits.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

from .schemas import DocumentRecord, StorySegment, PhotoItem, ExampleRecord


@dataclass
class DatasetStatistics:
    total_documents: int = 0
    total_pages: int = 0
    total_stories: int = 0
    total_photos: int = 0
    unique_photos: int = 0
    uncertain_photo_stories: int = 0

    examples_total: int = 0
    train_count: int = 0
    validation_count: int = 0
    adversarial_count: int = 0

    exact_duplicates: int = 0
    duplicate_rate_pct: float = 0.0

    grounding_failures: int = 0

    examples_by_task: Dict[str, int] = field(default_factory=dict)
    examples_by_story_type: Dict[str, int] = field(default_factory=dict)
    examples_by_template: Dict[str, int] = field(default_factory=dict)
    examples_by_department: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        lines = [
            "# SIET Magazine Training Dataset - Statistics Report\n",
            "## 1. Corpus Summary",
            f"- **Source Documents**: {self.total_documents}",
            f"- **Processed Pages**: {self.total_pages}",
            f"- **Extracted Stories/Events**: {self.total_stories}",
            f"- **Extracted Photos**: {self.total_photos} (Unique: {self.unique_photos})",
            f"- **Stories with Uncertain Photo Association**: {self.uncertain_photo_stories}\n",
            "## 2. Dataset Splits",
            f"- **Train Examples**: {self.train_count}",
            f"- **Validation Examples**: {self.validation_count}",
            f"- **Adversarial Examples**: {self.adversarial_count}",
            f"- **Total Supervised Examples**: {self.examples_total}",
            f"- **Duplicate Examples Filtered**: {self.exact_duplicates} ({self.duplicate_rate_pct:.2f}%)\n",
            "## 3. Tasks Distribution",
        ]
        for task, count in sorted(self.examples_by_task.items(), key=lambda x: -x[1]):
            lines.append(f"- **{task}**: {count}")

        lines.append("\n## 4. Story Types")
        for stype, count in sorted(self.examples_by_story_type.items(), key=lambda x: -x[1]):
            lines.append(f"- **{stype}**: {count}")

        lines.append("\n## 5. Templates")
        for tmpl, count in sorted(self.examples_by_template.items(), key=lambda x: -x[1]):
            lines.append(f"- **{tmpl}**: {count}")

        lines.append("\n## 6. Labs / Departments")
        for dept, count in sorted(self.examples_by_department.items(), key=lambda x: -x[1]):
            lines.append(f"- **{dept}**: {count}")

        lines.append(f"\n## 7. Grounding Audit Failures: {self.grounding_failures}\n")
        return "\n".join(lines)


class StatsAggregator:
    """
    Computes comprehensive dataset statistics.
    """

    def compute(
        self,
        documents: List[DocumentRecord],
        stories: List[StorySegment],
        all_examples: List[ExampleRecord],
        train_examples: List[ExampleRecord],
        val_examples: List[ExampleRecord],
        adversarial_examples: List[ExampleRecord],
        exact_duplicates: int = 0,
        grounding_failures: int = 0,
    ) -> DatasetStatistics:
        stats = DatasetStatistics()
        stats.total_documents = len(documents)
        stats.total_pages = sum(d.total_pages for d in documents)
        stats.total_stories = len(stories)

        # Photos
        all_photos = []
        for d in documents:
            for p in d.pages:
                all_photos.extend(p.photos)
        stats.total_photos = len(all_photos)
        stats.unique_photos = len({p.sha256 for p in all_photos if p.sha256})

        stats.uncertain_photo_stories = sum(
            1 for s in stories if s.photo_confidence == "uncertain"
        )

        stats.examples_total = len(all_examples)
        stats.train_count = len(train_examples)
        stats.validation_count = len(val_examples)
        stats.adversarial_count = len(adversarial_examples)

        stats.exact_duplicates = exact_duplicates
        denom = stats.examples_total + exact_duplicates
        stats.duplicate_rate_pct = (exact_duplicates / denom * 100) if denom > 0 else 0.0

        stats.grounding_failures = grounding_failures

        # Categorical counters
        task_counter = Counter()
        stype_counter = Counter()
        tmpl_counter = Counter()
        dept_counter = Counter()

        for ex in all_examples:
            m = ex.metadata
            task = m.get("task_type", "unknown")
            cat = m.get("category", "unknown")
            tmpl = m.get("template_id", "none")
            dept = m.get("lab_department", "Campus General")

            task_counter[task] += 1
            stype_counter[cat] += 1
            if tmpl != "none":
                tmpl_counter[tmpl] += 1
            if dept:
                dept_counter[dept] += 1

        stats.examples_by_task = dict(task_counter)
        stats.examples_by_story_type = dict(stype_counter)
        stats.examples_by_template = dict(tmpl_counter)
        stats.examples_by_department = dict(dept_counter)

        return stats
