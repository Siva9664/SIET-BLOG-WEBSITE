import asyncio
import hashlib
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import httpx
import trafilatura
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.modules.auth.models import User
from app.modules.domains.models import Domain
from app.modules.media.models import Media
from app.modules.news.models import DepartmentEnum, News, Source, StoryCoverage, SyncLog
from app.shared.types.content import ContentStatus
from app.shared.utils.slugs import ensure_unique_slug, generate_slug

DEPARTMENT_FALLBACK_IMAGES = {
    "ai-ml": [
        "https://images.unsplash.com/photo-1677442136019-21780efad99a?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=1200&q=80",
    ],
    "cybersecurity": [
        "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1510511459019-5dda7724fd87?auto=format&fit=crop&w=1200&q=80",
    ],
    "pcb-electronics": [
        "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1555680202-c86f0e12f086?auto=format&fit=crop&w=1200&q=80",
    ],
    "vlsi-semiconductor": [
        "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1597733336794-12d05021d510?auto=format&fit=crop&w=1200&q=80",
    ],
    "robotics": [
        "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1546776310-eef45dd6d63c?auto=format&fit=crop&w=1200&q=80",
    ],
    "ar-vr-xr": [
        "https://images.unsplash.com/photo-1593508512255-86ab42a8e620?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1535223289827-42f1e9919769?auto=format&fit=crop&w=1200&q=80",
    ],
    "iot": [
        "https://images.unsplash.com/photo-1558346490-a72e53ae2d4f?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80",
    ],
}

