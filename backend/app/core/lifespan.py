import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select

from app.core.database import async_session_maker
from app.core.logging import logger
from app.core.security import hash_password
from app.core.scheduler import start_scheduler, shutdown_scheduler
from app.modules.auth.models import User


async def ensure_admin_user():
    try:
        async with async_session_maker() as session:
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
                await session.commit()
                logger.info("Created default SUPER_ADMIN user: admin@siet.ac.in / Admin@123")
            else:
                admin_user.name = "Administrator"
                admin_user.password_hash = hash_password("Admin@123")
                admin_user.role = "SUPER_ADMIN"
                admin_user.is_active = True
                admin_user.is_verified = True
                await session.commit()
                logger.info("Ensured active SUPER_ADMIN user: admin@siet.ac.in / Admin@123")
    except Exception as e:
        logger.error(f"Error ensuring admin user: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup...")
    asyncio.create_task(ensure_admin_user())
    try:
        start_scheduler()
    except Exception as e:
        logger.error(f"Failed to start background scheduler: {e}")
    yield
    logger.info("Application shutdown...")
    shutdown_scheduler()
