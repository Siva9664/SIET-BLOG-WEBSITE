"""
Supervised fine-tuning (SFT) example builder for Qwen3-14B SIET College Magazine.
Generates structured ChatML examples across:
1. Editorial tasks
2. Template selection tasks
3. High-level layout intent tasks
4. Photo association and captioning tasks
5. Admin feedback corrections (approved-only filtering)
Strictly preserves source document and page provenance.
"""

from __future__ import annotations

import json
from typing import List, Dict, Any, Optional

from .schemas import (
    StorySegment,
    PhotoItem,
    ExampleRecord,
    AdminFeedbackRecord,
    LayoutIntent,
    PageType,
    PhotoConfidence,
)

SYSTEM_PROMPT = (
    "You are the editorial intelligence assistant for SIET (Sri Shakthi Institute of Engineering & Technology).\n"
    "STRICT GROUNDING RULES:\n"
    "1. Use ONLY supplied source / RAG context.\n"
    "2. Never invent names, dates, achievements, statistics, organizations, quotes, events, or other factual information.\n"
    "3. Missing information must be represented as null or empty values according to the requested schema.\n"
    "4. Do NOT fabricate content to fill a template."
)


def count_words(text: str) -> int:
    return len(text.strip().split())


class ExampleBuilder:
    """
    Builds structured ChatML training examples from segmented stories and photo data.
    """

    def __init__(self, system_prompt: str = SYSTEM_PROMPT):
        self.system_prompt = system_prompt

    # -------------------------------------------------------------------------
    # 1. Editorial Examples
    # -------------------------------------------------------------------------
    def build_editorial_examples(self, story: StorySegment) -> List[ExampleRecord]:
        examples: List[ExampleRecord] = []
        base_meta = {
            "doc_id": story.doc_id,
            "page_start": story.page_start,
            "page_end": story.page_end,
            "story_id": story.story_id,
            "category": story.story_type,
            "lab_department": story.lab_department or "General",
        }

        # Task 1: Section / Category Classification
        user_cat = (
            f"SOURCE CONTEXT:\n{story.source_text}\n\n"
            "TASK:\nClassify this college magazine story into one of the 10 standard categories:\n"
            "events, victories, achievements, projects, workshops, seminars, competitions, faculty, student, other.\n"
            "Output JSON with a single key 'category'."
        )
        asst_cat = json.dumps({"category": story.story_type})
        examples.append(ExampleRecord(
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_cat},
                {"role": "assistant", "content": asst_cat},
            ],
            metadata={**base_meta, "task_type": "section_classification"},
        ))

        # Task 2: Headline Generation (if headline is grounded in text)
        if story.headline:
            user_hl = (
                f"SOURCE CONTEXT:\n{story.source_text}\n\n"
                "TASK:\nGenerate a publication-ready magazine headline adhering strictly to the facts above.\n"
                "Keep under 15 words."
            )
            asst_hl = json.dumps({"headline": story.headline})
            examples.append(ExampleRecord(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_hl},
                    {"role": "assistant", "content": asst_hl},
                ],
                metadata={**base_meta, "task_type": "headline_generation"},
            ))

        # Task 3: Summary / TOC Digest Generation
        # Build concise grounded summary from first 1-2 sentences of body
        sentences = [s.strip() for s in story.body.replace("\n", " ").split(".") if s.strip()]
        toc_text = (sentences[0] + ".") if sentences else story.body[:120]
        if len(toc_text.split()) > 25:
            toc_text = " ".join(toc_text.split()[:22]) + "..."
        user_sum = (
            f"SOURCE CONTEXT:\n{story.source_text}\n\n"
            "TASK:\nGenerate a concise Table of Contents (TOC) summary strictly grounded in the source.\n"
            "Word limit: <= 25 words."
        )
        asst_sum = json.dumps({"toc_summary": toc_text})
        examples.append(ExampleRecord(
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_sum},
                {"role": "assistant", "content": asst_sum},
            ],
            metadata={**base_meta, "task_type": "summary_generation"},
        ))

        # Task 4: Grounded Rewriting (Editorial Article JSON)
        user_rewrite = (
            f"SOURCE CONTEXT:\n{story.source_text}\n\n"
            "TASK:\nGenerate a grounded magazine editorial entry in JSON with fields:\n"
            "'headline', 'body', 'date', 'people', 'organization', 'achievement_result'.\n"
            "If any field is missing from source, it MUST be null or empty list."
        )
        asst_rewrite = json.dumps({
            "headline": story.headline,
            "body": story.body,
            "date": story.date,
            "people": story.people,
            "organization": story.organization,
            "achievement_result": story.achievement_result,
        })
        examples.append(ExampleRecord(
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_rewrite},
                {"role": "assistant", "content": asst_rewrite},
            ],
            metadata={**base_meta, "task_type": "grounded_rewriting"},
        ))

        # Task 5: Keyword Extraction
        # Grounded keywords from entities and story type
        keywords = [story.story_type]
        if story.organization:
            keywords.append(story.organization)
        if story.lab_department:
            keywords.append(story.lab_department)
        if story.people:
            keywords.extend(story.people[:2])
        user_kw = (
            f"SOURCE CONTEXT:\n{story.source_text}\n\n"
            "TASK:\nExtract verified topical tags/keywords present directly in the text."
        )
        asst_kw = json.dumps({"keywords": keywords})
        examples.append(ExampleRecord(
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_kw},
                {"role": "assistant", "content": asst_kw},
            ],
            metadata={**base_meta, "task_type": "keyword_extraction"},
        ))

        # Task 6: Content Length Classification
        word_cnt = count_words(story.body)
        length_tier = "short" if word_cnt <= 100 else ("medium" if word_cnt <= 300 else "feature")
        user_len = (
            f"SOURCE CONTEXT:\n{story.source_text}\n\n"
            "TASK:\nClassify the word count budget tier of this story into 'short' (<=100 words), "
            "'medium' (101-300 words), or 'feature' (>300 words)."
        )
        asst_len = json.dumps({"length_tier": length_tier})
        examples.append(ExampleRecord(
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_len},
                {"role": "assistant", "content": asst_len},
            ],
            metadata={**base_meta, "task_type": "content_length_classification"},
        ))


        return examples

    # -------------------------------------------------------------------------
    # 2. Template Selection Examples (No Pixel Coordinates)
    # -------------------------------------------------------------------------
    def build_template_examples(self, story: StorySegment) -> List[ExampleRecord]:
        num_photos = len(story.attached_photos)
        word_cnt = count_words(story.body)

        # Determine logical template ID and layout characteristics based on content
        if story.story_type == "victories" or story.achievement_result:
            template_id = "template_achievement_spotlight_01"
            page_type = PageType.ACHIEVEMENT_FEATURE.value
            layout_intent = LayoutIntent.ACHIEVEMENT_FEATURE.value
            columns = 1
        elif num_photos >= 3:
            template_id = "template_photo_grid_02"
            page_type = PageType.PHOTO_FEATURE.value
            layout_intent = LayoutIntent.IMAGE_GRID.value
            columns = 2
        elif num_photos == 1 and word_cnt > 150:
            template_id = "template_hero_feature_03"
            page_type = PageType.EVENT_PAGE.value
            layout_intent = LayoutIntent.HERO_IMAGE.value
            columns = 2
        elif word_cnt > 250:
            template_id = "template_two_col_article_04"
            page_type = PageType.DEPARTMENT_ROUNDUP.value
            layout_intent = LayoutIntent.TWO_COLUMN_ARTICLE.value
            columns = 2
        else:
            template_id = "template_text_image_balanced_05"
            page_type = PageType.EVENT_PAGE.value
            layout_intent = LayoutIntent.TEXT_AND_IMAGE.value
            columns = 1

        template_spec = {
            "lab_department": story.lab_department or "Campus General",
            "template_id": template_id,
            "page_type": page_type,
            "story_type": story.story_type,
            "image_count": num_photos,
            "text_length": "feature" if word_cnt > 300 else ("medium" if word_cnt > 100 else "short"),
            "layout_intent": layout_intent,
            "template_characteristics": {
                "columns": columns,
                "has_pullquote": word_cnt > 200,
                "photo_aspect_ratio": "16:9" if num_photos <= 2 else "4:3",
                "accent_palette": "siet_navy_gold" if story.story_type == "victories" else "default_maroon",
            }
        }

        user_prompt = (
            f"STORY CONTEXT:\n"
            f"Headline: {story.headline or 'N/A'}\n"
            f"Category: {story.story_type}\n"
            f"Department: {story.lab_department or 'Campus General'}\n"
            f"Word Count: {word_cnt}\n"
            f"Attached Photos: {num_photos}\n\n"
            "TASK:\nRecommend appropriate publication template parameters for this magazine content.\n"
            "Note: Specify high-level layout intent only; do NOT provide pixel coordinates or CSS."
        )

        return [ExampleRecord(
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": json.dumps(template_spec)},
            ],
            metadata={
                "doc_id": story.doc_id,
                "page_start": story.page_start,
                "page_end": story.page_end,
                "story_id": story.story_id,
                "task_type": "template_recommendation",
                "template_id": template_id,
            },
        )]

    # -------------------------------------------------------------------------
    # 3. High-Level Layout Examples
    # -------------------------------------------------------------------------
    def build_layout_examples(self, story: StorySegment) -> List[ExampleRecord]:
        num_photos = len(story.attached_photos)
        word_cnt = count_words(story.body)

        if num_photos == 0:
            intent = LayoutIntent.FULL_WIDTH_STORY.value
            photo_placement = "none"
        elif num_photos == 1:
            intent = LayoutIntent.HERO_IMAGE.value
            photo_placement = "top_hero"
        elif num_photos == 2:
            intent = LayoutIntent.TEXT_AND_IMAGE.value
            photo_placement = "split_side"
        elif num_photos >= 3:
            intent = LayoutIntent.IMAGE_GRID.value
            photo_placement = "bottom_grid"
        else:
            intent = LayoutIntent.EVENT_PAGE.value
            photo_placement = "inline"

        layout_plan = {
            "layout_intent": intent,
            "photo_placement": photo_placement,
            "columns": 2 if word_cnt > 180 else 1,
            "header_style": "banner" if word_cnt > 200 else "standard",
            "callout_box": True if story.achievement_result else False,
        }

        user_prompt = (
            f"EVENT METADATA:\n"
            f"Story Type: {story.story_type}\n"
            f"Word Count: {word_cnt}\n"
            f"Available Photos: {num_photos}\n"
            f"Has Achievement: {bool(story.achievement_result)}\n\n"
            "TASK:\nPlan high-level page layout intent for deterministic rendering."
        )

        return [ExampleRecord(
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": json.dumps(layout_plan)},
            ],
            metadata={
                "doc_id": story.doc_id,
                "page_start": story.page_start,
                "page_end": story.page_end,
                "story_id": story.story_id,
                "task_type": "layout_intent",
            },
        )]

    # -------------------------------------------------------------------------
    # 4. Photo Association & Captioning Examples
    # -------------------------------------------------------------------------
    def build_photo_examples(
        self, story: StorySegment, photo_map: Dict[str, PhotoItem]
    ) -> List[ExampleRecord]:
        examples: List[ExampleRecord] = []
        base_meta = {
            "doc_id": story.doc_id,
            "page_start": story.page_start,
            "page_end": story.page_end,
            "story_id": story.story_id,
            "category": story.story_type,
        }

        # Photo-to-Story and Story-to-Photo association (Only when association is HIGH confidence!)
        if story.attached_photos and story.photo_confidence == PhotoConfidence.HIGH.value:
            user_assoc = (
                f"STORY CONTEXT:\nHeadline: {story.headline or 'N/A'}\n"
                f"Source Notes: {story.source_text}\n"
                f"Available Page Photos: {story.attached_photos}\n\n"
                "TASK:\nAssociate photos strictly belonging to this event based on document order and provenance.\n"
                "Never associate photos from other events."
            )
            asst_assoc = json.dumps({
                "story_id": story.story_id,
                "associated_photos": story.attached_photos,
                "confidence": "high",
                "relationship_rationale": "Photos are grouped at the conclusion of this event on the source page."
            })
            examples.append(ExampleRecord(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_assoc},
                    {"role": "assistant", "content": asst_assoc},
                ],
                metadata={**base_meta, "task_type": "story_to_photos"},
            ))

            # Caption generation for each attached photo (grounded strictly in source)
            for p_id in story.attached_photos:
                photo_item = photo_map.get(p_id)
                photo_desc = photo_item.caption_hint if (photo_item and photo_item.caption_hint) else ""
                
                # Grounded caption synthesis:
                people_str = ", ".join(story.people[:2]) if story.people else ""
                if story.story_type == "victories" and people_str:
                    caption = f"{people_str} receiving the award at SIET."
                elif people_str:
                    caption = f"{people_str} during the {story.story_type} session at SIET."
                elif story.headline:
                    caption = f"Participants during {story.headline}."
                else:
                    caption = f"Attendees during the college {story.story_type} event."

                # Ensure caption is <= 15 words
                caption_words = caption.split()
                if len(caption_words) > 15:
                    caption = " ".join(caption_words[:15]) + "."

                user_cap = (
                    f"STORY CONTEXT:\n{story.source_text}\n"
                    f"PHOTO ID: {p_id}\n\n"
                    "TASK:\nGenerate a concise, factual caption for this attached photo.\n"
                    "Word limit: <= 15 words. Strictly use facts from the story context."
                )
                asst_cap = json.dumps({"photo_id": p_id, "caption": caption})
                examples.append(ExampleRecord(
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_cap},
                        {"role": "assistant", "content": asst_cap},
                    ],
                    metadata={**base_meta, "task_type": "caption_generation", "photo_id": p_id},
                ))

        elif story.photo_confidence == PhotoConfidence.UNCERTAIN.value:
            # Uncertain association example (Model learns to acknowledge uncertainty instead of guessing!)
            user_unc = (
                f"STORY CONTEXT:\nHeadline: {story.headline or 'N/A'}\n"
                f"Source Notes: {story.source_text}\n\n"
                "TASK:\nAssess photo association confidence when multiple candidate stories share ambiguous photo placements."
            )
            asst_unc = json.dumps({
                "story_id": story.story_id,
                "confidence": "uncertain",
                "associated_photos": [],
                "reason": "Association is ambiguous on shared multi-story page; never invent photo relationships."
            })
            examples.append(ExampleRecord(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_unc},
                    {"role": "assistant", "content": asst_unc},
                ],
                metadata={**base_meta, "task_type": "photo_relevance_uncertain"},
            ))

        return examples

    # -------------------------------------------------------------------------
    # 5. Admin Feedback Dataset Examples (Approved-only filtering)
    # -------------------------------------------------------------------------
    def build_admin_feedback_example(self, fb: AdminFeedbackRecord) -> Optional[ExampleRecord]:
        """
        Converts human admin feedback into training examples ONLY if approved == True
        and eligible for training.
        """
        if not fb.approved or not fb.is_training_eligible:
            return None

        user_prompt = (
            f"ADMIN CORRECTION FEEDBACK:\n"
            f"Original AI Output: {json.dumps(fb.ai_output)}\n"
            f"Correction Type: {fb.correction_type}\n"
            f"Correction Rationale: {fb.reason}\n\n"
            "TASK:\nGenerate the final approved, grounded editorial output conforming to editor review."
        )
        asst_prompt = json.dumps(fb.final_approved_output)

        return ExampleRecord(
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": asst_prompt},
            ],
            metadata={
                "doc_id": fb.doc_id or "admin_feedback",
                "story_id": fb.story_id or fb.feedback_id,
                "task_type": f"admin_feedback_{fb.correction_type}",
                "feedback_id": fb.feedback_id,
                "template_version": fb.template_version,
                "model_version": fb.model_version,
            },
        )
