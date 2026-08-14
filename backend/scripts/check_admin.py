import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import async_session_maker
from app.modules.auth.models import User
from app.core.security import hash_password


async def check_or_create_admin():
    async with async_session_maker() as session:
        stmt = select(User).where(User.role.in_(["admin", "ADMIN", "super_admin", "SUPER_ADMIN"]))
        admins = (await session.execute(stmt)).scalars().all()
        
        print("Existing Admin Users:")
        for admin in admins:
            print(f"ID: {admin.id}, Email: {admin.email}, Role: {admin.role}")
        
        # Ensure default admin account exists
        default_admin = (await session.execute(select(User).where(User.email == "admin@siet.ac.in"))).scalars().first()
        if not default_admin:
            admin_user = User(
                email="admin@siet.ac.in",
                name="SIET Admin",
                role="SUPER_ADMIN",
                password_hash=hash_password("Admin@123"),
                is_active=True,
                is_verified=True,
                email_verified=True,
            )
            session.add(admin_user)
            await session.commit()
            print("Default Admin Created: admin@siet.ac.in / Admin@123")
        else:
            default_admin.password_hash = hash_password("Admin@123")
            await session.commit()
            print("Default Admin Password Ensured: admin@siet.ac.in / Admin@123")

if __name__ == "__main__":
    asyncio.run(check_or_create_admin())

