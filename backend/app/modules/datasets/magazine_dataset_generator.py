"""Magazine Training Dataset Generator Engine (Phase 8).

Converts existing college magazines (PDF/DOCX), event reports, achievement records,
project summaries, templates, and photograph catalogs into a versioned, deduplicated,
PII-sanitized instruction-tuning dataset in JSONL format for future QLoRA/LoRA fine-tuning.
"""

from __future__ import annotations

import collections
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from app.modules.datasets.magazine_dataset_schemas import (
    DatasetExample,
    DatasetExampleMetadata,
    DatasetProvenance,
    DatasetSplit,
    DatasetSplitConfig,
    DatasetStats,
    DatasetTaskType,
)
from app.modules.datasets.pii_sanitizer import detect_pii_issues, sanitize_text
from app.modules.magazine.file_parser import detect_event_info, parse_docx
from app.modules.magazine.template_library import STANDARD_TEMPLATES as TEMPLATE_LIBRARY


class MagazineDatasetGenerator:
    """Orchestrates ingestion, conversion, sanitization, deduplication, and splitting."""

    def __init__(
        self,
        dataset_version: str = "v1.0.0",
        split_config: Optional[DatasetSplitConfig] = None,
    ):
        self.dataset_version = dataset_version
        self.split_config = split_config or DatasetSplitConfig()
        self._seen_hashes: Set[str] = set()

    # ========================================================================
    # 1. Deduplication & Hashing Helper
    # ========================================================================

    def _compute_hash(self, task: DatasetTaskType, input_text: str) -> str:
        canonical = f"{task.value}::{re.sub(r'\\s+', ' ', input_text.strip())}"
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _is_duplicate(self, content_hash: str) -> bool:
        return content_hash in self._seen_hashes

    def _register_hash(self, content_hash: str) -> None:
        self._seen_hashes.add(content_hash)

    # ========================================================================
    # 2. Document & Asset Parsers
    # ========================================================================

    def parse_document_file(self, file_path: Path) -> Dict[str, Any]:
        """Extracts text and metadata from PDF or DOCX file."""
        path_str = str(file_path)
        ext = file_path.suffix.lower()
        text = ""
        images_count = 0
        digest = ""

        try:
            raw_bytes = file_path.read_bytes()
            digest = hashlib.sha256(raw_bytes).hexdigest()[:16]

            if ext == ".docx":
                text, imgs = parse_docx(raw_bytes)
                images_count = len(imgs)
            elif ext == ".pdf":
                import fitz
                doc = fitz.open(stream=raw_bytes, filetype="pdf")
                pages_text = []
                for p in doc:
                    pages_text.append(p.get_text())
                    images_count += len(p.get_images())
                text = "\n\n".join(pages_text)
            elif ext in [".txt", ".md"]:
                text = raw_bytes.decode("utf-8", errors="ignore")
        except Exception as e:
            text = f"Document extraction fallback for {file_path.name}: {e}"

        event_name, event_date = detect_event_info(text)

        return {
            "file_path": path_str,
            "filename": file_path.name,
            "ext": ext,
            "text": text.strip(),
            "event_name": event_name or file_path.stem.replace("_", " ").title(),
            "event_date": event_date or "2026-08-15",
            "images_count": images_count,
            "digest": digest,
        }

    # ========================================================================
    # 3. Task 1: raw document -> structured magazine content
    # ========================================================================

    def make_raw_to_structured_example(
        self,
        doc_info: Dict[str, Any],
        idx: int = 1,
    ) -> Optional[DatasetExample]:
        task = DatasetTaskType.RAW_TO_STRUCTURED
        raw_text = doc_info.get("text", "")
        if len(raw_text) < 60:
            return None

        event_name = doc_info.get("event_name", "SIET Academic Event")
        event_date = doc_info.get("event_date", "2026-08-15")

        # Instruction
        instruction = (
            "You are an expert editorial AI for the SIET college magazine. "
            "Read the following raw college report or document and convert it into structured magazine content "
            "matching the official editorial schema, including title, description, writeup headline, writeup text, "
            "photograph captions, and table of contents summary."
        )

        input_text = sanitize_text(
            f"Document Source: {doc_info.get('filename')}\n"
            f"Event Name: {event_name}\n"
            f"Event Date: {event_date}\n\n"
            f"Raw Document Text:\n{raw_text[:2500]}"
        )

        content_hash = self._compute_hash(task, input_text)
        if self._is_duplicate(content_hash):
            return None
        self._register_hash(content_hash)

        # Build clean structured output JSON
        title = f"{event_name}: Special Digest"
        desc = (
            f"Sri Shakthi Institute of Engineering & Technology held {event_name} on {event_date}, "
            f"showcasing innovative research and student project accomplishments across departments."
        )
        headline = f"Breakthrough Developments at {event_name}"
        writeup = (
            f"{headline}\n\n"
            f"The annual proceedings for {event_name} brought together faculty scholars, industry delegates, "
            f"and student engineers to advance cutting-edge applied technologies. "
            f"Participants exhibited interdisciplinary prototypes and shared critical academic findings.\n\n"
            f"{raw_text[:600].strip()}"
        )
        captions = [
            f"Keynote address by dignitaries during the inaugural session of {event_name}.",
            "Students demonstrating working hardware and software prototype to the evaluation panel.",
            "Group photograph of prize winners and faculty mentors at the valedictory ceremony.",
        ]
        toc = f"Comprehensive review of {event_name} held on {event_date}."

        output_dict = {
            "magazine_issue_title": title,
            "description": desc,
            "writeup_headline": headline,
            "writeup_text": writeup,
            "captions": captions,
            "toc_summary": toc,
            "sections": {
                "title": {"content": title, "confidence_score": 0.94},
                "description": {"content": desc, "confidence_score": 0.92},
                "writeup": {"content": writeup, "confidence_score": 0.95},
                "toc_summary": {"content": toc, "confidence_score": 0.93},
            },
        }

        output_str = sanitize_text(json.dumps(output_dict, indent=2))

        metadata = DatasetExampleMetadata(
            id=f"mag-{self.dataset_version}-task1-{idx:04d}",
            task=task,
            dataset_version=self.dataset_version,
            content_hash=content_hash,
            input_word_count=len(input_text.split()),
            output_word_count=len(output_str.split()),
            provenance=DatasetProvenance(
                source_type=f"{doc_info.get('ext', '').lstrip('.')}_document",
                source_ref=doc_info.get("filename", "unknown"),
                document_digest=doc_info.get("digest"),
                entity_label=event_name,
            ),
        )

        return DatasetExample(
            instruction=instruction,
            input=input_text,
            output=output_str,
            metadata=metadata,
        )

    # ========================================================================
    # 4. Task 2: raw content -> headline
    # ========================================================================

    def make_raw_to_headline_example(
        self,
        content: str,
        expected_headline: str,
        source_ref: str = "editorial_archive",
        idx: int = 1,
    ) -> Optional[DatasetExample]:
        task = DatasetTaskType.RAW_TO_HEADLINE
        instruction = (
            "Generate a compelling, journalistic magazine headline (maximum 15 words) "
            "that captures the core technical achievement, event, or research breakthrough described below."
        )

        input_text = sanitize_text(content.strip()[:1200])
        content_hash = self._compute_hash(task, input_text)
        if self._is_duplicate(content_hash):
            return None
        self._register_hash(content_hash)

        output_text = sanitize_text(expected_headline.strip())

        metadata = DatasetExampleMetadata(
            id=f"mag-{self.dataset_version}-task2-{idx:04d}",
            task=task,
            dataset_version=self.dataset_version,
            content_hash=content_hash,
            input_word_count=len(input_text.split()),
            output_word_count=len(output_text.split()),
            provenance=DatasetProvenance(
                source_type="article_text",
                source_ref=source_ref,
            ),
        )

        return DatasetExample(
            instruction=instruction,
            input=input_text,
            output=output_text,
            metadata=metadata,
        )

    # ========================================================================
    # 5. Task 3: raw content -> caption
    # ========================================================================

    def make_raw_to_caption_example(
        self,
        context: str,
        expected_caption: str,
        source_ref: str = "photo_archive",
        idx: int = 1,
    ) -> Optional[DatasetExample]:
        task = DatasetTaskType.RAW_TO_CAPTION
        instruction = (
            "Generate a concise, factual photograph caption (maximum 15 words) for a college magazine "
            "layout based on the provided event description and visual role."
        )

        input_text = sanitize_text(context.strip()[:1000])
        content_hash = self._compute_hash(task, input_text)
        if self._is_duplicate(content_hash):
            return None
        self._register_hash(content_hash)

        output_text = sanitize_text(expected_caption.strip())

        metadata = DatasetExampleMetadata(
            id=f"mag-{self.dataset_version}-task3-{idx:04d}",
            task=task,
            dataset_version=self.dataset_version,
            content_hash=content_hash,
            input_word_count=len(input_text.split()),
            output_word_count=len(output_text.split()),
            provenance=DatasetProvenance(
                source_type="photo_context",
                source_ref=source_ref,
            ),
        )

        return DatasetExample(
            instruction=instruction,
            input=input_text,
            output=output_text,
            metadata=metadata,
        )

    # ========================================================================
    # 6. Task 4: content -> section classification
    # ========================================================================

    def make_section_classification_example(
        self,
        content: str,
        expected_section: str,
        reason: str,
        source_ref: str = "section_library",
        idx: int = 1,
    ) -> Optional[DatasetExample]:
        task = DatasetTaskType.SECTION_CLASSIFICATION
        instruction = (
            "Classify the following college content into the appropriate magazine section category. "
            "Allowed categories: introduction, project_showcase, student_achievement, faculty_achievement, "
            "events, research, photo_gallery. Return a JSON object with 'section', 'confidence', and 'reason'."
        )

        input_text = sanitize_text(content.strip()[:1200])
        content_hash = self._compute_hash(task, input_text)
        if self._is_duplicate(content_hash):
            return None
        self._register_hash(content_hash)

        output_dict = {
            "section": expected_section,
            "confidence": 0.96,
            "reason": reason,
        }
        output_str = sanitize_text(json.dumps(output_dict, indent=2))

        metadata = DatasetExampleMetadata(
            id=f"mag-{self.dataset_version}-task4-{idx:04d}",
            task=task,
            dataset_version=self.dataset_version,
            content_hash=content_hash,
            input_word_count=len(input_text.split()),
            output_word_count=len(output_str.split()),
            provenance=DatasetProvenance(
                source_type="section_sample",
                source_ref=source_ref,
            ),
        )

        return DatasetExample(
            instruction=instruction,
            input=input_text,
            output=output_str,
            metadata=metadata,
        )

    # ========================================================================
    # 7. Task 5: content + template candidates -> selected template
    # ========================================================================

    def make_template_selection_example(
        self,
        content_summary: str,
        department_or_lab: str,
        section: str,
        photo_count: int,
        candidates: List[Dict[str, Any]],
        selected_template_id: str,
        page_type: str,
        reason: str,
        source_ref: str = "template_library",
        idx: int = 1,
    ) -> Optional[DatasetExample]:
        task = DatasetTaskType.TEMPLATE_SELECTION
        instruction = (
            "Given the magazine content and a list of candidate layout templates, select the most appropriate "
            "template considering department/lab affinity, section type, text capacity, and image constraints. "
            "Return a JSON object with 'template_id', 'page_type', 'confidence', and 'reason'."
        )

        cand_summary = []
        for c in candidates:
            cand_summary.append(
                f"- ID: {c.get('template_id')}, Name: {c.get('name')}, Page Type: {c.get('page_type')}, "
                f"Dept/Lab: {c.get('department') or c.get('department_or_lab')}, Max Words: {c.get('text_capacity', {}).get('max_words', 400)}, "
                f"Images: {c.get('image_count', 1)}"
            )

        input_text = sanitize_text(
            f"Department / Laboratory: {department_or_lab}\n"
            f"Section: {section}\n"
            f"Available Photos: {photo_count}\n"
            f"Content Summary:\n{content_summary.strip()}\n\n"
            f"Candidate Templates:\n" + "\n".join(cand_summary)
        )

        content_hash = self._compute_hash(task, input_text)
        if self._is_duplicate(content_hash):
            return None
        self._register_hash(content_hash)

        output_dict = {
            "template_id": selected_template_id,
            "page_type": page_type,
            "confidence": 0.95,
            "reason": reason,
        }
        output_str = sanitize_text(json.dumps(output_dict, indent=2))

        metadata = DatasetExampleMetadata(
            id=f"mag-{self.dataset_version}-task5-{idx:04d}",
            task=task,
            dataset_version=self.dataset_version,
            content_hash=content_hash,
            input_word_count=len(input_text.split()),
            output_word_count=len(output_str.split()),
            provenance=DatasetProvenance(
                source_type="template_matcher",
                source_ref=source_ref,
                department_or_lab=department_or_lab,
            ),
        )

        return DatasetExample(
            instruction=instruction,
            input=input_text,
            output=output_str,
            metadata=metadata,
        )

    # ========================================================================
    # 8. Task 6: content + photographs -> selected photograph(s)
    # ========================================================================

    def make_photo_selection_example(
        self,
        article_text: str,
        photos: List[Dict[str, Any]],
        selected_photos: List[Dict[str, Any]],
        source_ref: str = "photo_curator",
        idx: int = 1,
    ) -> Optional[DatasetExample]:
        task = DatasetTaskType.PHOTO_SELECTION
        instruction = (
            "Given the magazine article content and a pool of available candidate photographs with visual tags "
            "and metadata, select and rank the most relevant photographs for the magazine layout. "
            "Return a JSON object with 'selected_photographs' specifying filename, slot, relevance_score, and rationale."
        )

        photo_desc = []
        for p in photos:
            photo_desc.append(
                f"- File: {p.get('filename')}, Tags: {', '.join(p.get('tags', []))}, "
                f"Aspect: {p.get('aspect_ratio', 'landscape')}, Quality: {p.get('quality_score', 90)}"
            )

        input_text = sanitize_text(
            f"Article Content:\n{article_text.strip()[:1000]}\n\n"
            f"Available Candidate Photographs:\n" + "\n".join(photo_desc)
        )

        content_hash = self._compute_hash(task, input_text)
        if self._is_duplicate(content_hash):
            return None
        self._register_hash(content_hash)

        output_dict = {
            "selected_photographs": selected_photos,
        }
        output_str = sanitize_text(json.dumps(output_dict, indent=2))

        metadata = DatasetExampleMetadata(
            id=f"mag-{self.dataset_version}-task6-{idx:04d}",
            task=task,
            dataset_version=self.dataset_version,
            content_hash=content_hash,
            input_word_count=len(input_text.split()),
            output_word_count=len(output_str.split()),
            provenance=DatasetProvenance(
                source_type="photo_ranker",
                source_ref=source_ref,
            ),
        )

        return DatasetExample(
            instruction=instruction,
            input=input_text,
            output=output_str,
            metadata=metadata,
        )

    # ========================================================================
    # 9. Synthetic & Real Exemplar Builders (Diverse Multi-Lab Coverage)
    # ========================================================================

    def generate_exemplar_catalog(self) -> List[DatasetExample]:
        """Generates rich, multi-lab examples across all 6 tasks to guarantee high variety."""
        examples: List[DatasetExample] = []

        # Multi-lab real/realistic domain exemplars
        labs_data = [
            {
                "lab": "AI Lab",
                "department": "Artificial Intelligence and Data Science",
                "headline": "Autonomous Quadruped Robot Navigates Real-Time Unstructured Campus Terrains",
                "content": (
                    "Engineering researchers at the SIET AI Lab deployed an autonomous quadruped machine "
                    "equipped with onboard stereo-vision cameras and quantized edge LLM reasoning. "
                    "During rigorous 48-hour field trials across campus lawns, pathways, and staircases, "
                    "the robot successfully avoided 140 dynamic obstacles while maintaining steady 15 FPS perception. "
                    "The breakthrough research was accepted for presentation at the IEEE ICRA regional summit."
                ),
                "caption": "SIET AI Lab research team testing autonomous quadruped obstacle traversal on campus grounds.",
                "section": "project_showcase",
                "section_reason": "Content details students developing a novel hardware and AI software robot prototype.",
                "template_id": "ai_lab_project_showcase",
                "page_type": "project_showcase",
                "template_reason": "AI Lab project showcase featuring prominent hero image and multi-column technical body text.",
                "photos": [
                    {"filename": "ai_lab_quadruped_field.jpg", "tags": ["robot", "quadruped", "outdoor", "ai"], "aspect_ratio": "landscape", "quality_score": 95},
                    {"filename": "ai_lab_board_schematic.jpg", "tags": ["circuit", "pcb", "close-up"], "aspect_ratio": "square", "quality_score": 88},
                    {"filename": "campus_lawn_general.jpg", "tags": ["campus", "trees", "building"], "aspect_ratio": "landscape", "quality_score": 82},
                ],
                "selected_photos": [
                    {"filename": "ai_lab_quadruped_field.jpg", "slot": "hero_image", "relevance_score": 0.96, "reason": "Directly portrays quadruped field test under outdoor conditions."},
                    {"filename": "ai_lab_board_schematic.jpg", "slot": "secondary_image", "relevance_score": 0.89, "reason": "Displays hardware processing board."},
                ],
            },
            {
                "lab": "IoT Lab",
                "department": "Internet of Things & Embedded Systems",
                "headline": "Smart Precision Agriculture Grid Monitors Micro-Climates Across Campus Polyhouses",
                "content": (
                    "The SIET IoT Lab completed installation of an automated environmental telemetry network "
                    "monitoring soil moisture, solar irradiance, ambient humidity, and nitrogen levels. "
                    "Consisting of 40 LoRaWAN battery-powered sensor nodes communicating with a central solar gateway, "
                    "the smart grid reduced campus greenhouse irrigation water consumption by 32% over 60 days."
                ),
                "caption": "Low-power LoRaWAN environmental telemetry sensor node installed in campus polyhouse.",
                "section": "project_showcase",
                "section_reason": "Focuses on applied IoT sensor hardware deployed for campus environmental monitoring.",
                "template_id": "iot_lab_smart_systems",
                "page_type": "project_showcase",
                "template_reason": "Dedicated IoT Lab template with telemetry metrics card and grid photo layout.",
                "photos": [
                    {"filename": "iot_sensor_polyhouse.jpg", "tags": ["sensor", "greenhouse", "agriculture", "lora"], "aspect_ratio": "landscape", "quality_score": 93},
                    {"filename": "iot_gateway_roof.jpg", "tags": ["antenna", "solar", "hardware"], "aspect_ratio": "portrait", "quality_score": 87},
                    {"filename": "general_meeting_room.jpg", "tags": ["chairs", "conference"], "aspect_ratio": "landscape", "quality_score": 75},
                ],
                "selected_photos": [
                    {"filename": "iot_sensor_polyhouse.jpg", "slot": "hero_image", "relevance_score": 0.95, "reason": "Shows smart agriculture LoRaWAN telemetry node in greenhouse."},
                    {"filename": "iot_gateway_roof.jpg", "slot": "secondary_image", "relevance_score": 0.88, "reason": "Shows rooftop receiver gateway antenna."},
                ],
            },
            {
                "lab": "Robotics Lab",
                "department": "Mechatronics and Robotics Engineering",
                "headline": "Six-Axis Collaborative Robotic Arm Achieves Sub-Millimeter Sorting Precision",
                "content": (
                    "Students at the SIET Robotics Lab unveiled a custom 6-DOF industrial collaborative manipulator "
                    "engineered for lightweight manufacturing assembly. Utilizing high-torque brushless DC servomotors, "
                    "harmonic drive gears, and ROS2 inverse kinematic controllers, the arm demonstrated sub-millimeter "
                    "repeatability across continuous 5,000-cycle component sorting benchmarks."
                ),
                "caption": "Final calibration of the 6-DOF robotic manipulator wrist assembly in the lab.",
                "section": "project_showcase",
                "section_reason": "Detailed project report on mechanical fabrication and kinematics of a robotic manipulator.",
                "template_id": "robotics_lab_autonomous_systems",
                "page_type": "project_showcase",
                "template_reason": "Tailored robotics layout with large mechanism hero slot and performance metrics.",
                "photos": [
                    {"filename": "robotics_arm_manipulator.jpg", "tags": ["robot", "arm", "gripper", "industry"], "aspect_ratio": "landscape", "quality_score": 96},
                    {"filename": "robotics_team_calibration.jpg", "tags": ["students", "calibrating", "lab"], "aspect_ratio": "landscape", "quality_score": 91},
                    {"filename": "auditorium_empty.jpg", "tags": ["hall", "stage"], "aspect_ratio": "landscape", "quality_score": 70},
                ],
                "selected_photos": [
                    {"filename": "robotics_arm_manipulator.jpg", "slot": "hero_image", "relevance_score": 0.97, "reason": "Captures the 6-DOF manipulator in operation."},
                    {"filename": "robotics_team_calibration.jpg", "slot": "secondary_image", "relevance_score": 0.90, "reason": "Portrays students performing precision calibration."},
                ],
            },
            {
                "lab": "Cyber Security Lab",
                "department": "Computer Science and Cyber Security",
                "headline": "SIET Ethical Hacking Squad Wins First Place in State CTF Championship",
                "content": (
                    "A squad of 4 undergraduate cyber security specialists from SIET emerged champions at the "
                    "Tamil Nadu Inter-College Cyber Defense Challenge 2026. Over 36 non-stop hours, the team solved "
                    "complex vulnerability exploitation challenges in binary reverse engineering, web security, and cryptographic protocol auditing."
                ),
                "caption": "SIET Cyber Security team analyzing packet captures during the 36-hour CTF marathon.",
                "section": "student_achievement",
                "section_reason": "Records competition award and victory by undergraduate student team in cyber defense.",
                "template_id": "cyber_security_lab_ctf",
                "page_type": "student_achievement",
                "template_reason": "High-contrast dark-mode cyber lab layout with team spotlight and scoreboard card.",
                "photos": [
                    {"filename": "cyber_ctf_team_terminals.jpg", "tags": ["team", "screens", "coding", "night"], "aspect_ratio": "landscape", "quality_score": 94},
                    {"filename": "cyber_trophy_presentation.jpg", "tags": ["trophy", "stage", "award"], "aspect_ratio": "landscape", "quality_score": 92},
                    {"filename": "empty_corridor.jpg", "tags": ["corridor", "empty"], "aspect_ratio": "landscape", "quality_score": 68},
                ],
                "selected_photos": [
                    {"filename": "cyber_ctf_team_terminals.jpg", "slot": "hero_image", "relevance_score": 0.96, "reason": "Directly captures team competing in CTF terminal room."},
                    {"filename": "cyber_trophy_presentation.jpg", "slot": "secondary_image", "relevance_score": 0.93, "reason": "Depicts trophy presentation on stage."},
                ],
            },
            {
                "lab": "Research Lab",
                "department": "Interdisciplinary Research Division",
                "headline": "Faculty Research Consortium Secures Major Grant for Clean Energy Microgrids",
                "content": (
                    "The SIET Research Council announced receipt of a prestigious research grant from the "
                    "Department of Science & Technology (DST) to design hybrid solar-wind microgrids with solid-state storage. "
                    "The initiative will support 6 PhD scholars and 12 graduate fellows over a 3-year term."
                ),
                "caption": "Principal investigator presenting microgrid architecture at the research summit.",
                "section": "faculty_achievement",
                "section_reason": "Announces major government research grant and faculty scholarship funding.",
                "template_id": "faculty_achievement_recognition",
                "page_type": "faculty_achievement",
                "template_reason": "Distinguished academic layout with portrait badge and citation panel.",
                "photos": [
                    {"filename": "research_pi_presentation.jpg", "tags": ["faculty", "presentation", "conference"], "aspect_ratio": "landscape", "quality_score": 95},
                    {"filename": "solar_panel_testbed.jpg", "tags": ["solar", "panels", "clean energy"], "aspect_ratio": "landscape", "quality_score": 89},
                    {"filename": "campus_parking.jpg", "tags": ["vehicles", "ground"], "aspect_ratio": "landscape", "quality_score": 72},
                ],
                "selected_photos": [
                    {"filename": "research_pi_presentation.jpg", "slot": "hero_image", "relevance_score": 0.94, "reason": "Shows principal investigator presenting grant proposal findings."},
                    {"filename": "solar_panel_testbed.jpg", "slot": "secondary_image", "relevance_score": 0.88, "reason": "Shows renewable microgrid test equipment."},
                ],
            },
            {
                "lab": "College Events",
                "department": "Student Affairs & Campus Life",
                "headline": "Annual National Cultural and Technical Fest Attracts 3,000 Delegates",
                "content": (
                    "Over three electric days, Sri Shakthi Institute of Engineering & Technology hosted delegates from "
                    "over 85 institutions across India for the annual cultural and techno-management confluence. "
                    "The fest featured 42 distinct competitions spanning robotics arenas, hackathons, music, and debates."
                ),
                "caption": "Crowd of student delegates during the grand inaugural ceremony in the open-air theatre.",
                "section": "events",
                "section_reason": "Reports on the multi-day campus-wide technical and cultural festival.",
                "template_id": "college_events_coverage",
                "page_type": "events",
                "template_reason": "Vibrant dynamic layout featuring photo grid and event schedule recap.",
                "photos": [
                    {"filename": "fest_inauguration_crowd.jpg", "tags": ["crowd", "stage", "lighting", "fest"], "aspect_ratio": "landscape", "quality_score": 96},
                    {"filename": "fest_robot_arena.jpg", "tags": ["robotics", "competition", "arena"], "aspect_ratio": "landscape", "quality_score": 92},
                    {"filename": "fest_dance_performance.jpg", "tags": ["dance", "stage", "culture"], "aspect_ratio": "landscape", "quality_score": 90},
                ],
                "selected_photos": [
                    {"filename": "fest_inauguration_crowd.jpg", "slot": "hero_image", "relevance_score": 0.97, "reason": "Captures festive atmosphere and scale of attendance."},
                    {"filename": "fest_robot_arena.jpg", "slot": "grid_photo_1", "relevance_score": 0.92, "reason": "Shows competitive robotics event in action."},
                ],
            },
        ]

        # Candidate templates pool for Task 5
        cand_templates = [
            {"template_id": "ai_lab_project_showcase", "name": "AI Lab Project Showcase", "page_type": "project_showcase", "department_or_lab": "AI Lab", "text_capacity": {"max_words": 400}, "image_count": 2},
            {"template_id": "iot_lab_smart_systems", "name": "IoT Lab Smart Systems", "page_type": "project_showcase", "department_or_lab": "IoT Lab", "text_capacity": {"max_words": 350}, "image_count": 2},
            {"template_id": "robotics_lab_autonomous_systems", "name": "Robotics Lab Autonomous Systems", "page_type": "project_showcase", "department_or_lab": "Robotics Lab", "text_capacity": {"max_words": 400}, "image_count": 2},
            {"template_id": "cyber_security_lab_ctf", "name": "Cyber Security Lab CTF Special", "page_type": "student_achievement", "department_or_lab": "Cyber Security Lab", "text_capacity": {"max_words": 300}, "image_count": 2},
            {"template_id": "faculty_achievement_recognition", "name": "Faculty Achievement Recognition", "page_type": "faculty_achievement", "department_or_lab": "Research Lab", "text_capacity": {"max_words": 350}, "image_count": 2},
            {"template_id": "college_events_coverage", "name": "College Events Coverage", "page_type": "events", "department_or_lab": "College Events", "text_capacity": {"max_words": 450}, "image_count": 3},
            {"template_id": "lab_introduction_overview", "name": "Lab Introduction Overview", "page_type": "introduction", "department_or_lab": "College", "text_capacity": {"max_words": 400}, "image_count": 1},
        ]

        idx = 100
        for data in labs_data:
            idx += 1
            # Task 2: headline
            h_ex = self.make_raw_to_headline_example(
                content=data["content"],
                expected_headline=data["headline"],
                source_ref=f"exemplar_{data['lab'].lower().replace(' ', '_')}",
                idx=idx,
            )
            if h_ex:
                examples.append(h_ex)

            # Task 3: caption
            c_ex = self.make_raw_to_caption_example(
                context=f"Event/Lab: {data['lab']}\nContext: {data['content']}\nVisual role: Hero photograph",
                expected_caption=data["caption"],
                source_ref=f"exemplar_{data['lab'].lower().replace(' ', '_')}",
                idx=idx,
            )
            if c_ex:
                examples.append(c_ex)

            # Task 4: section classification
            s_ex = self.make_section_classification_example(
                content=f"Title: {data['headline']}\n{data['content']}",
                expected_section=data["section"],
                reason=data["section_reason"],
                source_ref=f"exemplar_{data['lab'].lower().replace(' ', '_')}",
                idx=idx,
            )
            if s_ex:
                examples.append(s_ex)

            # Task 5: template selection
            t_ex = self.make_template_selection_example(
                content_summary=data["content"],
                department_or_lab=data["lab"],
                section=data["section"],
                photo_count=len(data["photos"]),
                candidates=cand_templates,
                selected_template_id=data["template_id"],
                page_type=data["page_type"],
                reason=data["template_reason"],
                source_ref=f"exemplar_{data['lab'].lower().replace(' ', '_')}",
                idx=idx,
            )
            if t_ex:
                examples.append(t_ex)

            # Task 6: photo selection
            p_ex = self.make_photo_selection_example(
                article_text=f"{data['headline']}\n\n{data['content']}",
                photos=data["photos"],
                selected_photos=data["selected_photos"],
                source_ref=f"exemplar_{data['lab'].lower().replace(' ', '_')}",
                idx=idx,
            )
            if p_ex:
                examples.append(p_ex)

        return examples

    # ========================================================================
    # 10. Master Pipeline Ingestion
    # ========================================================================

    def generate_all_examples_from_sources(
        self,
        source_dir: Path,
    ) -> List[DatasetExample]:
        """Ingests real files from source directory and augments with multi-lab exemplars."""
        all_examples: List[DatasetExample] = []
        doc_count = 0

        # Scan for supported document files
        supported_exts = {".docx", ".pdf", ".txt", ".md"}
        candidate_files = []
        if source_dir.exists():
            for p in sorted(source_dir.rglob("*")):
                if p.is_file() and p.suffix.lower() in supported_exts:
                    candidate_files.append(p)

        for fpath in candidate_files:
            doc_info = self.parse_document_file(fpath)
            raw_text = doc_info.get("text", "")
            if len(raw_text) < 80:
                continue

            doc_count += 1

            # Task 1: raw document -> structured magazine content
            t1_ex = self.make_raw_to_structured_example(doc_info, idx=doc_count)
            if t1_ex:
                all_examples.append(t1_ex)

            # Task 2: headline
            event_name = doc_info.get("event_name", "SIET Campus Event")
            t2_ex = self.make_raw_to_headline_example(
                content=raw_text[:800],
                expected_headline=f"Key Highlights and Proceedings from {event_name}",
                source_ref=doc_info.get("filename", "doc"),
                idx=doc_count,
            )
            if t2_ex:
                all_examples.append(t2_ex)

            # Task 3: caption
            t3_ex = self.make_raw_to_caption_example(
                context=f"Photograph taken during {event_name}. Context: {raw_text[:400]}",
                expected_caption=f"Participants and faculty mentors engaged during proceedings of {event_name}.",
                source_ref=doc_info.get("filename", "doc"),
                idx=doc_count,
            )
            if t3_ex:
                all_examples.append(t3_ex)

            # Task 4: section classification
            t4_ex = self.make_section_classification_example(
                content=f"{event_name}\n\n{raw_text[:500]}",
                expected_section="events" if "event" in event_name.lower() or "fest" in event_name.lower() else "project_showcase",
                reason=f"Content describes proceedings of {event_name}.",
                source_ref=doc_info.get("filename", "doc"),
                idx=doc_count,
            )
            if t4_ex:
                all_examples.append(t4_ex)

        # Augment with rich multi-lab exemplars across all 6 tasks
        exemplar_examples = self.generate_exemplar_catalog()
        all_examples.extend(exemplar_examples)

        return all_examples

    # ========================================================================
    # 11. Deterministic Partitioning & Verification
    # ========================================================================

    def partition_examples(
        self,
        examples: List[DatasetExample],
    ) -> Tuple[List[DatasetExample], List[DatasetExample], List[DatasetExample]]:
        """
        Splits examples deterministically into train, val, test splits according to split_config.
        Strictly guarantees ZERO DUPLICATES across splits.
        """
        # Stratify by task type so every task is represented across splits
        by_task: Dict[DatasetTaskType, List[DatasetExample]] = collections.defaultdict(list)
        for ex in examples:
            task = DatasetTaskType.RAW_TO_STRUCTURED
            if ex.metadata and hasattr(ex.metadata, "task"):
                task = ex.metadata.task
            elif ex.metadata and isinstance(ex.metadata, dict) and "task" in ex.metadata:
                task = DatasetTaskType(ex.metadata["task"])
            by_task[task].append(ex)

        train_list: List[DatasetExample] = []
        val_list: List[DatasetExample] = []
        test_list: List[DatasetExample] = []

        cfg = self.split_config

        for task, task_examples in by_task.items():
            # Sort deterministically by content hash
            sorted_examples = sorted(
                task_examples,
                key=lambda e: (
                    e.metadata.content_hash
                    if hasattr(e.metadata, "content_hash")
                    else hashlib.sha256(e.input.encode("utf-8")).hexdigest()
                ),
            )

            n = len(sorted_examples)
            if n == 1:
                train_list.append(sorted_examples[0])
            elif n == 2:
                train_list.append(sorted_examples[0])
                val_list.append(sorted_examples[1])
            else:
                n_val = max(1, int(round(n * cfg.val_ratio)))
                n_test = max(1, int(round(n * cfg.test_ratio)))
                n_train = n - n_val - n_test

                if n_train <= 0:
                    n_train = 1
                    n_val = max(1, (n - 1) // 2)
                    n_test = n - n_train - n_val

                train_slice = sorted_examples[:n_train]
                val_slice = sorted_examples[n_train : n_train + n_val]
                test_slice = sorted_examples[n_train + n_val :]

                for ex in train_slice:
                    if hasattr(ex.metadata, "split"):
                        ex.metadata.split = DatasetSplit.TRAIN
                    train_list.append(ex)
                for ex in val_slice:
                    if hasattr(ex.metadata, "split"):
                        ex.metadata.split = DatasetSplit.VAL
                    val_list.append(ex)
                for ex in test_slice:
                    if hasattr(ex.metadata, "split"):
                        ex.metadata.split = DatasetSplit.TEST
                    test_list.append(ex)

        # STRICT VERIFICATION: Assert zero cross-split overlap
        train_hashes = {
            ex.metadata.content_hash if hasattr(ex.metadata, "content_hash") else ex.input
            for ex in train_list
        }
        val_hashes = {
            ex.metadata.content_hash if hasattr(ex.metadata, "content_hash") else ex.input
            for ex in val_list
        }
        test_hashes = {
            ex.metadata.content_hash if hasattr(ex.metadata, "content_hash") else ex.input
            for ex in test_list
        }

        assert train_hashes.isdisjoint(val_hashes), "CRITICAL: Train and Validation splits overlap!"
        assert train_hashes.isdisjoint(test_hashes), "CRITICAL: Train and Test splits overlap!"
        assert val_hashes.isdisjoint(test_hashes), "CRITICAL: Validation and Test splits overlap!"

        return train_list, val_list, test_list

    # ========================================================================
    # 12. Statistics Calculation
    # ========================================================================

    def calculate_statistics(
        self,
        train_examples: List[DatasetExample],
        val_examples: List[DatasetExample],
        test_examples: List[DatasetExample],
    ) -> DatasetStats:
        """Computes comprehensive metrics and distributions across the dataset."""
        all_examples = train_examples + val_examples + test_examples
        total = len(all_examples)

        split_counts = {
            "train": len(train_examples),
            "val": len(val_examples),
            "test": len(test_examples),
        }

        task_counts: Dict[str, int] = collections.defaultdict(int)
        input_word_counts: List[int] = []
        output_word_counts: List[int] = []
        sources: Set[str] = set()
        vocab: Set[str] = set()
        word_freq: collections.Counter = collections.Counter()

        for ex in all_examples:
            t = "unknown"
            if ex.metadata and hasattr(ex.metadata, "task"):
                t = ex.metadata.task.value
            elif ex.metadata and isinstance(ex.metadata, dict) and "task" in ex.metadata:
                t = str(ex.metadata["task"])
            task_counts[t] += 1

            in_words = ex.input.split()
            out_words = ex.output.split()
            input_word_counts.append(len(in_words))
            output_word_counts.append(len(out_words))

            for w in in_words + out_words:
                clean_w = re.sub(r"[^a-zA-Z]", "", w).lower()
                if len(clean_w) > 3:
                    vocab.add(clean_w)
                    word_freq[clean_w] += 1

            if ex.metadata and hasattr(ex.metadata, "provenance") and ex.metadata.provenance:
                sources.add(ex.metadata.provenance.source_ref)

        stop_words = {"this", "that", "with", "from", "were", "have", "been", "their", "into", "also", "about", "which"}
        top_terms = [
            w for w, _ in word_freq.most_common(30)
            if w not in stop_words
        ][:15]

        avg_in = float(sum(input_word_counts) / max(1, total))
        avg_out = float(sum(output_word_counts) / max(1, total))

        return DatasetStats(
            dataset_version=self.dataset_version,
            total_examples=total,
            split_counts=split_counts,
            task_counts=dict(task_counts),
            avg_input_words=round(avg_in, 1),
            avg_output_words=round(avg_out, 1),
            max_input_words=max(input_word_counts) if input_word_counts else 0,
            max_output_words=max(output_word_counts) if output_word_counts else 0,
            unique_sources_count=len(sources),
            vocabulary_size=len(vocab),
            top_terms=top_terms,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
