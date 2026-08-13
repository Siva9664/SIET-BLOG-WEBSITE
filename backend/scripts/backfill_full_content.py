import asyncio
import os
import sys
import time
from datetime import UTC, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import async_session_maker
from app.modules.news.models import News, StoryCoverage
from app.modules.news.pipeline import fetch_full_article_content, generate_dynamic_ai_explanation

async def backfill_full_content_enrichment():
    print("Starting backfill for full-content extraction & dynamic explanation sections...")
    start_time = time.time()

    async with async_session_maker() as session:
        result = await session.execute(
            select(News).order_by(News.id.desc())
        )
        all_news = list(result.scalars().all())
        total_count = len(all_news)
        print(f"Loaded {total_count} articles to process for full-content extraction.")

        full_count = 0
        summary_count = 0

        for idx, news in enumerate(all_news, start=1):
            url = news.source_url or news.canonical_url or ""

            # Fetch story coverage entries to build cluster context
            cov_result = await session.execute(
                select(StoryCoverage).where(StoryCoverage.news_id == news.id)
            )
            cov_records = list(cov_result.scalars().all())

            # Attempt full content fetch on primary URL
            full_text, content_depth = fetch_full_article_content(url)

            cluster_items = [
                {
                    "title": news.title,
                    "content": news.content or news.excerpt or "",
                    "source_name": news.source_name or "Primary Source",
                    "full_text": full_text if content_depth == "full" else (news.content or news.excerpt or ""),
                    "content_depth": content_depth,
                }
            ]

            # Append secondary coverage text if available
            for cov in cov_records:
                if not cov.is_primary and cov.source_url:
                    sec_text, sec_depth = fetch_full_article_content(cov.source_url)
                    cluster_items.append({
                        "title": cov.title,
                        "content": cov.title,
                        "source_name": cov.source_name,
                        "full_text": sec_text if sec_depth == "full" else cov.title,
                        "content_depth": sec_depth,
                    })

            # Generate dynamic simple & detailed explanation sections
            enrichment = generate_dynamic_ai_explanation(
                cluster_items,
                news.department or "ai-ml",
                news.subcategory or "General"
            )

            news.simple_explanation = enrichment["simple_explanation"]
            news.detailed_sections = enrichment["detailed_sections"]
            news.content_depth = enrichment["content_depth"]
            news.content_summary = enrichment["content_summary"]
            news.detailed_summary = enrichment["detailed_summary"]
            news.key_points = enrichment["key_points"]
            news.technical_details = enrichment["technical_details"]
            news.why_it_matters = enrichment["why_it_matters"]
            news.student_relevance = enrichment["student_relevance"]
            if full_text:
                news.content = full_text

            if enrichment["content_depth"] == "full":
                full_count += 1
            else:
                summary_count += 1

            if idx % 10 == 0 or idx == total_count:
                await session.commit()
                print(f"[{idx}/{total_count}] Processed article '{news.title[:45]}...' -> content_depth: {news.content_depth} (Subheadings: {len(news.detailed_sections or [])})")

        await session.commit()
        duration = round(time.time() - start_time, 2)
        print("\n=======================================================")
        print(f"Backfill Complete in {duration}s!")
        print(f"Total Processed: {total_count}")
        print(f"  - Full Content ('full'): {full_count}")
        print(f"  - Summary Only ('summary_only'): {summary_count}")
        print("=======================================================\n")

if __name__ == "__main__":
    asyncio.run(backfill_full_content_enrichment())
