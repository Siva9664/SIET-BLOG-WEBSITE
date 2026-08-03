from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.settings.models import SiteSettings
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.schemas import SettingsUpdate


class SettingsService:
    def __init__(self, db: AsyncSession):
        self.repo = SettingsRepository(db)

    async def get_settings(self) -> SiteSettings:
        return await self.repo.get_settings()

    async def update_settings(self, update_data: SettingsUpdate) -> SiteSettings:
        data_dict = update_data.model_dump(exclude_unset=True)
        return await self.repo.update_settings(data_dict)
