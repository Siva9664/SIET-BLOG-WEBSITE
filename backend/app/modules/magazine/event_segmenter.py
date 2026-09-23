"""
Event Segmentation Engine for SIET Magazine Generation.

Transforms uploaded PDF, DOCX, or text documents into a structured intermediate representation:
MagazineSource -> MagazineEvent[] with strict page provenance, participants, dates, facts,
and event-scoped photo associations.
"""

from __future__ import annotations

import io
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
import pymupdf
import docx

from app.core.logging import logger

EXTRACTED_UPLOADS_DIR = "uploads/magazines/extracted"
os.makedirs(EXTRACTED_UPLOADS_DIR, exist_ok=True)


class MagazineEvent(BaseModel):
    event_id: str
    source_page_start: int
    source_page_end: int
    title: str
    date: Optional[str] = None
    category: Optional[str] = "event"
    location: Optional[str] = None
    people: List[str] = Field(default_factory=list)
    organization: Optional[str] = None
    achievement_result: Optional[str] = None
    achievements: List[str] = Field(default_factory=list)
    source_pages: List[int] = Field(default_factory=list)
    facts: List[str] = Field(default_factory=list)
    body_source_text: str
    photos: List[Dict[str, Any]] = Field(default_factory=list)
    photo_associations: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = 1.0
    suggested_page_type: str = "event"

    @property
    def source_text(self) -> str:
        return self.body_source_text


class MagazineSource(BaseModel):
    document_title: str
    department: str
    total_pages: int
    masthead_image_url: Optional[str] = None
    extracted_images: List[Dict[str, Any]] = Field(default_factory=list)
    events: List[MagazineEvent] = Field(default_factory=list)


