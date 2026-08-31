import io
import re
from typing import List, Tuple

import docx


def extract_template_phrases(template_bytes: bytes, min_len: int = 20) -> List[str]:
    """
    Extracts all distinctive sample/instruction text phrases from a template .docx file.
    Filter out short common words to get distinctive sample phrases.
    """
    doc = docx.Document(io.BytesIO(template_bytes))
    phrases: List[str] = []

    ignore_exact = {
        "cover", "editor's note", "featured story", "events roundup",
        "student spotlight", "club updates", "gallery", "closing ai news", "normal", "heading 1"
    }

    for p in doc.paragraphs:
        t = p.text.strip()
        if len(t) >= min_len and t.lower() not in ignore_exact:
            # Skip pure placeholder tokens like {{EVENT_TITLE}} or [DATE]
            if re.match(r"^[\{\[\<].*[\}\]\>]$", t):
                continue
            phrases.append(t)

    return phrases


def verify_no_template_leakage(output_bytes: bytes, template_bytes: bytes) -> Tuple[bool, List[str]]:
    """
    Automated Regression Test:
    Verifies that zero sample/placeholder text from the template file appears in output_bytes.
    Returns (is_clean: bool, leaked_phrases: list[str]).
    """
    template_phrases = extract_template_phrases(template_bytes)
    leaked_phrases: List[str] = []

    try:
        out_doc = docx.Document(io.BytesIO(output_bytes))
        out_full_text = "\n".join([p.text for p in out_doc.paragraphs if p.text.strip()])

        for phrase in template_phrases:
            # Search for sub-phrases of 4+ words to be resilient to minor whitespace changes
            words = phrase.split()
            if len(words) >= 4:
                sub_phrase = " ".join(words[:5])
                if sub_phrase.lower() in out_full_text.lower():
                    leaked_phrases.append(phrase)
            elif phrase.lower() in out_full_text.lower():
                leaked_phrases.append(phrase)

    except Exception:
        # If output_bytes is not a docx (e.g. PDF text string), check plain text matching
        text_content = output_bytes.decode("utf-8", errors="ignore")
        for phrase in template_phrases:
            words = phrase.split()
            if len(words) >= 4:
                sub_phrase = " ".join(words[:5])
                if sub_phrase.lower() in text_content.lower():
                    leaked_phrases.append(phrase)

    is_clean = len(leaked_phrases) == 0
    return is_clean, leaked_phrases
