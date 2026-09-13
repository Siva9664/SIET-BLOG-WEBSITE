from typing import List, Optional
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.models import User, UserRole
from app.modules.auth.repository import UserRepository
from app.modules.labs.models import LabMembership
from app.shared.exceptions.custom import ForbiddenException, UnauthorizedException


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    user_id = request.state.user
    if not user_id:
        raise UnauthorizedException("Not authenticated.")

    repo = UserRepository(db)
    user = await repo.get_by_id(int(user_id))
    if not user or not user.is_active:
        raise UnauthorizedException("User account invalid or inactive.")
    return user


async def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    """SUPER_ADMIN only: unrestricted global administration."""
    role_val = str(current_user.role).upper()
    if role_val != UserRole.SUPER_ADMIN.value:
        raise ForbiddenException("Super Administrator permissions required.")
    return current_user


async def require_lab_admin(current_user: User = Depends(get_current_user)) -> User:
    """SUPER_ADMIN, LAB_ADMIN, or legacy ADMIN.
    
    ADMIN is treated as a deprecated legacy alias for LAB_ADMIN for backward compatibility.
    EDITOR and AUTHOR are strictly forbidden.
    """
    role_val = str(current_user.role).upper()
    if role_val not in (UserRole.SUPER_ADMIN.value, UserRole.LAB_ADMIN.value, UserRole.ADMIN.value):
        raise ForbiddenException("Lab Administrator permissions required.")
    return current_user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Backward compatibility alias for require_lab_admin."""
    return await require_lab_admin(current_user)


async def require_verified_email(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_verified:
        raise ForbiddenException("Email verification required.")
    return current_user


async def get_user_permitted_lab_ids(current_user: User, db: AsyncSession) -> List[int]:
    """Returns the list of active lab IDs that current_user has access to.
    
    If SUPER_ADMIN, returns all active lab IDs or special indicator. Note: For SUPER_ADMIN,
    callers should verify using verify_user_lab_access or check_object_lab_access directly.
    """
    if current_user.is_super_admin:
        from app.modules.labs.models import Lab
        stmt = select(Lab.id).where(Lab.is_active.is_(True))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    # For LAB_ADMIN and legacy ADMIN, fetch active memberships in active labs
    stmt = (
        select(LabMembership.lab_id)
        .where(
            LabMembership.user_id == current_user.id,
            LabMembership.is_active.is_(True)
        )
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def verify_user_lab_access(current_user: User, lab_id: int, db: AsyncSession) -> bool:
    """Verifies whether current_user is authorized for the given lab_id.
    
    Rules:
    - SUPER_ADMIN: unrestricted access to all labs.
    - LAB_ADMIN / ADMIN: access ONLY if active membership exists in the lab.
    - Others: False.
    Raises ForbiddenException if unauthorized.
    """
    if current_user.is_super_admin:
        return True

    if not current_user.is_lab_admin:
        raise ForbiddenException("Lab Administrator permissions required.")

    permitted_ids = await get_user_permitted_lab_ids(current_user, db)
    if lab_id not in permitted_ids:
        raise ForbiddenException(f"Access denied: you do not have permission for lab ID {lab_id}.")
    return True


async def check_object_lab_access(
    current_user: User,
    object_lab_id: Optional[int],
    db: AsyncSession,
    allow_global: bool = False
) -> bool:
    """Checks object-level lab authorization.
    
    Rules:
    - SUPER_ADMIN: unrestricted access to any object (lab-scoped or global).
    - If object_lab_id is NULL/global:
        - Only SUPER_ADMIN allowed unless allow_global=True (e.g. explicitly shared global templates).
    - If object_lab_id is set:
        - LAB_ADMIN / ADMIN: allowed ONLY if object_lab_id is in user's permitted labs.
    
    Raises ForbiddenException on denial.
    """
    if current_user.is_super_admin:
        return True

    if object_lab_id is None:
        if allow_global:
            return True
        raise ForbiddenException("Access denied: only Super Administrators may access global/unassigned resources.")

    if not current_user.is_lab_admin:
        raise ForbiddenException("Lab Administrator permissions required.")

    permitted_ids = await get_user_permitted_lab_ids(current_user, db)
    if object_lab_id not in permitted_ids:
        raise ForbiddenException("Access denied: resource belongs to another lab.")

    return True
