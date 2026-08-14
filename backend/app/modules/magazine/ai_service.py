"""
AI Content Generation Service for SIET Event Magazine Admin

Handles:
1. One-Click Full Auto-Generation for Event Magazine (Title, Description, Writeup, Captions, TOC)
2. Individual field assistance fallbacks
"""
import os
import re
import json
import httpx
from typing import List, Dict, Any, Optional

from app.core.logging import logger

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or ""


async def _call_llm(prompt: str) -> str:
    """
    Executes prompt using available LLM API (Gemini or OpenAI).
    If no API key is set, returns empty string to trigger intelligent rule-based fallback.
    """
    if GEMINI_API_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text = candidates[0]["content"]["parts"][0]["text"]
                        return text.strip()
        except Exception as e:
            logger.warning(f"Gemini API call failed: {e}. Using fallback engine.")

    if OPENAI_API_KEY:
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            }
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"OpenAI API call failed: {e}. Using fallback engine.")

    return ""


# ─── ONE-CLICK AUTO-GENERATE FULL MAGAZINE CONTENT ───────────────────────────

async def generate_full_magazine_content(
    event_name: str,
    event_date: str,
    raw_notes: str,
    photo_count: int = 0
) -> Dict[str, Any]:
    """
    One-click AI call to generate Title, Description, Writeup, Captions, and TOC Summary.
    """
    prompt = f"""You are creating content for a college engineering magazine issue.

Event name: {event_name}
Event date: {event_date}
Raw notes from admin: {raw_notes}
Number of photos uploaded: {photo_count}

Generate the following and return as JSON:

{{
  "magazine_issue_title": "short catchy title for this issue",
  "description": "3-4 sentence polished event overview, professional but engaging tone",
  "writeup": "400-600 word magazine article with a headline and 2-3 subheadings",
  "captions": ["one short caption per photo, max 12 words each, numbered in order"],
  "toc_summary": "one line, max 15 words, summarizing the issue for a table of contents"
}}

Only return valid JSON, no extra text."""

    llm_output = await _call_llm(prompt)

    if llm_output:
        # Strip potential markdown code fence markers (e.g. ```json ... ```)
        clean_json = re.sub(r"^```(json)?", "", llm_output.strip(), flags=re.IGNORECASE)
        clean_json = re.sub(r"```$", "", clean_json.strip()).strip()
        try:
            parsed = json.loads(clean_json)
            # Format writeup text into basic HTML structure if plain markdown
            writeup_raw = parsed.get("writeup", "")
            headline = f"Highlights from {event_name}"
            lines = [l.strip() for l in writeup_raw.split("\n") if l.strip()]
            if lines:
                if lines[0].startswith("#"):
                    headline = lines[0].replace("#", "").strip()
                elif len(lines[0]) < 80:
                    headline = lines[0]

            formatted_paragraphs = []
            for line in lines:
                if line.startswith("#"):
                    formatted_paragraphs.append(f'<h3 class="text-base font-bold text-ink border-l-2 border-accent pl-3 mt-4">{line.replace("#", "").strip()}</h3>')
                else:
                    formatted_paragraphs.append(f'<p class="text-sm leading-relaxed text-ink-soft mb-3">{line}</p>')

            writeup_html = f'<article class="prose max-w-none space-y-3 font-sans text-ink"><h2 class="text-xl font-bold text-accent border-b border-line pb-2">{headline}</h2>' + "".join(formatted_paragraphs) + '</article>'

            return {
                "magazine_issue_title": parsed.get("magazine_issue_title", f"{event_name} Special Edition"),
                "description": parsed.get("description", f"Highlights and research proceedings from {event_name}."),
                "writeup_headline": headline,
                "writeup_html": writeup_html,
                "writeup_text": writeup_raw,
                "captions": parsed.get("captions", []),
                "toc_summary": parsed.get("toc_summary", f"Coverage of {event_name} held on {event_date}."),
            }
        except Exception as e:
            logger.warning(f"Failed to parse LLM JSON output: {e}. Using rule fallback.")

    # Rule-Based High-Quality Fallback Generator
    clean_notes = raw_notes.strip().replace("\n", ", ")
    date_str = f" held on {event_date}" if event_date else ""
    event_str = event_name if event_name else "Campus Event"

    title_prefix = "" if event_str.lower().startswith("siet") else "SIET "
    title_gen = f"{title_prefix}{event_str}: Special Digest 2026"
    desc_gen = (
        f"Sri Shakthi Institute of Engineering & Technology proudly presented {event_str}{date_str}, "
        f"bringing together aspiring student researchers, faculty experts, and industry mentors. "
        f"Key proceedings included: {clean_notes if clean_notes else 'interactive demonstrations and technical discussions'}. "
        f"This magazine edition documents student research achievements and technological innovations."
    )

    writeup_headline = f"Innovation & Excellence: Key Moments from {event_str}"
    notes_paragraphs = [p.strip() for p in raw_notes.split("\n") if p.strip()]

    writeup_html = f"""<article class="prose max-w-none space-y-4 font-sans text-ink">
  <h2 className="text-xl font-bold text-accent border-b border-line pb-2">{writeup_headline}</h2>
  <p className="text-sm leading-relaxed text-ink font-medium">
    The campus of Sri Shakthi Institute of Engineering & Technology served as a vibrant hub of technological discovery during {event_str}. Bringing together student innovators and domain leaders, the event showcased significant advancements in engineering discipline.
  </p>
  <h3 className="text-base font-bold text-ink border-l-2 border-accent pl-3">Technical Demonstrations & Keynote Addresses</h3>
  <p className="text-sm leading-relaxed text-ink-soft">
    {" ".join(notes_paragraphs[:2]) if notes_paragraphs else "Distinguished speakers and student teams demonstrated cutting-edge prototypes, reflecting the institution's commitment to practical engineering education."}
  </p>
  <h3 className="text-base font-bold text-ink border-l-2 border-accent pl-3">Research Impact & Student Recognition</h3>
  <p className="text-sm leading-relaxed text-ink-soft">
    {" ".join(notes_paragraphs[2:]) if len(notes_paragraphs) > 2 else "Evaluation committees praised the technical rigor and real-world applicability of the presented solutions across all participating streams."}
  </p>
</article>"""

    fallback_captions = []
    defaults = [
        f"Opening keynote session at {event_str}.",
        "Students demonstrating research prototype to evaluation panel.",
        "Interactive Q&A discussion with faculty and guest dignitaries.",
        "Award ceremony honoring top student project teams.",
        "Group photograph of event organizers and participants.",
    ]
    for i in range(max(photo_count, 1)):
        fallback_captions.append(defaults[i % len(defaults)])

    toc_gen = f"Special issue covering {event_str} and student research achievements."

    return {
        "magazine_issue_title": title_gen,
        "description": desc_gen,
        "writeup_headline": writeup_headline,
        "writeup_html": writeup_html,
        "writeup_text": writeup_headline + "\n\n" + raw_notes,
        "captions": fallback_captions,
        "toc_summary": toc_gen,
    }


# ─── INDIVIDUAL ASSISTANCE FUNCTIONS ─────────────────────────────────────────

async def generate_event_overview(raw_notes: str, event_name: str, event_date: str) -> str:
    res = await generate_full_magazine_content(event_name, event_date, raw_notes)
    return res["description"]

async def generate_writeup_article(raw_notes: str, event_name: str = "") -> Dict[str, str]:
    res = await generate_full_magazine_content(event_name, "", raw_notes)
    return {
        "headline": res["writeup_headline"],
        "article_html": res["writeup_html"],
        "article_text": res["writeup_text"],
    }

async def generate_gallery_captions(event_name: str, event_description: str, photos: List[Dict[str, str]]) -> List[Dict[str, str]]:
    res = await generate_full_magazine_content(event_name, "", event_description, photo_count=len(photos))
    caps = res.get("captions", [])
    out = []
    for idx, item in enumerate(photos):
        cap = caps[idx] if idx < len(caps) else f"Photo from {event_name}"
        out.append({"id": item.get("id", str(idx)), "caption": cap})
    return out

async def generate_toc_entry(title: str, description: str) -> str:
    res = await generate_full_magazine_content(title, "", description)
    return res["toc_summary"]
