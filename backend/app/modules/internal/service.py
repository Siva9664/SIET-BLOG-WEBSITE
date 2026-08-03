import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.rss.client import RSSClient
from app.infrastructure.search.client import MeilisearchClient
from app.modules.analytics.repository import AnalyticsRepository
from app.modules.analytics.service import AnalyticsService
from app.modules.articles.models import Article
from app.modules.domains.models import Domain
from app.modules.magazine.models import Magazine
from app.modules.news.models import News
from app.shared.types.content import ContentStatus
from app.shared.utils.slugs import ensure_unique_slug, generate_slug


class InternalService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.search_client = MeilisearchClient()

    async def reindex_search(self) -> dict:
        """Push every published news/article/magazine row into its Meilisearch index."""
        counts = {"news": 0, "articles": 0, "magazine": 0}

        news_rows = (
            await self.db.execute(select(News).where(News.status == ContentStatus.PUBLISHED))
        ).scalars().all()
        for news_row in news_rows:
            ok = await self.search_client.index_document(
                "news",
                {
                    "id": news_row.id,
                    "slug": news_row.slug,
                    "title": news_row.title,
                    "content": news_row.content,
                    "excerpt": news_row.excerpt,
                },
            )
            if ok:
                counts["news"] += 1

        article_rows = (
            await self.db.execute(select(Article).where(Article.status == ContentStatus.PUBLISHED))
        ).scalars().all()
        for article_row in article_rows:
            ok = await self.search_client.index_document(
                "articles",
                {
                    "id": article_row.id,
                    "slug": article_row.slug,
                    "title": article_row.title,
                    "content": article_row.content,
                    "excerpt": article_row.excerpt,
                },
            )
            if ok:
                counts["articles"] += 1

        magazine_rows = (
            await self.db.execute(select(Magazine).where(Magazine.status == ContentStatus.PUBLISHED))
        ).scalars().all()
        for magazine_row in magazine_rows:
            ok = await self.search_client.index_document(
                "magazine",
                {
                    "id": magazine_row.id,
                    "slug": magazine_row.slug,
                    "title": magazine_row.title,
                    "description": magazine_row.description,
                },
            )
            if ok:
                counts["magazine"] += 1

        total = sum(counts.values())
        return {"status": "success", "message": f"Reindexed {total} documents.", "counts": counts}

    async def trigger_analytics(self) -> dict:
        service = AnalyticsService(AnalyticsRepository(self.db))
        await service.trigger_trending_calculation()
        return {"status": "success", "message": "Trending metrics recalculated."}

    async def fetch_news_external(self) -> dict:
        """Fetch RSS feeds configured in RSS_FEEDS and save new entries as draft news items."""
        rss_client = RSSClient()
        inserted_count = 0

        # Load domain map by slug
        domain_rows = (await self.db.execute(select(Domain))).scalars().all()
        domain_map = {d.slug: d.id for d in domain_rows}

        for feed_config in settings.RSS_FEEDS:
            feed_url = feed_config.get("feed_url")
            domain_slug = feed_config.get("domain_slug")
            source_name = feed_config.get("source_name") or "RSS Feed"

            if not feed_url:
                continue

            domain_id = domain_map.get(domain_slug) if domain_slug else None
            items = await rss_client.fetch_feed(feed_url)

            for item in items:
                link = item.get("link") or item.get("source_url")
                if not link:
                    continue

                # Dedup check by source_url
                existing = (
                    await self.db.execute(select(News).where(News.source_url == link))
                ).scalars().first()
                if existing:
                    continue

                title = item.get("title") or "Untitled News"
                description = item.get("summary") or item.get("description") or ""

                # HTML tag cleaning/truncation for description -> excerpt & content
                clean_description = re.sub(r"<[^>]+>", "", description).strip()
                excerpt = clean_description[:300] if clean_description else None
                content = clean_description if clean_description else title

                slug = generate_slug(title)
                slug = await ensure_unique_slug(self.db, News, slug)

                news_item = News(
                    title=title,
                    slug=slug,
                    content=content,
                    excerpt=excerpt,
                    source_url=link,
                    source_name=source_name,
                    domain_id=domain_id,
                    status=ContentStatus.DRAFT,
                    published_at=None,
                )
                self.db.add(news_item)
                inserted_count += 1

        await self.db.flush()
        return {"queued": True, "inserted": inserted_count}
