from fastapi import APIRouter, Depends

from app.modules.contact.schemas import ContactRequest
from app.modules.contact.service import ContactService
from app.shared.responses.helpers import success
from app.shared.responses.schemas import SuccessResponse

# NOTE: /contact should be assigned a tighter rate limit (e.g. 5 req/min) alongside /auth/forgot-password and /auth/resend-verification when Nginx config is next touched.
router = APIRouter(prefix="/contact", tags=["Contact"])


def get_contact_service() -> ContactService:
    return ContactService()


@router.post("", response_model=SuccessResponse[dict])
async def submit_contact(
    req: ContactRequest,
    service: ContactService = Depends(get_contact_service),
):
    await service.submit_contact(req)
    return success(data={"success": True}, message="Contact inquiry received.")
