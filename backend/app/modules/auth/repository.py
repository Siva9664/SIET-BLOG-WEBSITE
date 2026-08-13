from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.shared.repository.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, User)

    async def get_by_email(self, email: str) -> User | None:
        """Fetches a user profile by email address (case-insensitive)."""
        stmt = select(User).where(func.lower(User.email) == email.lower())
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def exists(self, email: str) -> bool:
        """Checks if a user exists with the specified email address (case-insensitive)."""
        stmt = select(User).where(func.lower(User.email) == email.lower())
        result = await self.db.execute(stmt)
        return result.scalars().first() is not None
