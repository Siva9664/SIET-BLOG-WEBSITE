from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.settings.schemas import SettingsResponse, SettingsUpdate
from app.modules.settings.service import SettingsService
from app.shared.auth.dependencies import require_admin
from app.shared.responses.helpers import success
from app.shared.responses.schemas import SuccessResponse

router = APIRouter(prefix="/admin/settings", tags=["Admin Settings"])


def get_settings_service(db: AsyncSession = Depends(get_db)) -> SettingsService:
    return SettingsService(db)


@router.get("", response_model=SuccessResponse[SettingsResponse])
async def get_settings(
    _: dict = Depends(require_admin),
    service: SettingsService = Depends(get_settings_service),
):
    settings = await service.get_settings()
    return success(data=settings)


@router.put("", response_model=SuccessResponse[SettingsResponse])
async def update_settings(
    update_data: SettingsUpdate,
    _: dict = Depends(require_admin),
    service: SettingsService = Depends(get_settings_service),
):
    updated = await service.update_settings(update_data)
    return success(data=updated, message="Settings updated successfully.")
