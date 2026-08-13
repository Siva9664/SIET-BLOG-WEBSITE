from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class HealthService:
    @staticmethod
    async def get_general_health() -> dict:
        return {"status": "healthy", "service": "SIET Portal API"}

    @staticmethod
    async def get_db_health(db: AsyncSession) -> dict:
        try:
            await db.execute(text("SELECT 1"))
            return {"status": "healthy", "database": "connected"}
        except Exception as e:
            return {"status": "unhealthy", "database": f"failed: {e}"}

    @staticmethod
    async def get_search_health() -> dict:
        # Meilisearch client not configured in this environment
        return {"status": "not_configured", "search": "meilisearch not initialised"}

    @staticmethod
    async def get_storage_health() -> dict:
        # R2 storage client not configured in this environment
        return {"status": "not_configured", "storage": "R2 storage not initialised"}
