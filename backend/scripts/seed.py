import asyncio
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import async_session_maker
from app.core.security import hash_password
import app.modules.labs.models  # noqa: F401
import app.modules.magazine.models  # noqa: F401
from app.modules.auth.models import User
from app.shared.constants import Roles

async def seed_data():
    print("Seeding database...")
    async with async_session_maker() as session:
        admin_email = "admin@siet.in"
        stmt = select(User).where(User.email == admin_email)
        result = await session.execute(stmt)
        admin = result.scalars().first()

        if not admin:
            admin_password = os.getenv("ADMIN_INITIAL_PASSWORD", "ChangeMeDevOnly123!")
            admin_user = User(
                name="System Administrator",
                email=admin_email,
                password_hash=hash_password(admin_password),
                role=Roles.ADMIN,
                email_verified=True
            )
            session.add(admin_user)
            await session.commit()
            print("Default admin user seeded successfully (admin@siet.in).")
        else:
            print("Admin user already exists. Skipping.")

if __name__ == "__main__":
    asyncio.run(seed_data())
