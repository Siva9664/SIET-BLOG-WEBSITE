from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.settings.schemas import SettingsResponse, SettingsUpdate
from app.modules.settings.service import SettingsService
from app.shared.auth.dependencies import require_admin

router = APIRouter(prefix="/admin/settings", tags=["Admin Settings"])


def get_settings_service(db: AsyncSession = Depends(get_db)) -> SettingsService:
    return SettingsService(db)


@router.get("", response_model=SettingsResponse)
async def get_settings(
    _: dict = Depends(require_admin),
    service: SettingsService = Depends(get_settings_service),
):
    return await service.get_settings()


@router.put("", response_model=SettingsResponse)
async def update_settings(
    update_data: SettingsUpdate,
    _: dict = Depends(require_admin),
    service: SettingsService = Depends(get_settings_service),
):
    return await service.update_settings(update_data)
