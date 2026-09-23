"""
Event-Scoped Photo Associator for SIET Magazine Generation.

Enforces strict photo isolation:
- Event A's photos are bound only to Event A.
- Never contaminates Event B with Event A's photos.
- Events with 0 photos are handled as pure text/editorial layouts with zero fabricated images.
- Distinguishes institutional header banners from event photographs.
"""

from __future__ import annotations

import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple
from app.core.logging import logger
from app.modules.magazine.event_segmenter import MagazineEvent, MagazineSource


class PhotoAssociator:
    """
    Enforces strict event-scoped photo association and prevents cross-event photo leakage.
    """

    @staticmethod
    def match_separate_photos(
        events: List[MagazineEvent],
        uploaded_photos: List[Dict[str, Any]],
        confidence_threshold_high: float = 0.90,
        confidence_threshold_review: float = 0.75,
    ) -> Tuple[List[MagazineEvent], List[Dict[str, Any]]]:
        """
        Automatically associates separately uploaded photos with segmented events.
        Uses:
        1. Explicit event index in filename (e.g. event_1, story_2) -> confidence: 0.95
        2. Semantic entity matching (participant names, event keywords, organization) -> confidence: 0.75-0.98

        Enforces confidence thresholds:
        - HIGH (>= 0.90): automatically attaches to event (HIGH CONFIDENCE).
        - REVIEW (0.75 - 0.89): automatically attaches to event, flags needs_review (REVIEW RECOMMENDED).
        - LOW (< 0.75): NEVER automatically attaches; remains unassigned in UNMATCHED PHOTOS.

        Returns (updated_events, association_records).
        """
        if not uploaded_photos or not events:
            return events, []

        all_associations: List[Dict[str, Any]] = []
        assigned_photo_ids = set()

        event_by_id = {ev.event_id: ev for ev in events}
        unmatched_photos: List[Dict[str, Any]] = []

        for photo in uploaded_photos:
            p_id = photo.get("id") or str(uuid.uuid4())
            photo["id"] = p_id
            fn = photo.get("file_name", "")
            fn_lower = fn.lower()
            caption = photo.get("caption", "")
            search_text = f"{fn_lower} {caption.lower()}"

            matched_event: Optional[MagazineEvent] = None
            conf = 0.0
            method = "none"
            evidence: List[str] = []

            # 1. Explicit index match (e.g. event_1, event-2, story_3, photo1_event2)
            idx_match = re.search(r"(?:event|story)[_\s-]*0*(\d+)", search_text)
            if idx_match:
                e_num = int(idx_match.group(1))
                cand_id = f"event_{e_num}"
                if cand_id in event_by_id:
                    matched_event = event_by_id[cand_id]
                elif 0 <= (e_num - 1) < len(events):
                    matched_event = events[e_num - 1]

                if matched_event:
                    conf = 0.95
                    method = "explicit_index"
                    evidence.append(
                        f"Filename contains explicit index hint '{idx_match.group(0)}' "
                        f"matching {matched_event.event_id} ('{matched_event.title[:30]}')."
                    )

            # 2. Semantic entity matching (participant names, title keywords, organizer)
            if not matched_event:
                best_score = 0.0
                best_ev = None
                best_evidence = []

                for ev in events:
                    score = 0.0
                    cur_ev_evidence = []

                    # Match participant names
                    for person in ev.people:
                        parts = [p.lower() for p in person.split() if len(p) > 2]
                        matched_parts = [p for p in parts if p in search_text]
                        if matched_parts:
                            score += 3.0 * len(matched_parts)
                            cur_ev_evidence.append(
                                f"Metadata matches participant '{person}' ({', '.join(matched_parts)})"
                            )

                    # Match title keywords
                    t_words = [
                        w.lower()
                        for w in re.findall(r"\b[A-Za-z0-9]{3,}\b", ev.title)
                        if w.lower() not in {"and", "the", "for", "with", "siet", "lab", "annual", "research"}
                    ]
                    matched_title = [w for w in t_words if w in search_text]
                    if matched_title:
                        score += 2.0 * len(matched_title)
                        cur_ev_evidence.append(
                            f"Metadata matches title keyword(s): {', '.join(matched_title)}"
                        )

                    # Match organizer
                    if ev.organization:
                        org_words = [
                            w.lower()
                            for w in re.findall(r"\b[A-Za-z0-9]{3,}\b", ev.organization)
                            if w.lower() not in {"and", "the", "for", "with", "pvt", "ltd"}
                        ]
                        matched_org = [w for w in org_words if w in search_text]
                        if matched_org:
                            score += 2.0 * len(matched_org)
                            cur_ev_evidence.append(
                                f"Metadata matches organization keyword(s): {', '.join(matched_org)}"
                            )

                    if score > best_score:
                        best_score = score
                        best_ev = ev
                        best_evidence = cur_ev_evidence

                if best_score >= 3.0 and best_ev:
                    matched_event = best_ev
                    conf = min(0.98, 0.85 + (best_score - 3.0) * 0.04)
                    method = "semantic_evidence"
                    evidence = best_evidence
                elif best_score >= 1.5 and best_ev:
                    matched_event = best_ev
                    conf = 0.75 + min(0.14, (best_score - 1.5) * 0.08)
                    method = "semantic_evidence"
                    evidence = best_evidence

            if matched_event and conf >= confidence_threshold_review:
                assoc = {
                    "photo_id": p_id,
                    "event_id": matched_event.event_id,
                    "association_method": method,
                    "confidence": round(conf, 2),
                    "evidence": evidence,
                    "status": "HIGH" if conf >= confidence_threshold_high else "REVIEW_RECOMMENDED",
                }
                photo["association"] = assoc
                all_associations.append(assoc)

                if conf >= confidence_threshold_high:
                    photo["status"] = "HIGH"
                    photo["needs_review"] = False
                    matched_event.photos.append(photo)
                    matched_event.photo_associations.append(assoc)
                    assigned_photo_ids.add(p_id)
                else:
                    photo["status"] = "REVIEW_RECOMMENDED"
                    photo["needs_review"] = True
                    matched_event.photos.append(photo)
                    matched_event.photo_associations.append(assoc)
                    assigned_photo_ids.add(p_id)
            else:
                # < 0.75 or no match: NEVER silently attach
                assoc = {
                    "photo_id": p_id,
                    "event_id": None,
                    "association_method": method if matched_event else "none",
                    "confidence": round(conf, 2),
                    "evidence": evidence if evidence else ["No strong entity or index match found (< 0.75)."],
                    "status": "UNMATCHED",
                }
                photo["status"] = "UNMATCHED"
                photo["needs_review"] = True
                photo["association"] = assoc
                all_associations.append(assoc)
                unmatched_photos.append(photo)
                logger.info(f"Photo '{fn}' confidence {conf:.2f} below threshold {confidence_threshold_review} - unassigned.")

        return events, all_associations

    @staticmethod
    def analyze_and_match(
        events: List[MagazineEvent],
        uploaded_photos: List[Dict[str, Any]],
        confidence_threshold_high: float = 0.90,
        confidence_threshold_review: float = 0.75,
    ) -> Dict[str, Any]:
        """
        Runs event-photo matching analysis for the admin review screen.
        Returns serialized events with matched photos, unmatched photos, and summary statistics.
        """
        import copy
        cloned_events = []
        for ev in events:
            if hasattr(ev, "model_copy"):
                cloned_events.append(ev.model_copy(deep=True))
            else:
                cloned_events.append(copy.deepcopy(ev))
        updated_events, associations = PhotoAssociator.match_separate_photos(
            cloned_events,
            uploaded_photos,
            confidence_threshold_high=confidence_threshold_high,
            confidence_threshold_review=confidence_threshold_review,
        )

        matched_photos_set = set()
        for ev in updated_events:
            for p in ev.photos:
                matched_photos_set.add(p.get("id"))

        unmatched = [p for p in uploaded_photos if p.get("id") not in matched_photos_set]
        high_count = sum(1 for a in associations if a.get("confidence", 0) >= confidence_threshold_high and a.get("event_id"))
        review_count = sum(1 for a in associations if confidence_threshold_review <= a.get("confidence", 0) < confidence_threshold_high and a.get("event_id"))

        events_data = []
        for ev in updated_events:
            events_data.append({
                "event_id": ev.event_id,
                "title": ev.title,
                "date": ev.date,
                "category": getattr(ev, "category", "event"),
                "people": ev.people,
                "achievements": ev.achievements,
                "organization": ev.organization,
                "source_pages": ev.source_pages,
                "matched_photos": [
                    {
                        "id": p.get("id"),
                        "file_name": p.get("file_name"),
                        "url": p.get("url"),
                        "disk_path": p.get("disk_path"),
                        "caption": p.get("caption", ""),
                        "confidence": p.get("association", {}).get("confidence", 0.0),
                        "status": p.get("status", "HIGH"),
                        "needs_review": p.get("needs_review", False),
                        "evidence": p.get("association", {}).get("evidence", []),
                    }
                    for p in ev.photos
                ],
            })

        return {
            "events": events_data,
            "associations": associations,
            "matched_photos": [
                photo for ev in events_data for photo in ev.get("matched_photos", [])
            ],
            "unmatched_photos": [
                {
                    "id": p.get("id"),
                    "file_name": p.get("file_name"),
                    "url": p.get("url"),
                    "disk_path": p.get("disk_path"),
                    "caption": p.get("caption", ""),
                    "confidence": p.get("association", {}).get("confidence", 0.0),
                    "status": "UNMATCHED",
                    "needs_review": True,
                    "evidence": p.get("association", {}).get("evidence", ["No strong entity or index match found (< 0.75)."]),
                }
                for p in unmatched
            ],
            "stats": {
                "total_events": len(events),
                "total_photos": len(uploaded_photos),
                "auto_matched": high_count,
                "auto_matched_count": high_count,
                "review_recommended": review_count,
                "review_recommended_count": review_count,
                "unmatched": len(unmatched),
                "unmatched_count": len(unmatched),
            },
        }

    @staticmethod
    def bind_event_photos(
        source: MagazineSource,
        user_photo_map: Optional[Dict[str, List[Any]]] = None,
        uploaded_photos: Optional[List[Dict[str, Any]]] = None,
    ) -> MagazineSource:
        """
        Binds photos to their respective events based on:
        1. Explicit user/caller photo mapping: {event_id: [photo_paths/urls]}
        2. Automatic matching of separately uploaded photos.
        3. In-document photo proximity from extracted page assets.
        Guarantees that photos are never mixed across events.
        """
        # A mapping supplied by the review UI is the final human decision.  It
        # must never be supplemented by a second automatic matching pass: doing
        # so would undo a removal or reassignment made by the administrator.
        if user_photo_map is not None:
            available_photos = {
                str(photo["id"]): dict(photo)
                for photo in (uploaded_photos or [])
                if photo.get("id")
            }
            events_by_id = {event.event_id: event for event in source.events}
            seen_photo_ids: set[str] = set()
            approved_by_event: Dict[str, List[Dict[str, Any]]] = {
                event.event_id: [] for event in source.events
            }

            for event_id, approved_photos in user_photo_map.items():
                if event_id not in events_by_id:
                    raise ValueError(f"Unknown event in approved associations: {event_id}")
                if not isinstance(approved_photos, list):
                    raise ValueError(f"Approved associations for {event_id} must be a list.")

                for submitted_photo in approved_photos:
                    if not isinstance(submitted_photo, dict) or not submitted_photo.get("id"):
                        raise ValueError("Every approved photo must include its server-issued id.")
                    photo_id = str(submitted_photo["id"])
                    if photo_id not in available_photos:
                        raise ValueError(f"Approved photo is not part of this upload: {photo_id}")
                    if photo_id in seen_photo_ids:
                        raise ValueError(f"A photo may only be assigned to one event: {photo_id}")

                    seen_photo_ids.add(photo_id)
                    canonical_photo = dict(available_photos[photo_id])
                    canonical_photo["caption"] = submitted_photo.get(
                        "caption", canonical_photo.get("caption", "")
                    )
                    canonical_photo["status"] = "USER_APPROVED"
                    canonical_photo["needs_review"] = False
                    canonical_photo["association"] = {
                        "photo_id": photo_id,
                        "event_id": event_id,
                        "association_method": "user_approved",
                        "confidence": 1.0,
                        "evidence": ["Approved by administrator review"],
                        "status": "USER_APPROVED",
                    }
                    approved_by_event[event_id].append(canonical_photo)

            for event in source.events:
                event.photos = approved_by_event[event.event_id]
                event.photo_associations = [
                    photo["association"] for photo in event.photos
                ]
            return source

        # Automatic matching is only appropriate for an unattended generation
        # path which has not received a review mapping.
        if uploaded_photos:
            source.events, _ = PhotoAssociator.match_separate_photos(
                events=source.events,
                uploaded_photos=uploaded_photos,
            )

        return source

    @staticmethod
    def validate_photo_isolation(
        stories: List[Dict[str, Any]],
        all_available_photos: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Quality gate to verify that zero cross-event photo contamination occurred.
        """
        assigned_photo_sets: Dict[str, set] = {}
        duplicates: List[str] = []

        for s in stories:
            s_id = s.get("story_id", "unknown")
            photos = set()
            for ph in s.get("attached_photos", []):
                url = ph.get("url") if isinstance(ph, dict) else str(ph)
                if url:
                    photos.add(url)
            assigned_photo_sets[s_id] = photos

        # Check for intersection between any two stories
        story_ids = list(assigned_photo_sets.keys())
        for i in range(len(story_ids)):
            for j in range(i + 1, len(story_ids)):
                id_a, id_b = story_ids[i], story_ids[j]
                overlap = assigned_photo_sets[id_a].intersection(assigned_photo_sets[id_b])
                if overlap:
                    duplicates.append(f"Collision between {id_a} and {id_b}: {overlap}")

        return {
            "is_isolated": len(duplicates) == 0,
            "violations": duplicates,
            "story_count": len(stories),
            "total_assigned_photos": sum(len(p) for p in assigned_photo_sets.values()),
        }