SEED_SOURCES = [
    # AI / ML
    {"name": "TechCrunch AI", "department": "ai-ml", "feed_type": "rss", "feed_url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"name": "VentureBeat AI", "department": "ai-ml", "feed_type": "rss", "feed_url": "https://venturebeat.com/category/ai/feed/"},
    {"name": "MIT Tech Review", "department": "ai-ml", "feed_type": "rss", "feed_url": "https://www.technologyreview.com/feed/"},
    {"name": "Ars Technica Tech", "department": "ai-ml", "feed_type": "rss", "feed_url": "https://feeds.arstechnica.com/arstechnica/technology-lab"},
    {"name": "arXiv cs.AI", "department": "ai-ml", "feed_type": "rss", "feed_url": "http://export.arxiv.org/rss/cs.AI"},
    {"name": "arXiv cs.LG", "department": "ai-ml", "feed_type": "rss", "feed_url": "http://export.arxiv.org/rss/cs.LG"},
    {"name": "Hugging Face Blog", "department": "ai-ml", "feed_type": "rss", "feed_url": "https://huggingface.co/blog/feed.xml"},
    {"name": "NVIDIA Blog", "department": "ai-ml", "feed_type": "rss", "feed_url": "https://blogs.nvidia.com/feed/"},

    # Cybersecurity
    {"name": "BleepingComputer", "department": "cybersecurity", "feed_type": "rss", "feed_url": "https://www.bleepingcomputer.com/feed/"},
    {"name": "The Hacker News", "department": "cybersecurity", "feed_type": "rss", "feed_url": "https://feeds.feedburner.com/TheHackersNews"},
    {"name": "Krebs on Security", "department": "cybersecurity", "feed_type": "rss", "feed_url": "https://krebsonsecurity.com/feed/"},
    {"name": "Dark Reading", "department": "cybersecurity", "feed_type": "rss", "feed_url": "https://www.darkreading.com/rss.xml"},
    {"name": "SecurityWeek", "department": "cybersecurity", "feed_type": "rss", "feed_url": "https://www.securityweek.com/feed/"},

    # PCB / Electronics
    {"name": "Electronics Weekly", "department": "pcb-electronics", "feed_type": "rss", "feed_url": "https://www.electronicsweekly.com/feed/"},
    {"name": "All About Circuits", "department": "pcb-electronics", "feed_type": "rss", "feed_url": "https://www.allaboutcircuits.com/rss/"},
    {"name": "Hackaday", "department": "pcb-electronics", "feed_type": "rss", "feed_url": "https://hackaday.com/blog/feed/"},
    {"name": "Circuit Cellar", "department": "pcb-electronics", "feed_type": "rss", "feed_url": "https://circuitcellar.com/feed/"},

    # VLSI / Semiconductor
    {"name": "Semiconductor Engineering", "department": "vlsi-semiconductor", "feed_type": "rss", "feed_url": "https://semiengineering.com/feed/"},
    {"name": "EE Times", "department": "vlsi-semiconductor", "feed_type": "rss", "feed_url": "https://www.eetimes.com/feed/"},

    # Robotics
    {"name": "IEEE Spectrum Robotics", "department": "robotics", "feed_type": "rss", "feed_url": "https://spectrum.ieee.org/feeds/topic/robotics.rss"},
    {"name": "The Robot Report", "department": "robotics", "feed_type": "rss", "feed_url": "https://www.therobotreport.com/feed/"},
    {"name": "Robotics Business Review", "department": "robotics", "feed_type": "rss", "feed_url": "https://www.roboticsbusinessreview.com/feed/"},

    # AR / VR / XR
    {"name": "Road to VR", "department": "ar-vr-xr", "feed_type": "rss", "feed_url": "https://www.roadtovr.com/feed/"},
    {"name": "UploadVR", "department": "ar-vr-xr", "feed_type": "rss", "feed_url": "https://www.uploadvr.com/rss/"},

    # IoT
    {"name": "IoT For All", "department": "iot", "feed_type": "rss", "feed_url": "https://www.iotforall.com/feed"},
    {"name": "Hackster.io", "department": "iot", "feed_type": "rss", "feed_url": "https://www.hackster.io/news.rss"},
    {"name": "Arduino Blog", "department": "iot", "feed_type": "rss", "feed_url": "https://blog.arduino.cc/feed/"},
    {"name": "Raspberry Pi Blog", "department": "iot", "feed_type": "rss", "feed_url": "https://www.raspberrypi.com/news/feed/"},
]

SUBCATEGORY_RULES = {
    "ai-ml": {
        "Generative AI": ["generative", "genai", "llm", "chatgpt", "claude", "gemini", "diffusion", "midjourney", "transformer"],
        "LLM": ["llm", "large language model", "gpt-4", "llama", "mistral", "fine-tuning", "prompt"],
        "Computer Vision": ["vision", "object detection", "image generation", "segmentation", "opencv", "camera"],
        "NLP": ["nlp", "language processing", "translation", "token", "sentiment", "text generation"],
        "AI Hardware": ["tpu", "gpu", "h100", "b200", "npu", "accelerator", "silicon", "ai chip"],
        "AI Research": ["arxiv", "paper", "dataset", "benchmark", "state-of-the-art", "sota", "algorithm"],
    },
    "cybersecurity": {
        "Network Security": ["firewall", "vpn", "ddos", "packet", "dns", "router", "traffic"],
        "Vulnerabilities": ["cve", "zero-day", "exploit", "patch", "flaw", "vulnerability", "rce"],
        "Malware": ["trojan", "spyware", "backdoor", "payload", "botnet", "infostealer"],
        "Ransomware": ["ransomware", "extortion", "lockbit", "encryptor", "ransom"],
        "Cloud Security": ["aws", "azure", "iam", "kubernetes", "s3", "misconfiguration"],
        "AI Security": ["jailbreak", "prompt injection", "poisoning", "deepfake", "model inversion"],
    },
    "pcb-electronics": {
        "PCB Design": ["pcb", "gerber", "kicad", "altium", "trace", "via", "layer", "schematic"],
        "Embedded Systems": ["microcontroller", "arm", "cortex", "firmware", "rtos", "stm32", "esp32"],
        "Sensors": ["sensor", "accelerometer", "gyroscope", "adc", "i2c", "spi", "analog"],
        "Power Electronics": ["voltage", "converter", "mosfet", "inverter", "battery", "power supply"],
    },
    "vlsi-semiconductor": {
        "Chip Design": ["asic", "fpga", "verilog", "vhdl", "rtl", "soc", "logic synthesis"],
        "Semiconductor": ["wafer", "foundry", "tsmc", "intel", "samsung", "3nm", "2nm", "photolithography"],
        "Packaging": ["chiplet", "2.5d", "3d packaging", "interposer", "hbm"],
    },
    "robotics": {
        "Humanoid Robots": ["humanoid", "bipedal", "boston dynamics", "figure", "optimus"],
        "Autonomous Robots": ["lidar", "slam", "ros", "ros2", "path planning", "navigation", "autonomous"],
        "Drones": ["uav", "quadcopter", "drone", "flight controller"],
        "Industrial Robots": ["arm", "actuator", "cobot", "manufacturing", "servo"],
    },
    "ar-vr-xr": {
        "Spatial Computing": ["apple vision pro", "spatial", "hand tracking", "pass-through"],
        "XR Hardware": ["headset", "display", "micro-oled", "lens", "optics", "quest"],
        "Augmented Reality": ["ar glasses", "smart glasses", "heads-up display"],
    },
    "iot": {
        "Edge Computing": ["edge ai", "edge node", "gateway", "tinyml"],
        "IoT Security": ["mqtt", "coap", "firmware update", "botnet", "iot device"],
        "Smart Cities": ["smart grid", "telemetry", "lorawan", "cellular iot", "nb-iot"],
    },
}

UNWANTED_KEYWORDS = [
    "promo code", "coupon", "discount", "deal", "shopping", "gift card",
    "hotels.com", "ulta", "uber eats", "ray-ban", "b&h photo", "sale",
    "how to buy", "buy now", "cheapest", "cashback", "fashion promo"
]

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "up", "about", "into", "over", "after", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "should", "can", "could", "may", "might", "must", "this", "that", "these", "those",
    "it", "its", "new", "how", "why", "what", "which", "who", "whom", "more", "first"
}


