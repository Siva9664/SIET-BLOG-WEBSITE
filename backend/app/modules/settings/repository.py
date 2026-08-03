from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.settings.models import SiteSettings


class SettingsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_settings(self) -> SiteSettings:
        stmt = select(SiteSettings).where(SiteSettings.id == 1)
        result = await self.db.execute(stmt)
        settings = result.scalars().first()
        if not settings:
            settings = SiteSettings(
                id=1,
                site_name="SIET News",
                credit_line="AI Research Lab · Sri Shakthi Institute of Engineering and Technology",
                accent_color="#0F2B5C",
                newsletter_enabled=True,
                featured_domains="machine-learning, robotics",
            )
            self.db.add(settings)
            await self.db.flush()
        return settings

    async def update_settings(self, update_data: dict) -> SiteSettings:
        settings = await self.get_settings()
        for key, value in update_data.items():
            if value is not None and hasattr(settings, key):
                setattr(settings, key, value)
        await self.db.flush()
        return settings
