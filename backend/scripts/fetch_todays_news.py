import asyncio
from datetime import UTC, datetime
import os
import sys
import xml.etree.ElementTree as ET

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import select, delete
from app.core.database import async_session_maker
from app.modules.domains.models import Domain
from app.modules.media.models import Media
from app.modules.news.models import News
from app.shared.types.content import ContentStatus, MediaType
from app.shared.utils.slugs import ensure_unique_slug, generate_slug

# High resolution tech cover images
CATEGORY_IMAGES = {
    "ai": [
        "https://images.unsplash.com/photo-1677442136019-21780efad99a?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=900&q=80",
    ],
    "robotics": [
        "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1546776310-eef45dd6d63c?auto=format&fit=crop&w=900&q=80",
    ],
    "medical": [
        "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1530497610245-94d3c16cda28?auto=format&fit=crop&w=900&q=80",
    ],
    "code": [
        "https://images.unsplash.com/photo-1555066931-4365d14bab8c?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?auto=format&fit=crop&w=900&q=80",
    ],
    "general": [
        "https://images.unsplash.com/photo-1519389950473-47ba0277781c?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=900&q=80",
    ],
}

# Unwanted non-tech deal/promo terms
UNWANTED_KEYWORDS = [
    "promo code", "coupon", "discount", "deal", "shopping", "gift card",
    "hotels.com", "ulta", "uber eats", "ray-ban", "b&h photo", "sale",
    "off in august", "how to buy", "buy now", "cheapest", "cashback", "fashion"
]

# Comprehensive Tech, AI & IT RSS Feeds
FEEDS = [
    {
        "source": "TechCrunch AI",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "default_domain": "ai-tech-news",
    },
    {
        "source": "VentureBeat AI",
        "url": "https://venturebeat.com/category/ai/feed/",
        "default_domain": "ai-tech-news",
    },
    {
        "source": "Ars Technica IT & Software",
        "url": "https://feeds.arstechnica.com/arstechnica/technology-lab",
        "default_domain": "programming",
    },
    {
        "source": "ZDNET IT News",
        "url": "https://www.zdnet.com/news/rss.xml",
        "default_domain": "it-news",
    },
    {
        "source": "TechCrunch Enterprise",
        "url": "https://techcrunch.com/category/enterprise/feed/",
        "default_domain": "it-news",
    },
    {
        "source": "MIT Tech Review",
        "url": "https://www.technologyreview.com/feed/",
        "default_domain": "ai-tech-news",
    },
    {
        "source": "IEEE Spectrum",
        "url": "https://spectrum.ieee.org/rss/fulltext",
        "default_domain": "robotics",
    },
    {
        "source": "Hacker News",
        "url": "https://news.ycombinator.com/rss",
        "default_domain": "programming",
    },
]


def is_tech_news(title: str, text: str) -> bool:
    content_lower = f"{title} {text}".lower()
    for word in UNWANTED_KEYWORDS:
        if word in content_lower:
            return False
    return True


def pick_image_url(title: str, domain_slug: str, index: int) -> str:
    title_lower = title.lower()
    if "robot" in title_lower or "drone" in title_lower or "navigation" in title_lower or domain_slug == "robotics":
        pool = CATEGORY_IMAGES["robotics"]
    elif "med" in title_lower or "health" in title_lower or domain_slug == "medical-tech":
        pool = CATEGORY_IMAGES["medical"]
    elif "ai" in title_lower or "llm" in title_lower or "model" in title_lower or domain_slug == "ai-tech-news":
        pool = CATEGORY_IMAGES["ai"]
    elif "code" in title_lower or "software" in title_lower or "cloud" in title_lower or domain_slug == "programming" or domain_slug == "it-news":
        pool = CATEGORY_IMAGES["code"]
    else:
        pool = CATEGORY_IMAGES["general"]
    return pool[index % len(pool)]


async def get_or_create_media(session, image_url: str, title: str) -> Media:
    file_key = f"web_news_{abs(hash(image_url))}.jpg"
    stmt = select(Media).where(Media.file_key == file_key)
    existing = (await session.execute(stmt)).scalars().first()
    if existing:
        return existing

    media = Media(
        filename=f"{generate_slug(title[:30])}.jpg",
        file_key=file_key,
        media_type=MediaType.IMAGE,
        mime_type="image/jpeg",
        size_bytes=102400,
        public_url=image_url,
    )
    session.add(media)
    await session.flush()
    return media