def clean_html_text(raw_html: str) -> str:
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_raw_rss_image(item_elem: ET.Element, desc_html: str) -> Optional[str]:
    """Tier 1: Extract inline image candidate from RSS XML item tags or description HTML."""
    for tag in ["{http://search.yahoo.com/mrss/}content", "{http://search.yahoo.com/mrss/}thumbnail", "media:content", "media:thumbnail", "enclosure"]:
        elem = item_elem.find(tag)
        if elem is not None and elem.get("url"):
            url = elem.get("url")
            if url.startswith("http") and not any(bad in url.lower() for bad in [".gif", "pixel", "icon"]):
                return url

    if desc_html:
        img_match = re.search(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', desc_html, re.IGNORECASE)
        if img_match:
            img_url = img_match.group(1)
            if not any(bad in img_url.lower() for bad in [".gif", "pixel", "icon", "tracker", "logo"]):
                return img_url

    return None


def extract_meta_image_from_html(html: str, base_url: str) -> Optional[str]:
    """Tier 2: Extract featured og:image or twitter:image meta tags from article HTML page."""
    if not html:
        return None
    patterns = [
        r'<meta[^>]+(?:property|name)=["\'](?:og:image|og:image:url|og:image:secure_url|twitter:image|twitter:image:src)["\'][^>]+content=["\']([^"\'\s]+)["\']',
        r'<meta[^>]+content=["\']([^"\'\s]+)["\'][^>]+(?:property|name)=["\'](?:og:image|og:image:url|og:image:secure_url|twitter:image|twitter:image:src)["\']',
    ]
    for p in patterns:
        m = re.search(p, html, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if candidate and not candidate.startswith("data:"):
                from urllib.parse import urljoin
                full_url = urljoin(base_url, candidate)
                if full_url.startswith("http"):
                    return full_url
    return None


def extract_body_images_from_html(html: str, base_url: str) -> List[str]:
    """Tier 3: Extract substantial <img> elements from article body HTML (filters out tiny icons/ads)."""
    if not html:
        return []
    candidates = []
    from urllib.parse import urljoin
    img_matches = re.findall(r'<img[^>]+>', html, re.IGNORECASE)
    for img_tag in img_matches:
        w_match = re.search(r'width=["\']?(\d+)["\']?', img_tag, re.IGNORECASE)
        h_match = re.search(r'height=["\']?(\d+)["\']?', img_tag, re.IGNORECASE)
        if w_match and int(w_match.group(1)) < 100:
            continue
        if h_match and int(h_match.group(1)) < 100:
            continue

        src_match = re.search(r'src=["\']([^"\'\s]+)["\']', img_tag, re.IGNORECASE) or re.search(r'data-src=["\']([^"\'\s]+)["\']', img_tag, re.IGNORECASE)
        if src_match:
            img_url = src_match.group(1).strip()
            if not img_url or img_url.startswith("data:"):
                continue

            low = img_url.lower()
            unwanted = [".gif", ".svg", "pixel", "icon", "logo", "avatar", "tracker", "gravatar", "badge", "ad-", "button", "feedburner"]
            if any(bad in low for bad in unwanted):
                continue

            full_url = urljoin(base_url, img_url)
            if full_url.startswith("http") and full_url not in candidates:
                candidates.append(full_url)
    return candidates


async def validate_image_url(url: str, client: Optional[httpx.AsyncClient] = None) -> bool:
    """Validates that candidate image URL returns HTTP 200/206 with valid image Content-Type."""
    if not url or not url.startswith("http"):
        return False
    if any(domain in url for domain in ["unsplash.com", "images.unsplash.com"]):
        return True

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"
    }

    own_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=6.0, follow_redirects=True, headers=headers)
        own_client = True

    try:
        try:
            resp = await client.head(url, headers=headers, follow_redirects=True, timeout=5.0)
            if resp.status_code == 200:
                ct = resp.headers.get("content-type", "").lower()
                if ct.startswith("image/") or "octet-stream" in ct or "binary" in ct:
                    return True
        except Exception:
            pass

        resp = await client.get(url, headers={**headers, "Range": "bytes=0-1024"}, follow_redirects=True, timeout=6.0)
        if resp.status_code in (200, 206):
            ct = resp.headers.get("content-type", "").lower()
            if ct.startswith("image/") or "octet-stream" in ct or "binary" in ct:
                return True
            body_head = resp.content[:16]
            if body_head.startswith(b'\xff\xd8\xff') or body_head.startswith(b'\x89PNG') or body_head.startswith(b'GIF8') or body_head.startswith(b'RIFF'):
                return True
    except Exception:
        pass
    finally:
        if own_client:
            await client.aclose()

    return False


