import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select, text

from app.core.database import async_session_maker, engine, Base
from app.core.logging import logger
from app.core.security import hash_password
from app.core.scheduler import start_scheduler, shutdown_scheduler

# Import all models to register in metadata
import app.modules.news.models
import app.modules.auth.models
from app.modules.auth.models import User
import app.modules.articles.models
import app.modules.domains.models
from app.modules.domains.models import Domain
import app.modules.magazine.models
import app.modules.media.models
import app.modules.settings.models
import app.modules.tags.models
import app.modules.analytics.models
import app.modules.engagement.models


async def auto_bootstrap_database():
    """Automatically create tables, sync schema columns, seed default domains & admin user from environment settings."""
    try:
        # 1. Create tables automatically if they don't exist
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Automatic DB Schema initialization complete.")

        # 2. Sync columns if missing
        async with async_session_maker() as session:
            await session.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;"))
            await session.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT TRUE;"))
            await session.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP WITH TIME ZONE;"))

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
                except Exception:
                    pass

            # Sync new Magazine event-based columns
            magazine_cols = [
                ("event_name", "VARCHAR(255)"),
                ("event_date", "TIMESTAMP WITH TIME ZONE"),
                ("is_featured", "BOOLEAN DEFAULT TRUE"),
                ("featured_until", "TIMESTAMP WITH TIME ZONE"),
                ("cover_pages", "JSONB DEFAULT '[]'::jsonb"),
                ("body_pages", "JSONB DEFAULT '[]'::jsonb"),
                ("gallery_images", "JSONB DEFAULT '[]'::jsonb"),
            ]
            for col_name, col_type in magazine_cols:
                try:
                    await session.execute(text(f"ALTER TABLE magazines ADD COLUMN IF NOT EXISTS {col_name} {col_type};"))
                except Exception:
                    pass

            # 3. Seed required domain categories if missing
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

            # 4. Ensure active SUPER_ADMIN user
            stmt = select(User).where(User.email == "admin@siet.ac.in")
            admin_user = (await session.execute(stmt)).scalars().first()
            if not admin_user:
                admin_user = User(
                    email="admin@siet.ac.in",
                    name="Administrator",
                    role="SUPER_ADMIN",
                    password_hash=hash_password("Admin@123"),
                    is_active=True,
                    is_verified=True,
                )
                session.add(admin_user)
                logger.info("Created default SUPER_ADMIN user: admin@siet.ac.in / Admin@123")
            else:
                admin_user.name = "Administrator"
                admin_user.password_hash = hash_password("Admin@123")
                admin_user.role = "SUPER_ADMIN"
                admin_user.is_active = True
                admin_user.is_verified = True
                logger.info("Ensured active SUPER_ADMIN user: admin@siet.ac.in / Admin@123")

            await session.commit()
    except Exception as e:
        logger.error(f"Error during automatic database bootstrap: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup...")
    await auto_bootstrap_database()
    try:
        start_scheduler()
    except Exception as e:
        logger.error(f"Failed to start background scheduler: {e}")
    yield
    logger.info("Application shutdown...")
    shutdown_scheduler()
