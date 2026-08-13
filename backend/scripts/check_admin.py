import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import async_session_maker
from app.modules.auth.models import User
from app.shared.utils.security import get_password_hash

async def check_or_create_admin():
    async with async_session_maker() as session:
        stmt = select(User).where(User.role == "admin")
        admins = (await session.execute(stmt)).scalars().all()
        
        if not admins:
            print("No admin user found. Creating default admin user...")
            admin_user = User(
                email="admin@siet.ac.in",
                name="SIET Admin",
                role="admin",
                password_hash=get_password_hash("admin123"),
                is_active=True
            )
            session.add(admin_user)
            await session.commit()
            print("Admin created: Email = admin@siet.ac.in, Password = admin123")
        else:
            print("Existing Admin Users:")
            for admin in admins:
                print(f"ID: {admin.id}, Email: {admin.email}, Role: {admin.role}")
            
            # Reset default admin password to ensure user can log in
            default_admin = (await session.execute(select(User).where(User.email == "admin@siet.ac.in"))).scalars().first()
            if not default_admin:
                admin_user = User(
                    email="admin@siet.ac.in",
                    name="SIET Admin",
                    role="admin",
                    password_hash=get_password_hash("admin123"),
                    is_active=True
                )
                session.add(admin_user)
                await session.commit()
                print("Default Admin Created: admin@siet.ac.in / admin123")
            else:
                default_admin.password_hash = get_password_hash("admin123")
                await session.commit()
                print("Default Admin Password Reset: admin@siet.ac.in / admin123")

if __name__ == "__main__":
    asyncio.run(check_or_create_admin())
