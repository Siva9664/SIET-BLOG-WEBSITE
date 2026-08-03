from app.core.logging import logger
from app.infrastructure.email.provider import EmailProvider
from app.modules.contact.schemas import ContactRequest


class ContactService:
    def __init__(self, email_provider: EmailProvider | None = None):
        self.email_provider = email_provider or EmailProvider()

    async def submit_contact(self, request: ContactRequest) -> bool:
        try:
            success = await self.email_provider.send_contact_notification(
                name=request.name,
                email=request.email,
                subject=request.subject,
                message=request.message,
            )
            if not success:
                logger.error(f"Failed to send contact notification email for {request.email}")
            return True
        except Exception as e:
            logger.error(f"Error processing contact form submission from {request.email}: {e}")
            return True