async def fetch_rss_items(feed_info: dict) -> list[dict]:
    items = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
            resp = await client.get(feed_info["url"])
            if resp.status_code != 200:
                return []

            root = ET.fromstring(resp.text)
            channel = root.find("channel")
            if channel is None:
                return []

            for i, item in enumerate(channel.findall("item")[:6]):
                title_elem = item.find("title")
                link_elem = item.find("link")
                desc_elem = item.find("description")

                title = title_elem.text.strip() if title_elem is not None and title_elem.text else None
                link = link_elem.text.strip() if link_elem is not None and link_elem.text else None
                desc = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""

                import re
                clean_desc = re.sub(r"<[^>]+>", "", desc).strip()
                excerpt = clean_desc[:220] + "..." if len(clean_desc) > 220 else clean_desc

                if title and link and is_tech_news(title, clean_desc):
                    img_url = pick_image_url(title, feed_info["default_domain"], i)
                    items.append({
                        "title": title,
                        "content": clean_desc or title,
                        "excerpt": excerpt or title,
                        "source_url": link,
                        "source_name": feed_info["source"],
                        "default_domain_slug": feed_info["default_domain"],
                        "image_url": img_url,
                    })
    except Exception as e:
        print(f"Error fetching feed {feed_info['source']}: {e}")
    return items


async def sync_todays_news():
    print("Fetching full spectrum AI, IT & Technology news...")
    
    all_fetched = []
    for feed in FEEDS:
        items = await fetch_rss_items(feed)
        all_fetched.extend(items)

    async with async_session_maker() as session:
        # Clean up off-topic non-tech entries
        all_news = (await session.execute(select(News))).scalars().all()
        deleted_count = 0
        for n in all_news:
            if not is_tech_news(n.title, n.content or ""):
                await session.delete(n)
                deleted_count += 1
        
        if deleted_count > 0:
            await session.commit()
            print(f"Purged {deleted_count} non-tech promo deal entries.")

        # Ensure domains exist in DB
        required_domains = [
            ("AI Tech News", "ai-tech-news"),
            ("Programming", "programming"),
            ("IT & Infrastructure", "it-news"),
            ("Robotics", "robotics"),
            ("Medical Tech", "medical-tech"),
        ]
        for name, slug in required_domains:
            stmt = select(Domain).where(Domain.slug == slug)
            dom = (await session.execute(stmt)).scalars().first()
            if not dom:
                session.add(Domain(name=name, slug=slug))
        await session.commit()

        domain_result = await session.execute(select(Domain))
        domains = domain_result.scalars().all()
        domain_map = {d.slug: d.id for d in domains}

        inserted_count = 0
        for item in all_fetched:
            stmt = select(News).where(News.source_url == item["source_url"])
            existing = (await session.execute(stmt)).scalars().first()
            
            media = await get_or_create_media(session, item["image_url"], item["title"])

            if existing:
                if existing.featured_image_id is None:
                    existing.featured_image_id = media.id
                continue

            domain_id = domain_map.get(item["default_domain_slug"]) or list(domain_map.values())[0]
            slug = generate_slug(item["title"])
            slug = await ensure_unique_slug(session, News, slug)

            news_record = News(
                title=item["title"],
                slug=slug,
                content=item["content"],
                excerpt=item["excerpt"],
                source_url=item["source_url"],
                source_name=item["source_name"],
                domain_id=domain_id,
                featured_image_id=media.id,
                status=ContentStatus.PUBLISHED,
                published_at=datetime.now(UTC),
            )
            session.add(news_record)
            inserted_count += 1

        # Update remaining news items missing image
        all_news_stmt = select(News).where(News.featured_image_id == None)
        unassigned_news = (await session.execute(all_news_stmt)).scalars().all()
        for idx, news_item in enumerate(unassigned_news):
            img_url = pick_image_url(news_item.title, "general", idx)
            media = await get_or_create_media(session, img_url, news_item.title)
            news_item.featured_image_id = media.id

        await session.commit()
        print(f"Successfully processed {inserted_count} new AI, IT & Tech news items into PostgreSQL database!")


if __name__ == "__main__":
    asyncio.run(sync_todays_news())
