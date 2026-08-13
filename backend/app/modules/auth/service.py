from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.modules.auth.models import User
from app.modules.auth.repository import UserRepository
from app.modules.auth.schemas import LoginRequest
from app.shared.exceptions.custom import UnauthorizedException


class AuthService:
    def __init__(self, db: AsyncSession):
        self.repo = UserRepository(db)

    async def login(self, data: LoginRequest) -> tuple[str, str, User]:
        clean_email = str(data.email).strip().lower()
        logger.info(f"[AUTH LOGIN] Attempt for email: '{clean_email}'")

        user = await self.repo.get_by_email(clean_email)
        if not user:
            logger.warning(f"[AUTH LOGIN FAILED] Email '{clean_email}' not found.")
            raise UnauthorizedException("Invalid email or password.")

        if not user.is_active:
            logger.warning(f"[AUTH LOGIN FAILED] Account '{clean_email}' is disabled.")
            raise UnauthorizedException("Account is disabled.")

        pw_valid = verify_password(data.password, user.password_hash)
        if not pw_valid:
            logger.warning(f"[AUTH LOGIN FAILED] Password mismatch for '{clean_email}'.")
            raise UnauthorizedException("Invalid email or password.")

        user.last_login = datetime.now(UTC)
        await self.repo.update(user)

        access_token = create_access_token(str(user.id), user.role)
        refresh_token = create_refresh_token(str(user.id), user.role)

        logger.info(f"[AUTH LOGIN SUCCESS] User ID {user.id} ({user.role}) logged in.")
        return access_token, refresh_token, user

    async def refresh(self, refresh_token: str) -> str:
        payload = decode_token(refresh_token)
        if not payload or payload.type != "refresh":
            raise UnauthorizedException("Invalid or expired refresh token.")

        user = await self.repo.get_by_id(int(payload.sub))
        if not user or not user.is_active:
            raise UnauthorizedException("User account invalid or inactive.")

        return create_access_token(str(user.id), user.role)
