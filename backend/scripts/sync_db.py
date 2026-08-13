import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import async_session_maker, engine, Base
import app.modules.news.models  # Import models to register in metadata
import app.modules.auth.models
import app.modules.articles.models
import app.modules.domains.models
import app.modules.magazine.models
import app.modules.media.models
import app.modules.settings.models
import app.modules.tags.models
import app.modules.analytics.models
import app.modules.engagement.models

async def sync_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session_maker() as session:
        # Ensure users table columns
        await session.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;"))
        await session.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT TRUE;"))
        await session.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP WITH TIME ZONE;"))

        # Ensure news table has all new enriched columns
        news_cols = [
            ("simple_explanation", "TEXT"),
            ("detailed_sections", "JSONB"),
            ("content_depth", "VARCHAR(20) DEFAULT 'summary_only'"),
            ("content_summary", "TEXT"),
            ("detailed_summary", "TEXT"),
            ("key_points", "JSONB"),
            ("technical_details", "TEXT"),
            ("why_it_matters", "TEXT"),
            ("student_relevance", "TEXT"),
            ("department", "VARCHAR(50) DEFAULT 'ai-ml'"),
            ("subcategory", "VARCHAR(100)"),
            ("tags_list", "JSONB"),
            ("coverage_count", "INTEGER DEFAULT 1"),
            ("verification_status", "VARCHAR(30) DEFAULT 'single_source'"),
            ("source_id", "INTEGER REFERENCES sources(id) ON DELETE SET NULL"),
            ("canonical_url", "VARCHAR(500)"),
            ("author", "VARCHAR(150)"),
            ("image_url", "VARCHAR(600)"),
            ("image_caption", "VARCHAR(300)"),
            ("fetched_at", "TIMESTAMP WITH TIME ZONE"),
            ("processed_at", "TIMESTAMP WITH TIME ZONE"),
            ("content_hash", "VARCHAR(64)"),
            ("duplicate_of_id", "INTEGER REFERENCES news(id) ON DELETE SET NULL"),
            ("processing_status", "VARCHAR(20) DEFAULT 'processed'"),
            ("is_archived", "BOOLEAN DEFAULT FALSE"),
            ("archived_at", "TIMESTAMP WITH TIME ZONE"),
        ]
        for col_name, col_type in news_cols:
            try:
                await session.execute(text(f"ALTER TABLE news ADD COLUMN IF NOT EXISTS {col_name} {col_type};"))
            except Exception as e:
                print(f"Note on {col_name}: {e}")

        await session.commit()
        print("Database schema synchronized successfully with all tables and columns!")

if __name__ == "__main__":
    asyncio.run(sync_database())
