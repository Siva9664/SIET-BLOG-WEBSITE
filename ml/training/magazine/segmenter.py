"""
Event and story segmentation engine for college magazines and reports.
Extracts individual stories, events, victories, achievements, and metadata
without hallucinating missing fields.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple, Dict, Any

from .schemas import DocumentRecord, PageData, StorySegment, StoryType


# Department indicators
DEPT_PATTERNS = [
    (r"Computer Science (?:&|and) Engineering|CSE", "Computer Science & Engineering"),
    (r"Electronics (?:&|and) Communication Engineering|ECE", "Electronics & Communication Engineering"),
    (r"Electrical (?:&|and) Electronics Engineering|EEE", "Electrical & Electronics Engineering"),
    (r"Mechanical Engineering|MECH", "Mechanical Engineering"),
    (r"Artificial Intelligence (?:&|and) Data Science|AI & DS|AI&DS", "Artificial Intelligence & Data Science"),
    (r"Information Technology|IT", "Information Technology"),
    (r"Biomedical Engineering|BME", "Biomedical Engineering"),
    (r"Civil Engineering|CIVIL", "Civil Engineering"),
    (r"Science (?:&|and) Humanities|S&H", "Science & Humanities"),
    (r"Management Studies|MBA", "Department of Management Studies"),
]

# Classification keywords
VICTORY_KEYWORDS = [
    r"\bwon\b", r"\bwinner\b", r"\bfirst prize\b", r"\bsecond prize\b", r"\bthird prize\b",
    r"\b1st prize\b", r"\b2nd prize\b", r"\b3rd prize\b", r"\bchampion\b", r"\btriumph\b",
    r"\bgold medal\b", r"\bsilver medal\b", r"\bbronze medal\b", r"\brunner[ -]up\b", r"\bbagged\b"
]

ACHIEVEMENT_KEYWORDS = [
    r"\bgrant\b", r"\bfunded\b", r"\binr\s*\d+", r"\blakhs?\b", r"\bpatent\b",
    r"\bpublished\b", r"\bdistinction\b", r"\brecognition\b", r"\bawarded\b",
    r"\bexcellence award\b", r"\bfaculty award\b"
]

WORKSHOP_KEYWORDS = [
    r"\bworkshop\b", r"\bhands-on\b", r"\btraining program\b", r"\bbootcamp\b", r"\bmasterclass\b"
]

SEMINAR_KEYWORDS = [
    r"\bseminar\b", r"\bwebinar\b", r"\bguest lecture\b", r"\binvited talk\b",
    r"\bsymposium\b", r"\bkeynote address\b"
]

COMPETITION_KEYWORDS = [
    r"\bhackathon\b", r"\bcontest\b", r"\bcompetition\b", r"\btournament\b",
    r"\bcoding challenge\b", r"\bideathon\b"
]

PROJECT_KEYWORDS = [
    r"\bproject expo\b", r"\bcapstone\b", r"\bprototype\b", r"\binnovation display\b",
    r"\bproject demonstration\b", r"\bhardware demo\b"
]

FACULTY_KEYWORDS = [
    r"\bfaculty development\b", r"\bfdp\b", r"\bph\.?d\b", r"\bprofessor\b",
    r"\bassociate professor\b", r"\bassistant professor\b", r"\bdr\.\s+[a-z]"
]

STUDENT_KEYWORDS = [
    r"\bstudent club\b", r"\bnss\b", r"\byrc\b", r"\brotaract\b", r"\bcultural\b",
    r"\bsports day\b", r"\bathletics\b", r"\bblood donation\b"
]


def classify_story_type(text: str, headline: str = "") -> str:
    """Classifies a text block into one of the 10 standard story categories."""
    combined = f"{headline}\n{text}".lower()

    # Priority 1: Victory / Competition results
    if any(re.search(kw, combined) for kw in VICTORY_KEYWORDS):
        return StoryType.VICTORIES.value

    # Priority 2: Grants / Patents / Formal Achievements
    if any(re.search(kw, combined) for kw in ACHIEVEMENT_KEYWORDS):
        return StoryType.ACHIEVEMENTS.value

    # Priority 3: Workshops
    if any(re.search(kw, combined) for kw in WORKSHOP_KEYWORDS):
        return StoryType.WORKSHOPS.value

    # Priority 4: Seminars & Guest Lectures
    if any(re.search(kw, combined) for kw in SEMINAR_KEYWORDS):
        return StoryType.SEMINARS.value

    # Priority 5: Competitions
    if any(re.search(kw, combined) for kw in COMPETITION_KEYWORDS):
        return StoryType.COMPETITIONS.value

    # Priority 6: Projects
    if any(re.search(kw, combined) for kw in PROJECT_KEYWORDS):
        return StoryType.PROJECTS.value

    # Priority 7: Faculty specific
    if any(re.search(kw, combined) for kw in FACULTY_KEYWORDS) and not any(re.search(kw, combined) for kw in STUDENT_KEYWORDS):
        return StoryType.FACULTY.value

    # Priority 8: Student specific
    if any(re.search(kw, combined) for kw in STUDENT_KEYWORDS):
        return StoryType.STUDENT.value

    # Priority 9: General campus events
    if re.search(r"\bevent\b|\bcelebration\b|\binauguration\b|\bannual day\b|\bconvocation\b|\bconference\b", combined):
        return StoryType.EVENTS.value

    return StoryType.OTHER.value


def extract_dates(text: str) -> Optional[str]:
    """Extracts date strings without inventing or extrapolating."""
    patterns = [
        r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?(?:[–\-]\d{1,2}(?:st|nd|rd|th)?)?(?:,\s*\d{4})?\b",
        r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)(?:,\s*\d{4})?\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2}(?:[–\-]\d{1,2})?(?:,\s*\d{4})?\b",
        r"\b\d{1,2}[/-]\d{1,2}[/-]20\d{2}\b",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return None


def extract_people(text: str) -> List[str]:
    """Extracts names of people with honorific titles or roles strictly grounded in text."""
    names = []
    # Match Dr. / Prof. / Er. / Mr. / Ms. / Mrs. [Initials.] Name
    title_pattern = r"\b(?:Dr\.|Prof\.|Er\.|Mr\.|Ms\.|Mrs\.)\s+(?:[A-Z]\.\s*)*[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*"
    for m in re.finditer(title_pattern, text):
        name = m.group(0).strip()
        if name not in names:
            names.append(name)

    # Match "by <Name>" in prize/victory contexts
    by_pattern = r"\bwon by\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)"
    for m in re.finditer(by_pattern, text):
        name = m.group(1).strip()
        if name not in names and len(name.split()) <= 4:
            names.append(name)

    return names



def extract_organization(text: str) -> Optional[str]:
    """Extracts organizing body or partner company strictly grounded in text."""
    org_patterns = [
        r"\b(?:organized by|hosted by|conducted by)\s+([^.,;\n]+)",
        r"\b(?:in collaboration with|sponsored by|funded by)\s+([^.,;\n]+)",
    ]
    for p in org_patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            org = m.group(1).strip()
            # Clean trailing words
            org = re.split(r"\b(?:on|at|during|for)\b", org, flags=re.IGNORECASE)[0].strip()
            if org and len(org) < 80:
                return org

    # Department check
    for p, dept_name in DEPT_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            return dept_name

    return None


def extract_achievement_result(text: str) -> Optional[str]:
    """Extracts explicit prize, award, or financial funding strictly grounded in text."""
    result_patterns = [
        r"\b(?:First|1st|Second|2nd|Third|3rd)\s+Prize\b",
        r"\b(?:First|1st|Second|2nd|Third|3rd)\s+Place\b",
        r"\b(?:Gold|Silver|Bronze)\s+Medal\b",
        r"\bRunner[ -]up\b",
        r"\bINR\s*[\d,]+(?:\s*Lakhs?|\s*Crores?)?\b",
        r"\b₹\s*[\d,]+(?:\s*Lakhs?|\s*Crores?)?\b",
        r"\bCash award of\s*[^.,;\n]+",
    ]
    for p in result_patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return None


def extract_department(text: str) -> Optional[str]:
    """Extracts department name if present in text."""
    for p, dept_name in DEPT_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            return dept_name
    return None


class StorySegmenter:
    """
    Segments a DocumentRecord into discrete, well-defined StorySegments.
    """

    def segment_document(self, doc: DocumentRecord) -> List[StorySegment]:
        stories: List[StorySegment] = []

        for page in doc.pages:
            page_stories = self.segment_page(page, doc.doc_id)
            stories.extend(page_stories)

        return stories

    def segment_page(self, page: PageData, doc_id: str) -> List[StorySegment]:
        text = page.text.strip()
        if not text:
            return []

        # Split text into candidate story chunks
        raw_chunks = self._split_text_chunks(text)
        page_stories: List[StorySegment] = []

        for idx, chunk in enumerate(raw_chunks, start=1):
            if not chunk.strip():
                continue

            lines = [l.strip() for l in chunk.strip().splitlines() if l.strip()]
            if not lines:
                continue

            headline, body = self._extract_headline_and_body(lines)
            story_type = classify_story_type(body, headline or "")

            story_id = f"{doc_id}_p{page.page_number}_s{idx}"
            date_val = extract_dates(chunk)
            people_val = extract_people(chunk)
            org_val = extract_organization(chunk)
            res_val = extract_achievement_result(chunk)
            dept_val = extract_department(chunk)

            story = StorySegment(
                story_id=story_id,
                doc_id=doc_id,
                story_type=story_type,
                page_start=page.page_number,
                page_end=page.page_number,
                headline=headline,
                body=body,
                date=date_val,
                people=people_val,
                organization=org_val,
                achievement_result=res_val,
                attached_photos=[],  # Populated by photo_associator
                photo_confidence="high",
                source_text=chunk.strip(),
                lab_department=dept_val,
            )
            page_stories.append(story)

        return page_stories

    def _split_text_chunks(self, text: str) -> List[str]:
        """Splits multi-story page text using section headers, double newlines, or dividers."""
        # Check for explicit Markdown or separator dividers
        dividers = [r"\n\s*---\s*\n", r"\n\s*===\s*\n", r"\n\s*_{3,}\s*\n"]
        for div in dividers:
            if re.search(div, text):
                return [c.strip() for c in re.split(div, text) if c.strip()]

        # Split by clear Title/Headline patterns
        # e.g., lines starting with '#', or lines in uppercase, or lines ending with colon
        paragraphs = text.split("\n\n")
        if len(paragraphs) <= 1:
            return [text]

        chunks: List[str] = []
        current_chunk: List[str] = []

        for p in paragraphs:
            p_strip = p.strip()
            if not p_strip:
                continue

            # Check if this paragraph looks like a new story header:
            # Short length (< 90 chars), no terminal period, title-like or all caps
            is_new_story_header = (
                len(p_strip) < 90
                and not p_strip.endswith((".", ",", ";"))
                and (
                    p_strip.isupper()
                    or p_strip.startswith(("#", "Event:", "Title:", "Workshop:", "Victory:", "Achievement:"))
                    or any(p_strip.lower().startswith(prefix) for prefix in [
                        "workshop on", "seminar on", "hands-on", "guest lecture", "hackathon",
                        "congratulations", "first prize", "national conference"
                    ])
                )
            )

            if is_new_story_header and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [p_strip]
            else:
                current_chunk.append(p_strip)

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks if chunks else [text]

    def _extract_headline_and_body(self, lines: List[str]) -> Tuple[Optional[str], str]:
        """Separates the headline from body text."""
        first_line = lines[0]
        # Clean markdown prefix
        cleaned_first = re.sub(r"^#+\s*", "", first_line).strip()

        # If first line is relatively short (< 120 chars) and there are more lines, treat as headline
        if len(lines) > 1 and len(cleaned_first) <= 120 and not cleaned_first.endswith("."):
            headline = cleaned_first
            body = "\n\n".join(lines[1:])
        elif cleaned_first.startswith(("Event:", "Title:", "Topic:")):
            headline = cleaned_first.split(":", 1)[-1].strip()
            body = "\n\n".join(lines[1:]) if len(lines) > 1 else headline
        else:
            # Single paragraph story or long opener
            headline = cleaned_first[:90].strip() if len(cleaned_first) > 90 else cleaned_first
            body = "\n\n".join(lines)

        return headline, body