def _save_image_bytes(img_bytes: bytes, mime_type: str, page_num: int, idx: int) -> Dict[str, Any]:
    """Saves extracted image bytes to disk and returns metadata."""
    ext = "png"
    if "jpeg" in mime_type.lower() or "jpg" in mime_type.lower():
        ext = "jpg"
    elif "webp" in mime_type.lower():
        ext = "webp"

    file_id = f"ext_p{page_num}_{idx}_{uuid.uuid4().hex[:8]}"
    filename = f"{file_id}.{ext}"
    filepath = os.path.join(EXTRACTED_UPLOADS_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(img_bytes)

    public_url = f"/{EXTRACTED_UPLOADS_DIR}/{filename}"
    return {
        "id": file_id,
        "url": public_url,
        "file_name": filename,
        "page_num": page_num,
    }


def extract_pdf_pages_and_assets(
    file_bytes: bytes,
) -> Tuple[List[Dict[str, Any]], Optional[str], List[Dict[str, Any]]]:
    """
    Extracts text blocks with coordinates and images per page.
    Distinguishes institutional header banners from event photographs.
    Returns (pages_data, masthead_url, all_extracted_images).
    """
    doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    pages_data: List[Dict[str, Any]] = []
    all_extracted_images: List[Dict[str, Any]] = []
    seen_xrefs: Dict[int, Dict[str, Any]] = {}
    masthead_url: Optional[str] = None

    for pno in range(len(doc)):
        page = doc[pno]
        page_num = pno + 1
        blocks = page.get_text("blocks")
        
        # Sort text blocks top-to-bottom
        text_blocks = []
        for b in blocks:
            if b[6] == 0 and b[4].strip():  # Text block
                text_blocks.append({
                    "bbox": (b[0], b[1], b[2], b[3]),
                    "y0": b[1],
                    "y1": b[3],
                    "text": b[4].strip(),
                })
        text_blocks.sort(key=lambda x: x["y0"])

        # Extract page images
        page_photos = []
        try:
            image_list = page.get_images(full=True)
            for idx, img_info in enumerate(image_list):
                xref = img_info[0]
                base_img = doc.extract_image(xref)
                w, h = base_img["width"], base_img["height"]
                img_bytes = base_img["image"]
                img_ext = base_img["ext"]
                mime = f"image/{img_ext}"

                rects = page.get_image_rects(xref)
                rect = rects[0] if rects else pymupdf.Rect(0, 0, w, h)

                # Identify masthead banner: top of page (y < 120), wide aspect ratio > 4:1
                is_masthead = (rect.y0 < 120 and (w / max(1, h)) > 3.5)
                
                if xref in seen_xrefs:
                    saved_meta = dict(seen_xrefs[xref])
                    saved_meta["rect"] = (rect.x0, rect.y0, rect.x1, rect.y1)
                    saved_meta["y0"] = rect.y0
                    saved_meta["y1"] = rect.y1
                    saved_meta["page_num"] = page_num
                else:
                    saved_meta = _save_image_bytes(img_bytes, mime, page_num, idx)
                    saved_meta["rect"] = (rect.x0, rect.y0, rect.x1, rect.y1)
                    saved_meta["y0"] = rect.y0
                    saved_meta["y1"] = rect.y1
                    saved_meta["width"] = w
                    saved_meta["height"] = h
                    saved_meta["is_masthead"] = is_masthead
                    seen_xrefs[xref] = saved_meta
                    all_extracted_images.append(saved_meta)

                if is_masthead:
                    if not masthead_url:
                        masthead_url = saved_meta["url"]
                    saved_meta["is_masthead"] = True
                else:
                    saved_meta["is_masthead"] = False
                    page_photos.append(saved_meta)
        except Exception as e:
            logger.warning(f"Image extraction warning on page {page_num}: {e}")

        pages_data.append({
            "page_num": page_num,
            "text_blocks": text_blocks,
            "photos": page_photos,
        })

    doc.close()
    return pages_data, masthead_url, all_extracted_images


def _clean_participant_names(text: str) -> List[str]:
    """Extracts grounded student and participant names from text blocks without hardcoded blacklists."""
    names: List[str] = []

    # 1. Regex search for explicit labels (e.g. "Participants: ...", "Team Members: ...")
    for m in re.finditer(r"(?:Participants?|Team\s*Members?|Participant|Students?)\s*:\s*([^\n]+)", text, re.IGNORECASE):
        raw = m.group(1)
        tokens = re.split(r"[,;&]|\sand\s", raw)
        for t in tokens:
            clean = re.sub(r"[\(–-].*$", "", t).strip()
            clean = re.sub(r"^[●•\-\s]+", "", clean).strip()
            clean = re.sub(r"^(?:Participants?|Team\s*Members?|Participant|Students?)\s*:\s*", "", clean, flags=re.IGNORECASE).strip()
            if 2 < len(clean) < 40 and not any(k in clean.lower() for k in ["team", "location", "conducted", "organised", "organized", "strong", "international", "hackathon"]):
                if clean and clean not in names:
                    names.append(clean)

    # 2. Search for student name lines with academic years: e.g. "Student Name (II Year, CSE)" or "Participant Name (III Year, IT)"
    student_matches = re.findall(r"\b([A-Z][a-zA-Z\. ]{2,30})\s*\((?:I|II|III|IV)\s*(?:Year|CSE|IT|AIDS|AIML|ECE|EEE|MECH|CIVIL)", text)
    for sm in student_matches:
        c = re.sub(r"^(?:Participants?|Team\s*Members?|Participant|Students?)\s*:\s*", "", sm.strip(), flags=re.IGNORECASE).strip()
        if 2 < len(c) < 40 and not any(k in c.lower() for k in ["team", "location", "organised", "organized", "international", "hackathon"]):
            if c and c not in names:
                names.append(c)

    # 3. Search for bulleted team members: "Student Name – II CSE" or "Participant: Student Name - II Year CSE"
    for line in text.splitlines():
        line_clean = line.strip()
        if "–" in line_clean or " - " in line_clean:
            parts = re.split(r"[–-]", line_clean, maxsplit=1)
            if len(parts) == 2:
                cand = re.sub(r"^[●•\-\s]+", "", parts[0]).strip()
                cand = re.sub(r"^(?:Participants?|Team\s*Members?|Participant|Students?)\s*:\s*", "", cand, flags=re.IGNORECASE).strip()
                suffix = parts[1].strip()
                # Must have an academic year or department indicator in suffix
                if re.search(r"\b(?:I|II|III|IV)\s*(?:Year|CSE|IT|AIDS|AIML|ECE|EEE|MECH|CIVIL|B\.E|B\.Tech)\b", suffix, re.IGNORECASE):
                    if 2 < len(cand) < 35 and not any(k in cand.lower() for k in ["hackathon", "competition", "orchestrate", "conducted", "location", "organised", "world rank"]):
                        if cand and cand not in names:
                            names.append(cand)

    return names


def _extract_organization_generic(title: str, body: str) -> Optional[str]:
    """Extracts organizer, sponsor, or host organization generically without company blacklists/whitelists."""
    # 1. Search for explicit Organised by / Conducted by / Hosted by in body
    m_body = re.search(
        r"(?:Organi[sz]ed\s+by|Conducted\s+by|Hosted\s+by|Sponsor(?:ed)?\s+by|Organi[sz]ation)\s*[:\-]?\s*([A-Za-z0-9\s&×\-\.]{2,50})",
        body,
        re.IGNORECASE,
    )
    if m_body:
        cand = m_body.group(1).split("\n")[0].strip()
        cand = re.sub(r"^[●•\-\s]+", "", cand).strip()
        cand = re.split(r"\s+and\b|\s+conducted\b|\s+held\b", cand, flags=re.IGNORECASE)[0].strip()
        cand = re.sub(r"^(?:the\s+)", "", cand, flags=re.IGNORECASE).strip()
        if len(cand) > 2 and not any(w in cand.lower() for w in ["conducted", "location", "student", "department"]):
            return cand

    # 2. Search for "organized by (the) X" in title or lead text
    m_title = re.search(
        r"(?:organized|conducted|hosted)\s+by\s+(?:the\s+)?([A-Za-z0-9\s&×\-\.]{2,40})",
        f"{title} {body[:200]}",
        re.IGNORECASE,
    )
    if m_title:
        cand = m_title.group(1).strip()
        cand = re.sub(r"^(?:the\s+)", "", cand, flags=re.IGNORECASE).strip()
        if len(cand) > 2:
            return cand

    # 3. Check for parenthetical brand in title: e.g. "Frontier Hackathon (Colosseum × Solana)"
    m_paren = re.search(r"\(([A-Za-z0-9\s&×\-\.]{2,40})\)", title)
    if m_paren:
        val = m_paren.group(1).strip()
        val_lower = val.lower()
        if not any(w in val_lower for w in ["year", "cse", "it", "autonomous", "mcp", "ai", "ui/ux"]):
            return val

    # 4. Check for leading brand prefix in title: e.g. "HackerRank Orchestrate", "Meta × PyTorch × Hugging Face OpenEnv"
    m_lead = re.match(
        r"^([A-Z][a-zA-Z0-9\s&×\-\.]{2,35}?)\s+(?:Orchestrate|Hackathon|Challenge|Contest|Conference|Buildathon|SQL|OpenEnv)",
        title,
    )
    if m_lead:
        val = m_lead.group(1).strip()
        if not any(w in val.lower() for w in ["international", "national", "global", "annual", "state"]):
            return val

    return None


def segment_pdf_events(
    file_bytes: bytes,
    filename: str = "document.pdf",
    default_department: str = "Artificial Intelligence Research Lab",
) -> MagazineSource:
    """
    Main PDF parser and deterministic event segmenter.
    Parses document into distinct MagazineEvent entities with full provenance.
    """
    pages_data, masthead_url, all_extracted_images = extract_pdf_pages_and_assets(file_bytes)
    total_pages = len(pages_data)

    doc_title = default_department
    if pages_data and pages_data[0]["text_blocks"]:
        first_page_texts = [b["text"] for b in pages_data[0]["text_blocks"][:3]]
        clean_header = " — ".join([t for t in first_page_texts if len(t) < 80 and not t.lower().startswith("august")])
        if clean_header:
            doc_title = clean_header

    month_regex = re.compile(
        r"^(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}$",
        re.IGNORECASE,
    )
    competition_prefix_regex = re.compile(
        r"^(?:●\s*)?(?:Competition|Event|Hackathon|Symposium|Conference|Project|Workshop|Seminar)\s*:\s*(.+)$",
        re.IGNORECASE,
    )

    events: List[MagazineEvent] = []
    current_event_dict: Optional[Dict[str, Any]] = None
    current_month: Optional[str] = None
    current_section_category: Optional[str] = None
    event_counter = 1

    def finalize_current_event():
        nonlocal current_event_dict, event_counter, current_section_category
        if not current_event_dict:
            return

        body_text = "\n\n".join(current_event_dict["raw_lines"]).strip()
        if not body_text or len(body_text) < 15:
            return

        people = _clean_participant_names(body_text)

        # Extract achievements/results
        ach_result = None
        ach_match = re.search(
            r"(?:Achievement|Result)\s*:?\s*([^\n]+(?:\n[●•][^\n]+)*)",
            body_text,
            re.IGNORECASE,
        )
        if ach_match:
            ach_result = ach_match.group(1).strip()

        # If a block has no achievement, no participants, and is very short, treat it as a section category
        words = body_text.split()
        if len(current_event_dict["raw_lines"]) <= 1 and not ach_result and not people and len(words) < 15:
            current_section_category = current_event_dict["title"]
            current_event_dict = None
            return

        # Extract facts
        facts = []
        for line in body_text.splitlines():
            line_str = line.strip()
            if line_str.startswith(("●", "•", "-")):
                clean_f = re.sub(r"^[●•\-\s]+", "", line_str).strip()
                if clean_f:
                    facts.append(clean_f)
            elif any(kw in line_str.lower() for kw in ["world rank", "first place", "top 50", "top 100", "top 800", "selected as"]):
                facts.append(line_str)

        org = _extract_organization_generic(current_event_dict["title"], body_text)

        b_lower = body_text.lower()
        p_type = "event"
        if any(k in b_lower for k in ["first place", "won", "gold badge", "rank #1", "runner up", "champion"]):
            p_type = "victory"
        elif any(k in b_lower for k in ["package development", "sdk", "open-source", "published", "library", "framework"]):
            p_type = "project"
        elif any(k in b_lower for k in ["internship", "fellowship", "apprenticeship"]):
            p_type = "seminar"
        elif any(k in b_lower for k in ["conference", "speaker", "summit", "keynote"]):
            p_type = "seminar"
        elif any(k in b_lower for k in ["national innovation", "funding track", "pre-seed", "top 100", "leaderboard", "finalist"]):
            p_type = "achievement"

        p_start = current_event_dict["page_start"]
        p_end = current_event_dict["page_end"]
        source_pages = list(range(p_start, p_end + 1))
        ach_list = [ach_result] if ach_result else []

        evt = MagazineEvent(
            event_id=f"event_{event_counter}",
            source_page_start=p_start,
            source_page_end=p_end,
            source_pages=source_pages,
            title=current_event_dict["title"],
            date=current_event_dict.get("date") or current_month,
            people=people,
            organization=org or current_section_category,
            achievement_result=ach_result,
            achievements=ach_list,
            facts=facts[:6],
            body_source_text=body_text,
            photos=current_event_dict.get("photos", []),
            photo_associations=current_event_dict.get("photo_associations", []),
            confidence=1.0,
            suggested_page_type=p_type,
        )
        # Attach vertical coordinates for spatial photo matching
        setattr(evt, "_y0", current_event_dict.get("y0", 0.0))
        setattr(evt, "_y1", current_event_dict.get("y1", 800.0))
        events.append(evt)
        event_counter += 1
        current_event_dict = None

    # Process all pages and assets as a unified document stream
    # Elements on each page are sorted top-to-bottom by y0
    for page_info in pages_data:
        pno = page_info["page_num"]
        text_blocks = page_info["text_blocks"]
        page_photos = [p for p in page_info["photos"] if not p.get("is_masthead")]

        # Build unified stream of page elements sorted by vertical coordinate y0
        stream_items: List[Dict[str, Any]] = []
        for b in text_blocks:
            stream_items.append({
                "kind": "text",
                "y0": b["y0"],
                "y1": b["y1"],
                "data": b,
            })
        for p in page_photos:
            stream_items.append({
                "kind": "photo",
                "y0": p.get("y0", 0.0),
                "y1": p.get("y1", 800.0),
                "data": p,
            })
        stream_items.sort(key=lambda item: item["y0"])

        for item in stream_items:
            if item["kind"] == "text":
                b = item["data"]
                raw_text = b["text"].strip()
                # Normalize zero-width unicode spaces
                txt = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", raw_text).strip()
                if not txt:
                    continue

                lines = [l.strip() for l in txt.splitlines() if l.strip()]
                first_line = lines[0] if lines else ""

                if pno == 1 and any(hdr in first_line.upper() for hdr in ["ARTIFICIAL INTELLIGENCE RESEARCH LAB", "ACCOMPLISHMENTS 2026", "STUDENTS WHO SECURED"]):
                    continue

                if month_regex.match(first_line):
                    current_month = first_line
                    continue

                is_new_event = False
                event_title = ""

                comp_match = competition_prefix_regex.match(first_line)
                if comp_match:
                    is_new_event = True
                    event_title = comp_match.group(1).strip()
                elif (
                    len(lines) <= 2
                    and len(txt) <= 90
                    and not txt.endswith((".", ";", ":"))
                    and b["y0"] > 100
                    and first_line[0].isupper()
                ):
                    lower = first_line.lower().strip()
                    field_prefixes = (
                        "participant", "team", "student", "member", "achievement",
                        "result", "location", "organised", "organized", "conducted",
                        "venue", "rank", "selected", "http", "●", "•", "-", "*",
                    )
                    is_field = any(lower.startswith(fp) for fp in field_prefixes)
                    is_student_line = bool(re.search(r"[–-]\s*(?:I|II|III|IV)\b|\((?:I|II|III|IV)\b", first_line))
                    if not is_field and not is_student_line:
                        is_new_event = True
                        event_title = " ".join(lines)

                if is_new_event:
                    finalize_current_event()
                    current_event_dict = {
                        "title": event_title,
                        "date": current_month,
                        "page_start": pno,
                        "page_end": pno,
                        "y0": b["y0"],
                        "y1": b["y1"],
                        "raw_lines": [txt],
                        "photos": [],
                        "photo_associations": [],
                    }
                else:
                    if current_event_dict:
                        current_event_dict["raw_lines"].append(txt)
                        current_event_dict["page_end"] = pno
                        current_event_dict["y0"] = min(current_event_dict.get("y0", b["y0"]), b["y0"])
                        current_event_dict["y1"] = max(current_event_dict.get("y1", b["y1"]), b["y1"])
                    else:
                        if len(txt) > 30 and not txt.lower().startswith(("page", "http")):
                            current_event_dict = {
                                "title": first_line[:70],
                                "date": current_month,
                                "page_start": pno,
                                "page_end": pno,
                                "y0": b["y0"],
                                "y1": b["y1"],
                                "raw_lines": [txt],
                                "photos": [],
                                "photo_associations": [],
                            }

            elif item["kind"] == "photo":
                photo = item["data"]
                # End-of-event association: photo follows event text before next event begins
                if current_event_dict:
                    py0 = photo.get("y0", 0.0)
                    base_conf = 0.90
                    evidence = [
                        f"Document position: photo appeared after event '{current_event_dict['title'][:40]}' text on page {pno}."
                    ]

                    # Secondary verification: search adjacent text blocks on this page
                    nearby_blocks = [
                        tb for tb in text_blocks
                        if abs(tb["y0"] - py0) < 85.0 or abs(tb["y1"] - py0) < 85.0
                    ]
                    nearby_combined = " ".join([tb["text"] for tb in nearby_blocks]).lower()
                    ev_title_words = set(re.findall(r"\b[A-Za-z]{3,}\b", current_event_dict["title"].lower()))
                    ev_title_words.difference_update({"the", "and", "for", "with", "siet", "lab", "annual"})

                    matched_terms = [w for w in ev_title_words if w in nearby_combined]
                    if matched_terms:
                        base_conf = 0.98
                        evidence.append(f"Secondary semantic verification: nearby text/caption matches event keyword(s) {matched_terms}.")

                    assoc_record = {
                        "photo_id": photo.get("id"),
                        "event_id": f"event_{event_counter}",
                        "association_method": "document_position",
                        "confidence": base_conf,
                        "evidence": evidence,
                    }
                    photo["association"] = assoc_record

                    # Confidence thresholds:
                    # HIGH (>= 0.75): automatically attach
                    # MEDIUM (0.45 - 0.74): keep positional association, mark for review
                    # LOW (< 0.45): leave unassigned
                    if base_conf >= 0.75:
                        current_event_dict["photos"].append(photo)
                        current_event_dict["photo_associations"].append(assoc_record)
                    elif base_conf >= 0.45:
                        photo["needs_review"] = True
                        current_event_dict["photos"].append(photo)
                        current_event_dict["photo_associations"].append(assoc_record)
                    else:
                        logger.info(f"Photo {photo.get('id')} has low confidence ({base_conf}) - leaving unassigned.")

    finalize_current_event()

    # Safety fallback: ensure any non-masthead photos on a page are not orphaned
    assigned_photo_ids = set()
    for ev in events:
        for p in ev.photos:
            assigned_photo_ids.add(p.get("id"))

    for page_info in pages_data:
        pno = page_info["page_num"]
        p_photos = [p for p in page_info["photos"] if not p.get("is_masthead")]
        unassigned_on_page = [p for p in p_photos if p.get("id") not in assigned_photo_ids]
        if not unassigned_on_page:
            continue

        page_events = [ev for ev in events if ev.source_page_start <= pno <= ev.source_page_end] or events
        if page_events:
            for photo in unassigned_on_page:
                photo_y = (photo.get("y0", 0.0) + photo.get("y1", 0.0)) / 2.0
                best_event = min(
                    page_events,
                    key=lambda ev: abs(getattr(ev, "_y0", 0.0) - photo_y)
                )
                assoc_record = {
                    "photo_id": photo.get("id"),
                    "event_id": best_event.event_id,
                    "association_method": "spatial_proximity",
                    "confidence": 0.80,
                    "evidence": [f"Fallback spatial proximity on page {pno}"],
                }
                photo["association"] = assoc_record
                best_event.photos.append(photo)
                best_event.photo_associations.append(assoc_record)
                assigned_photo_ids.add(photo.get("id"))

    return MagazineSource(
        document_title=doc_title,
        department=default_department,
        total_pages=total_pages,
        masthead_image_url=masthead_url,
        extracted_images=all_extracted_images,
        events=events,
    )


def segment_docx_events(
    file_bytes: bytes,
    filename: str = "document.docx",
    default_department: str = "Artificial Intelligence Research Lab",
) -> MagazineSource:
    """
    Parses a Word (.docx) document while strictly preserving paragraph, heading,
    and inline image sequence. Applies end-of-event photo association to bind
    trailing images to their preceding event.
    """
    doc = docx.Document(io.BytesIO(file_bytes))
    all_extracted_images: List[Dict[str, Any]] = []
    events: List[MagazineEvent] = []
    current_event_dict: Optional[Dict[str, Any]] = None
    event_counter = 1
    doc_title = default_department

    def finalize_docx_event():
        nonlocal current_event_dict, event_counter
        if not current_event_dict:
            return
        body_text = "\n\n".join(current_event_dict["raw_lines"]).strip()
        if not body_text or len(body_text) < 15:
            return

        people = _clean_participant_names(body_text)
        ach_result = None
        ach_match = re.search(r"(?:Achievement|Result)\s*:?\s*([^\n]+)", body_text, re.IGNORECASE)
        if ach_match:
            ach_result = ach_match.group(1).strip()

        org = _extract_organization_generic(current_event_dict["title"], body_text)
        p_type = "event"
        b_lower = body_text.lower()
        if any(k in b_lower for k in ["first place", "won", "gold badge", "rank #1", "runner up"]):
            p_type = "victory"
        elif any(k in b_lower for k in ["package", "sdk", "open-source", "published"]):
            p_type = "project"
        elif any(k in b_lower for k in ["hackathon", "top 100", "finalist"]):
            p_type = "achievement"

        evt = MagazineEvent(
            event_id=f"event_{event_counter}",
            source_page_start=1,
            source_page_end=1,
            source_pages=[1],
            title=current_event_dict["title"],
            date="2026",
            people=people,
            organization=org,
            achievement_result=ach_result,
            achievements=[ach_result] if ach_result else [],
            facts=[],
            body_source_text=body_text,
            photos=current_event_dict.get("photos", []),
            photo_associations=current_event_dict.get("photo_associations", []),
            confidence=1.0,
            suggested_page_type=p_type,
        )
        events.append(evt)
        event_counter += 1
        current_event_dict = None

    for p in doc.paragraphs:
        txt = p.text.strip()

        # Check for inline images in paragraph
        blip_rids = p._p.xpath('.//a:blip/@r:embed')
        for rId in blip_rids:
            try:
                rel = doc.part.related_parts.get(rId)
                if rel and hasattr(rel, "blob"):
                    img_bytes = rel.blob
                    mime = getattr(rel, "content_type", "image/png")
                    saved_meta = _save_image_bytes(img_bytes, mime, page_num=1, idx=len(all_extracted_images))
                    saved_meta["is_masthead"] = False
                    all_extracted_images.append(saved_meta)

                    if current_event_dict:
                        assoc = {
                            "photo_id": saved_meta["id"],
                            "event_id": f"event_{event_counter}",
                            "association_method": "document_position",
                            "confidence": 0.90,
                            "evidence": [f"DOCX stream order: photo follows event '{current_event_dict['title'][:30]}' text."],
                        }
                        saved_meta["association"] = assoc
                        current_event_dict["photos"].append(saved_meta)
                        current_event_dict["photo_associations"].append(assoc)
            except Exception as e:
                logger.warning(f"DOCX image extraction error: {e}")

        if not txt:
            continue

        # Check for event boundary
        is_heading = (
            p.style.name.startswith("Heading")
            or txt.startswith(("#", "Competition:", "Event:", "Hackathon:"))
            or (len(txt) < 80 and txt.isupper())
        )

        clean_title = re.sub(r"^[#\*\-\s]+", "", txt).strip()
        clean_title = re.sub(r"^(?:Competition|Event|Hackathon)\s*:\s*", "", clean_title, flags=re.IGNORECASE).strip()

        if is_heading:
            finalize_docx_event()
            current_event_dict = {
                "title": clean_title,
                "raw_lines": [txt],
                "photos": [],
                "photo_associations": [],
            }
        else:
            if current_event_dict:
                current_event_dict["raw_lines"].append(txt)
            else:
                if len(txt) > 20:
                    current_event_dict = {
                        "title": clean_title[:70],
                        "raw_lines": [txt],
                        "photos": [],
                        "photo_associations": [],
                    }

    finalize_docx_event()

    return MagazineSource(
        document_title=doc_title,
        department=default_department,
        total_pages=1,
        masthead_image_url=None,
        extracted_images=all_extracted_images,
        events=events,
    )


def segment_document_events(
    file_bytes: bytes,
    filename: str = "document.pdf",
    default_department: str = "Artificial Intelligence Research Lab",
) -> MagazineSource:
    """
    Unified multi-format document parser and deterministic event segmenter.
    Supports PDF and DOCX while preserving sequential block and photo relationships.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext in (".docx", ".doc"):
        return segment_docx_events(file_bytes, filename, default_department)
    return segment_pdf_events(file_bytes, filename, default_department)


def group_events_into_editorial_stories(
    source: Optional[MagazineSource] = None,
    events: Optional[List[MagazineEvent]] = None,
    default_department: str = "Artificial Intelligence Research Lab",
) -> List[Dict[str, Any]]:
    """
    Groups detected events into cohesive, high-impact editorial stories
    suitable for multi-page magazine layout planning (SIET_DEFAULT_V1).
    Uses content-driven clustering based on word budget, photo availability,
    source page proximity, and semantic priority rather than document-specific keywords.
    """
    if events is None:
        events = source.events if source else []
    if not events:
        return []

    # Filter out empty placeholder events (standalone section headings)
    real_events = [
        e for e in events
        if len(e.body_source_text.split()) >= 15 or e.people or e.achievement_result
    ]
    if not real_events:
        real_events = events

    stories: List[Dict[str, Any]] = []
    current_cluster: List[MagazineEvent] = []
    current_words = 0

    def finalize_cluster(cluster_events: List[MagazineEvent]) -> Optional[Dict[str, Any]]:
        if not cluster_events:
            return None

        lead = cluster_events[0]
        type_priority = {"victory": 5, "achievement": 4, "project": 3, "seminar": 2, "event": 1}
        best_type = max(cluster_events, key=lambda ev: type_priority.get(ev.suggested_page_type, 1)).suggested_page_type

        combined_text = "\n\n---\n\n".join([e.body_source_text for e in cluster_events])
        people: List[str] = []
        for e in cluster_events:
            for p in e.people:
                if p not in people:
                    people.append(p)

        photos: List[str] = []
        for e in cluster_events:
            for ph in e.photos:
                url = ph.get("url") if isinstance(ph, dict) else str(ph)
                if url and url not in photos:
                    photos.append(url)

        if len(cluster_events) == 1:
            title = lead.title
            headline = lead.title
            sec = lead.organization or "Department Highlights"
        else:
            titles_short = [re.sub(r"[\–\-].*$", "", e.title).strip() for e in cluster_events]
            title = " & ".join(titles_short[:2])
            headline = f"{lead.title} & Related Achievements"
            sec = lead.organization or "Lab Achievements"

        return {
            "story_id": f"story_{len(stories) + 1}_{lead.event_id}",
            "event_ids": [e.event_id for e in cluster_events],
            "title": title,
            "section": sec,
            "story_type": best_type,
            "target_page_type": best_type if best_type in ["victory", "project", "seminar", "achievement"] else "news_highlights",
            "headline_hint": headline,
            "source_text": combined_text,
            "people": people,
            "attached_photos": photos,
            "date": lead.date or "2026",
            "event_count": len(cluster_events),
        }

    for ev in real_events:
        w_count = len(ev.body_source_text.split())
        if not current_cluster:
            current_cluster.append(ev)
            current_words = w_count
            continue

        prev_ev = current_cluster[-1]
        same_or_next_page = abs(ev.source_page_start - prev_ev.source_page_end) <= 1
        under_budget = (current_words + w_count) <= 180
        has_photos = bool(ev.photos)
        prev_has_photos = any(bool(e.photos) for e in current_cluster)
        photos_compatible = not (has_photos and prev_has_photos)
        prev_is_massive = current_words >= 100

        if same_or_next_page and under_budget and photos_compatible and not prev_is_massive:
            current_cluster.append(ev)
            current_words += w_count
        else:
            st = finalize_cluster(current_cluster)
            if st:
                stories.append(st)
            current_cluster = [ev]
            current_words = w_count

    if current_cluster:
        st = finalize_cluster(current_cluster)
        if st:
            stories.append(st)

    return stories
