import asyncio
from app.core.database import async_session_maker
from app.modules.auth.service import AuthService
from app.modules.auth.schemas import LoginRequest

async def test_login():
    async with async_session_maker() as session:
        service = AuthService(session)
        try:
            access_token, refresh_token, user = await service.login(LoginRequest(email="admin@siet.ac.in", password="Admin@123"))
            print("Login successful!")
            print("Access token:", access_token)
            print("Refresh token:", refresh_token)
            print("User:", user.id, user.email, user.role)
        except Exception as e:
            print("Login failed:", e)

if __name__ == "__main__":
    asyncio.run(test_login())
