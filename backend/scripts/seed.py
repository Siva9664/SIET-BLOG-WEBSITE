import asyncio
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import async_session_maker
from app.core.security import hash_password
from app.modules.labs.models import Lab
from app.modules.magazine.models import MagazineTemplate
from app.modules.auth.models import User
import app.modules.domains.models
import app.modules.media.models
import app.modules.articles.models
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
            await session.flush()
            print("Default admin user seeded successfully (admin@siet.in).")
        else:
            print("Admin user already exists. Skipping.")

        # Seed Default Magazine Template
        stmt_tmpl = select(MagazineTemplate).where(MagazineTemplate.name == 'SIET Default V1 Template')
        result_tmpl = await session.execute(stmt_tmpl)
        if not result_tmpl.scalars().first():
            from app.modules.magazine.models import MagazineType
            default_template = MagazineTemplate(
                name='SIET Default V1 Template',
                template_family='academic_digest',
                is_active=True,
                is_global=True,
                section_schema=[],
                style_rules={"colors": {"primary": "#0f172a", "accent": "#3b82f6"}, "fonts": {"heading": "Inter", "body": "Merriweather"}},
                created_by_id=admin.id if admin else admin_user.id
            )
            session.add(default_template)
            await session.commit()
            print("Default magazine template seeded successfully.")
        else:
            await session.commit()
            print("Default magazine template already exists. Skipping.")

if __name__ == "__main__":
    asyncio.run(seed_data())