async def resolve_best_article_image(
    rss_img_candidate: Optional[str],
    article_url: str,
    article_html: Optional[str],
    department: str,
    index: int,
    client: Optional[httpx.AsyncClient] = None
) -> str:
    """
    4-Tier Article Image Resolution:
    1. RSS item image / enclosure / media tags (validated via HTTP)
    2. Article page og:image / twitter:image meta tags (validated via HTTP)
    3. Article main body substantial <img> tags (validated via HTTP)
    4. Stock fallback image (DEFAULT_IMAGES)
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    own_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=headers)
        own_client = True

    try:
        # Tier 1: RSS Image Tag
        if rss_img_candidate and rss_img_candidate.startswith("http"):
            if await validate_image_url(rss_img_candidate, client):
                return rss_img_candidate

        # Fetch HTML if missing
        if not article_html and article_url and article_url.startswith("http"):
            try:
                resp = await client.get(article_url, timeout=8.0)
                if resp.status_code == 200:
                    article_html = resp.text
            except Exception:
                pass

        if article_html:
            # Tier 2: og:image or twitter:image
            og_img = extract_meta_image_from_html(article_html, article_url)
            if og_img and await validate_image_url(og_img, client):
                return og_img

            # Tier 3: Substantial body image
            body_imgs = extract_body_images_from_html(article_html, article_url)
            for body_img in body_imgs[:3]:
                if await validate_image_url(body_img, client):
                    return body_img

    except Exception as ex:
        print(f"Image resolution note for {article_url}: {ex}")
    finally:
        if own_client:
            await client.aclose()

    # Tier 4: Stock Fallback
    fallback_pool = DEPARTMENT_FALLBACK_IMAGES.get(department, DEPARTMENT_FALLBACK_IMAGES["ai-ml"])
    return fallback_pool[index % len(fallback_pool)]


def extract_image_from_item(item_elem: ET.Element, desc_html: str, department: str, index: int) -> str:
    """Legacy sync fallback wrapper returning raw RSS candidate or stock fallback."""
    candidate = extract_raw_rss_image(item_elem, desc_html)
    if candidate:
        return candidate
    fallback_pool = DEPARTMENT_FALLBACK_IMAGES.get(department, DEPARTMENT_FALLBACK_IMAGES["ai-ml"])
    return fallback_pool[index % len(fallback_pool)]


def compute_content_hash(title: str, url: str, excerpt: str) -> str:
    raw = f"{title.strip().lower()}|{url.strip().lower()}|{excerpt[:100].strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def tokenize_title(title: str) -> Set[str]:
    words = re.findall(r"\b[a-zA-Z0-9\-]+\b", title.lower())
    return {w for w in words if len(w) > 2 and w not in STOP_WORDS}


def calculate_story_similarity(title1: str, desc1: str, title2: str, desc2: str) -> float:
    tokens1 = tokenize_title(title1)
    tokens2 = tokenize_title(title2)
    if not tokens1 or not tokens2:
        return 0.0

    t_jaccard = len(tokens1.intersection(tokens2)) / len(tokens1.union(tokens2)) if tokens1.union(tokens2) else 0.0
    seq_ratio = SequenceMatcher(None, title1.lower(), title2.lower()).ratio()

    # Lead summary / content tokens overlap
    c_tok1 = tokenize_title(f"{title1} {(desc1 or '')[:250]}")
    c_tok2 = tokenize_title(f"{title2} {(desc2 or '')[:250]}")
    c_jaccard = len(c_tok1.intersection(c_tok2)) / len(c_tok1.union(c_tok2)) if (c_tok1 and c_tok2) else 0.0

    score = (t_jaccard * 0.45) + (seq_ratio * 0.35) + (c_jaccard * 0.20)

    # Keyword/Entity match boost for technical terms
    shared_keywords = tokens1.intersection(tokens2)
    if len(shared_keywords) >= 2:
        score += 0.06
    elif len(shared_keywords) == 1:
        kw = list(shared_keywords)[0]
        if len(kw) >= 6:
            score += 0.04

    return min(1.0, score)


def classify_article(title: str, content: str, default_dept: str) -> Tuple[str, str, List[str]]:
    combined = f"{title} {content}".lower()
    dept = default_dept
    subcategory = "General"
    tags = []

    rules = SUBCATEGORY_RULES.get(dept, {})
    best_match_count = 0

    for subcat_name, keywords in rules.items():
        match_count = sum(1 for kw in keywords if kw in combined)
        if match_count > best_match_count:
            best_match_count = match_count
            subcategory = subcat_name

    for subcat_name, keywords in rules.items():
        for kw in keywords:
            if kw in combined and len(kw) > 3:
                tag_name = kw.title()
                if tag_name not in tags and len(tags) < 6:
                    tags.append(tag_name)

    if not tags:
        tags = [dept.upper().replace("-", " "), subcategory]

    return dept, subcategory, tags


# ─── FULL-CONTENT EXTRACTION STAGE ───────────────────────────────────────────

def fetch_full_article_content(url: str) -> Tuple[str, str, Optional[str]]:
    """
    Fetches full article main body text using trafilatura readability parser.
    Returns (full_text, content_depth, raw_html).
    """
    if not url or "arxiv.org/pdf" in url:
        return "", "summary_only", None

    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return "", "summary_only", None

        extracted = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            include_images=False,
            include_links=False,
            no_fallback=False
        )

        if extracted and len(extracted.strip()) >= 150:
            clean_body = re.sub(r"\n{3,}", "\n\n", extracted.strip())
            return clean_body, "full", downloaded
        return "", "summary_only", downloaded
    except Exception as ex:
        print(f"Full-text fetch exception for {url}: {ex}")

    return "", "summary_only", None


# ─── DYNAMIC EXPLANATION ENRICHMENT WITH CUSTOM SUBHEADINGS ───────────────────

def generate_dynamic_ai_explanation(
    cluster_items: List[Dict[str, Any]],
    dept: str,
    subcategory: str
) -> Dict[str, Any]:
    """
    Generates:
    - simple_explanation: 2-4 lines, plain language, no jargon.
    - detailed_sections: Dynamic subheadings matching actual story content structure.
    - key_points, why_it_matters, student_relevance, content_depth.
    """
    primary_title = cluster_items[0]["title"]
    
    # Collect full text or summary text from all cluster items
    full_texts = []
    has_full_content = False

    for item in cluster_items:
        txt = item.get("full_text") or item.get("content") or ""
        if item.get("content_depth") == "full" and len(txt) >= 150:
            has_full_content = True
        full_texts.append(f"[{item['source_name']}] {item['title']}\n{txt}")

    combined_raw_text = "\n\n".join(full_texts)
    content_depth = "full" if has_full_content else "summary_only"

    # Split paragraphs and sentences
    raw_paragraphs = [p.strip() for p in combined_raw_text.split("\n\n") if len(p.strip()) > 30]
    sentences = [s.strip() for s in re.split(r"[.!?]", clean_html_text(combined_raw_text)) if len(s.strip()) > 18]

    # 1. Simple Explanation (2-4 lines plain language)
    if sentences:
        p1 = sentences[0] + "."
        p2 = sentences[1] + "." if len(sentences) > 1 else ""
        simple_explanation = f"{p1} {p2}".strip()
    else:
        simple_explanation = f"{primary_title}. This report covers recent engineering progress in {subcategory}."

    if len(simple_explanation) > 300:
        simple_explanation = simple_explanation[:297] + "..."

    # 2. Dynamic Detailed Sections with Custom Subheadings
    detailed_sections: List[Dict[str, Any]] = []

    if content_depth == "full" and len(raw_paragraphs) >= 3:
        # Divide extracted article body naturally into dynamic subheadings
        chunk_size = max(2, len(raw_paragraphs) // 4)

        # Dynamic Heading candidates based on keyword presence
        lower_full = combined_raw_text.lower()

        section_ideas = []
        if "announce" in lower_full or "launch" in lower_full or "release" in lower_full or "introduce" in lower_full:
            section_ideas.append("Key Announcement & Overview")
        else:
            section_ideas.append("Overview & Core Event")

        if "spec" in lower_full or "archit" in lower_full or "perform" in lower_full or "model" in lower_full or "chip" in lower_full:
            section_ideas.append("Technical Architecture & Specifications")

        if "vuln" in lower_full or "cve" in lower_full or "attack" in lower_full or "exploit" in lower_full or "patch" in lower_full:
            section_ideas.append("Security Vulnerability & Exploitation Analysis")

        if "price" in lower_full or "availab" in lower_full or "cost" in lower_full or "market" in lower_full or "dollar" in lower_full:
            section_ideas.append("Pricing & Availability")

        if "test" in lower_full or "bench" in lower_full or "evaluat" in lower_full or "result" in lower_full:
            section_ideas.append("Experimental Results & Performance Benchmarks")

        section_ideas.append("Industry Context & Implementation Outlook")

        for idx, heading in enumerate(section_ideas):
            start_p = idx * chunk_size
            end_p = start_p + chunk_size if idx < len(section_ideas) - 1 else len(raw_paragraphs)
            slice_paras = raw_paragraphs[start_p:end_p]
            if slice_paras:
                # Clean header prefix tags if present
                clean_paras = [re.sub(r"^\[[^\]]+\]\s*", "", p).strip() for p in slice_paras if p.strip()]
                if clean_paras:
                    detailed_sections.append({
                        "heading": heading,
                        "paragraphs": clean_paras[:3]
                    })
    else:
        # Honest Summary-Only Dynamic Sections (1-2 sections)
        overview_text = " ".join(sentences[:3]) + "." if sentences else primary_title
        detailed_sections = [
            {
                "heading": "Event Overview",
                "paragraphs": [overview_text]
            }
        ]
        if len(sentences) > 3:
            detailed_sections.append({
                "heading": "Context & Technical Summary",
                "paragraphs": [" ".join(sentences[3:6]) + "."]
            })

    # 3. Key Points (3-5 bullet takeaways)
    key_points = []
    seen = set()
    for s in sentences[1:]:
        clean_s = re.sub(r"^\[[^\]]+\]\s*", "", s).strip()
        if clean_s and clean_s.lower() not in seen and len(key_points) < 5:
            seen.add(clean_s.lower())
            key_points.append(f"• {clean_s}")

    if not key_points:
        key_points = [
            f"• Primary update regarding {primary_title}",
            f"• Verified development in {dept.upper().replace('-', ' ')} ({subcategory})",
        ]

    # 4. Why It Matters
    why_it_matters = (
        f"Advances in {dept.upper().replace('-', ' ')} directly impact system engineering workflows. "
        f"Tracking {subcategory.lower()} updates enables engineers to optimize architectural decisions and mitigate operational risks."
    )

    # 5. Student Relevance
    student_relevance = (
        f"For SIET engineering students: Reviewing this case study offers practical grounding in "
        f"{subcategory} concepts, real-world deployment patterns, and industry best practices."
    )

    return {
        "simple_explanation": simple_explanation,
        "detailed_sections": detailed_sections,
        "content_summary": simple_explanation,
        "detailed_summary": "\n\n".join([f"### {sec['heading']}\n" + "\n".join(sec['paragraphs']) for sec in detailed_sections]),
        "key_points": key_points,
        "technical_details": f"Detailed technical breakdown across {len(detailed_sections)} dynamic sections.",
        "why_it_matters": why_it_matters,
        "student_relevance": student_relevance,
        "content_depth": content_depth,
    }


async def fetch_rss_feed(source_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*"
    }
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True, headers=headers) as client:
            resp = await client.get(source_info["feed_url"])
            if resp.status_code != 200:
                return []

            root = ET.fromstring(resp.text)
            channel = root.find("channel")
            if channel is None:
                item_nodes = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
            else:
                item_nodes = channel.findall("item")

            for idx, item in enumerate(item_nodes[:10]):
                title_elem = item.find("title") if item.find("title") is not None else item.find("{http://www.w3.org/2005/Atom}title")
                link_elem = item.find("link") if item.find("link") is not None else item.find("{http://www.w3.org/2005/Atom}link")
                desc_elem = item.find("description") if item.find("description") is not None else (item.find("{http://www.w3.org/2005/Atom}summary") if item.find("{http://www.w3.org/2005/Atom}summary") is not None else item.find("{http://www.w3.org/2005/Atom}content"))
                author_elem = item.find("author") if item.find("author") is not None else item.find("{http://www.w3.org/2005/Atom}author")

                title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
                
                link = ""
                if link_elem is not None:
                    link = link_elem.get("href") or link_elem.text or ""
                link = link.strip()

                desc_raw = desc_elem.text if desc_elem is not None and desc_elem.text else ""
                clean_desc = clean_html_text(desc_raw)

                combined_low = f"{title} {clean_desc}".lower()
                if any(bad in combined_low for bad in UNWANTED_KEYWORDS):
                    continue

                if title and link:
                    author_name = author_elem.text.strip() if author_elem is not None and author_elem.text else source_info["name"]
                    img_url = extract_image_from_item(item, desc_raw, source_info["department"], idx)

                    items.append({
                        "title": title,
                        "content": clean_desc or title,
                        "source_url": link,
                        "source_name": source_info["name"],
                        "author": author_name,
                        "department": source_info["department"],
                        "image_url": img_url,
                        "published_at": datetime.now(UTC),
                    })
    except Exception as e:
        print(f"[{source_info['name']}] RSS Fetch Note: {e}")
    return items


async def seed_sources_in_db(session: AsyncSession) -> List[Dict[str, Any]]:
    existing_result = await session.execute(select(Source))
    existing_sources = {s.feed_url: s for s in existing_result.scalars().all()}

    db_sources = []
    for seed in SEED_SOURCES:
        if seed["feed_url"] in existing_sources:
            src = existing_sources[seed["feed_url"]]
            db_sources.append({
                "id": src.id,
                "name": src.name,
                "department": src.department,
                "feed_url": src.feed_url,
                "is_active": src.is_active,
            })
        else:
            new_source = Source(
                name=seed["name"],
                department=seed["department"],
                feed_type=seed["feed_type"],
                feed_url=seed["feed_url"],
                is_active=True,
                error_count=0,
            )
            session.add(new_source)
            await session.flush()
            db_sources.append({
                "id": new_source.id,
                "name": new_source.name,
                "department": new_source.department,
                "feed_url": new_source.feed_url,
                "is_active": new_source.is_active,
            })
    
    await session.commit()
    return db_sources


async def run_sync_pipeline(is_full_sync: bool = False) -> Dict[str, Any]:
    start_time = time.time()
    discovered_count = 0
    new_count = 0
    duplicate_count = 0
    failed_count = 0

    async with async_session_maker() as session:
        sources = await seed_sources_in_db(session)

        active_sources = [s for s in sources if s["is_active"]]
        feed_results = await asyncio.gather(*[fetch_rss_feed(s) for s in active_sources])
        all_batch_items = []
        for source, fetched_items in zip(active_sources, feed_results):
            if not fetched_items:
                continue

            discovered_count += len(fetched_items)
            for item in fetched_items:
                item["source_id"] = source["id"]
                all_batch_items.append(item)

        # ─── Multi-Source Story Clustering & Full-Text Fetch Stage ───────────
        cutoff_72h = datetime.now(UTC) - timedelta(hours=72)
        recent_db_query = await session.execute(
            select(News).where(News.published_at >= cutoff_72h)
        )
        recent_db_news = list(recent_db_query.scalars().all())

        seen_urls: set[str] = set()
        seen_hashes: set[str] = set()

        for item in all_batch_items:
            if item["source_url"] in seen_urls:
                duplicate_count += 1
                continue
            seen_urls.add(item["source_url"])

            try:
                c_hash = compute_content_hash(item["title"], item["source_url"], item["content"])
                if c_hash in seen_hashes:
                    duplicate_count += 1
                    continue
                seen_hashes.add(c_hash)

                async with session.begin_nested():
                    # Check exact URL duplicate in DB
                    stmt_url = select(News).where(News.source_url == item["source_url"])
                    existing_url_news = (await session.execute(stmt_url)).scalar_one_or_none()
                    if existing_url_news:
                        duplicate_count += 1
                        continue

                    # Check exact Hash duplicate in DB
                    stmt_hash = select(News).where(News.content_hash == c_hash)
                    existing_hash_news = (await session.execute(stmt_hash)).scalar_one_or_none()
                    if existing_hash_news:
                        duplicate_count += 1
                        continue

                    # Perform Full-Article Text & Image Extraction
                    raw_html = None
                    try:
                        full_text, content_depth, raw_html = await asyncio.wait_for(
                            asyncio.to_thread(fetch_full_article_content, item["source_url"]),
                            timeout=4.0
                        )
                    except Exception:
                        full_text, content_depth, raw_html = "", "summary_only", None

                    item["full_text"] = full_text
                    item["content_depth"] = content_depth

                    # Accurate Image Resolution (RSS -> og:image -> body img -> stock fallback)
                    item["image_url"] = await resolve_best_article_image(
                        rss_img_candidate=item.get("image_url"),
                        article_url=item["source_url"],
                        article_html=raw_html,
                        department=item["department"],
                        index=discovered_count
                    )

                    # Fuzzy Match against Recent DB Articles
                    matched_db_news: Optional[News] = None
                    for db_news in recent_db_news:
                        if db_news.source_name == item["source_name"]:
                            continue

                        sim_score = calculate_story_similarity(
                            item["title"], item["content"], db_news.title, db_news.content
                        )
                        if sim_score >= 0.25:
                            matched_db_news = db_news
                            break

                    if matched_db_news:
                        coverage_entry = StoryCoverage(
                            news_id=matched_db_news.id,
                            source_name=item["source_name"],
                            source_url=item["source_url"],
                            title=item["title"],
                            published_at=item["published_at"],
                            is_primary=False,
                        )
                        session.add(coverage_entry)

                        matched_db_news.coverage_count += 1
                        matched_db_news.verification_status = "confirmed"

                        # Re-synthesize enrichment with multi-source full text context
                        cluster_items = [
                            {
                                "title": matched_db_news.title,
                                "content": matched_db_news.content,
                                "source_name": matched_db_news.source_name,
                                "full_text": matched_db_news.content,
                                "content_depth": matched_db_news.content_depth
                            },
                            item
                        ]
                        new_enrichment = generate_dynamic_ai_explanation(
                            cluster_items,
                            matched_db_news.department,
                            matched_db_news.subcategory or "General"
                        )
                        matched_db_news.simple_explanation = new_enrichment["simple_explanation"]
                        matched_db_news.detailed_sections = new_enrichment["detailed_sections"]
                        matched_db_news.content_summary = new_enrichment["content_summary"]
                        matched_db_news.detailed_summary = new_enrichment["detailed_summary"]
                        matched_db_news.key_points = new_enrichment["key_points"]
                        matched_db_news.technical_details = new_enrichment["technical_details"]
                        matched_db_news.why_it_matters = new_enrichment["why_it_matters"]
                        matched_db_news.student_relevance = new_enrichment["student_relevance"]
                        matched_db_news.content_depth = new_enrichment["content_depth"]

                        duplicate_count += 1
                        continue

                    # Create New Story Record
                    dept, subcat, tags = classify_article(item["title"], item["content"], item["department"])
                    enrichment = generate_dynamic_ai_explanation([item], dept, subcat)

                    base_slug = generate_slug(item["title"])
                    slug = await ensure_unique_slug(session, News, base_slug)

                    news_record = News(
                        title=item["title"],
                        slug=slug,
                        content=full_text or item["content"],
                        excerpt=enrichment["simple_explanation"],
                        simple_explanation=enrichment["simple_explanation"],
                        detailed_sections=enrichment["detailed_sections"],
                        content_depth=enrichment["content_depth"],
                        content_summary=enrichment["content_summary"],
                        detailed_summary=enrichment["detailed_summary"],
                        key_points=enrichment["key_points"],
                        technical_details=enrichment["technical_details"],
                        why_it_matters=enrichment["why_it_matters"],
                        student_relevance=enrichment["student_relevance"],
                        department=dept,
                        subcategory=subcat,
                        tags_list=tags,
                        coverage_count=1,
                        verification_status="single_source",
                        source_id=item["source_id"],
                        source_url=item["source_url"],
                        canonical_url=item["source_url"],
                        source_name=item["source_name"],
                        author=item["author"],
                        image_url=item["image_url"],
                        published_at=item["published_at"],
                        fetched_at=datetime.now(UTC),
                        processed_at=datetime.now(UTC),
                        content_hash=c_hash,
                        processing_status="processed",
                        status=ContentStatus.PUBLISHED,
                    )
                    session.add(news_record)
                    await session.flush()

                    primary_cov = StoryCoverage(
                        news_id=news_record.id,
                        source_name=item["source_name"],
                        source_url=item["source_url"],
                        title=item["title"],
                        published_at=item["published_at"],
                        is_primary=True,
                    )
                    session.add(primary_cov)
                    await session.flush()
                    new_count += 1
                    recent_db_news.append(news_record)

                await session.commit()

            except Exception as ex:
                print(f"Item error: {ex}")
                failed_count += 1

        duration = round(time.time() - start_time, 2)
        log_status = "success" if failed_count == 0 else ("partial" if new_count > 0 else "failed")

        sync_log = SyncLog(
            run_at=datetime.now(UTC),
            duration_seconds=duration,
            sources_checked=len(sources),
            articles_discovered=discovered_count,
            articles_new=new_count,
            articles_duplicate=duplicate_count,
            articles_failed=failed_count,
            status=log_status,
            log_details={
                "sync_type": "full" if is_full_sync else "incremental",
                "active_sources": len([s for s in sources if s["is_active"]]),
            }
        )
        session.add(sync_log)
        await session.commit()

async def reprocess_stock_fallback_images(limit: int = 250) -> Dict[str, int]:
    """
    Re-runs improved 4-tier image extraction and HTTP validation against stored articles
    that currently use a stock fallback image (Unsplash URLs).
    Returns before/after breakdown statistics.
    """
    og_upgraded = 0
    body_upgraded = 0
    remained_stock = 0
    total_processed = 0

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    }

    async with async_session_maker() as session:
        stmt = select(News).where(News.image_url.like("%unsplash.com%")).order_by(News.id.desc()).limit(limit)
        articles = (await session.execute(stmt)).scalars().all()
        total_processed = len(articles)

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
            for idx, article in enumerate(articles):
                url = article.source_url
                if not url or not url.startswith("http"):
                    remained_stock += 1
                    continue

                html = None
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        html = resp.text
                except Exception:
                    pass

                new_img = None

                if html:
                    og_candidate = extract_meta_image_from_html(html, url)
                    if og_candidate and await validate_image_url(og_candidate, client):
                        new_img = og_candidate
                        og_upgraded += 1
                    else:
                        body_candidates = extract_body_images_from_html(html, url)
                        for b_img in body_candidates[:3]:
                            if await validate_image_url(b_img, client):
                                new_img = b_img
                                body_upgraded += 1
                                break

                if new_img:
                    article.image_url = new_img
                else:
                    remained_stock += 1

                if (idx + 1) % 20 == 0 or idx == len(articles) - 1:
                    await session.commit()

    return {
        "total_processed": total_processed,
        "upgraded_og_image": og_upgraded,
        "upgraded_body_image": body_upgraded,
        "total_upgraded_to_real": og_upgraded + body_upgraded,
        "remained_stock_fallback": remained_stock,
    }


if __name__ == "__main__":
    res = asyncio.run(run_sync_pipeline(is_full_sync=True))
    print(f"Pipeline Sync Output: {res}")
