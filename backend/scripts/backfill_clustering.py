import asyncio
import os
import sys
from datetime import UTC, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import async_session_maker
from app.modules.news.models import News, StoryCoverage
from app.modules.news.pipeline import calculate_story_similarity, generate_cluster_ai_enrichment

async def backfill_story_clustering():
    async with async_session_maker() as session:
        print("Starting backfill for multi-source story clustering...")
        result = await session.execute(
            select(News).order_by(News.published_at.desc())
        )
        all_news = list(result.scalars().all())
        print(f"Loaded {len(all_news)} articles to inspect for clustering.")

        processed_ids = set()
        clustered_count = 0

        for i, news_a in enumerate(all_news):
            if news_a.id in processed_ids:
                continue

            cluster = [news_a]
            processed_ids.add(news_a.id)

            for news_b in all_news[i+1:]:
                if news_b.id in processed_ids:
                    continue
                if news_a.source_name == news_b.source_name:
                    continue

                sim_score = calculate_story_similarity(news_a.title, news_a.content, news_b.title, news_b.content)
                if sim_score >= 0.35:
                    cluster.append(news_b)
                    processed_ids.add(news_b.id)

            # Ensure primary coverage record exists for news_a
            cov_result = await session.execute(
                select(StoryCoverage).where(StoryCoverage.news_id == news_a.id)
            )
            existing_covs = list(cov_result.scalars().all())

            if not existing_covs:
                primary_cov = StoryCoverage(
                    news_id=news_a.id,
                    source_name=news_a.source_name or "Primary Source",
                    source_url=news_a.source_url or "",
                    title=news_a.title,
                    published_at=news_a.published_at,
                    is_primary=True,
                )
                session.add(primary_cov)
                existing_covs.append(primary_cov)

            if len(cluster) > 1:
                clustered_count += 1
                print(f"Cluster found: '{news_a.title[:50]}' reported by {len(cluster)} sources ({', '.join([c.source_name for c in cluster])})")

                # Add secondary coverage entries to primary news_a
                for secondary_item in cluster[1:]:
                    sec_cov = StoryCoverage(
                        news_id=news_a.id,
                        source_name=secondary_item.source_name or "Secondary Source",
                        source_url=secondary_item.source_url or "",
                        title=secondary_item.title,
                        published_at=secondary_item.published_at,
                        is_primary=False,
                    )
                    session.add(sec_cov)
                    existing_covs.append(sec_cov)

                news_a.coverage_count = len(existing_covs)
                news_a.verification_status = "confirmed"

                # Synthesize multi-source AI enrichment
                cluster_dicts = [
                    {"title": item.title, "content": item.content, "source_name": item.source_name}
                    for item in cluster
                ]
                enrichment = generate_cluster_ai_enrichment(cluster_dicts, news_a.department or "ai-ml", news_a.subcategory or "General")
                news_a.content_summary = enrichment["content_summary"]
                news_a.detailed_summary = enrichment["detailed_summary"]
                news_a.key_points = enrichment["key_points"]
                news_a.technical_details = enrichment["technical_details"]
                news_a.why_it_matters = enrichment["why_it_matters"]
                news_a.student_relevance = enrichment["student_relevance"]

            else:
                news_a.coverage_count = len(existing_covs)
                news_a.verification_status = "confirmed" if len(existing_covs) >= 2 else "single_source"

        await session.commit()
        print(f"Backfill complete! Clustered {clustered_count} multi-source stories.")

if __name__ == "__main__":
    asyncio.run(backfill_story_clustering())
