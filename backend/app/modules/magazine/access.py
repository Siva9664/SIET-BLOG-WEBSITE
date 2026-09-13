from typing import List, Optional
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.labs.models import TemplateLabAssignment
from app.modules.magazine.models import Magazine, MagazineTemplate, TemplateVersion
from app.shared.auth.dependencies import get_user_permitted_lab_ids
from app.shared.exceptions.custom import ForbiddenException, NotFoundException


async def check_magazine_access(
    current_user: User,
    magazine: Magazine,
    db: AsyncSession,
    require_write: bool = False,
) -> bool:
    """Strictly verifies whether current_user is authorized to view or edit the given magazine.
    
    Rules:
    - SUPER_ADMIN: unrestricted access to all magazines (read & write).
    - If magazine.lab_id is NULL:
        - Only SUPER_ADMIN can access/edit.
        - Lab Admins cannot access unassigned/legacy magazines unless granted.
    - If magazine.lab_id is set:
        - LAB_ADMIN / ADMIN: allowed ONLY if magazine.lab_id in permitted_lab_ids.
    """
    if current_user.is_super_admin:
        return True

    if not current_user.is_lab_admin:
        raise ForbiddenException("Lab Administrator permissions required.")

    if magazine.lab_id is None:
        raise ForbiddenException("Access denied: only Super Administrators may access unassigned/global magazines.")

    permitted_lab_ids = await get_user_permitted_lab_ids(current_user, db)
    if magazine.lab_id not in permitted_lab_ids:
        raise ForbiddenException(f"Access denied: magazine belongs to lab #{magazine.lab_id}, not your assigned lab(s).")

    return True


async def check_template_access(
    current_user: User,
    template: MagazineTemplate,
    db: AsyncSession,
    require_write: bool = False,
) -> bool:
    """Verifies access to a template according to the 3 rules:
    1. Template is explicitly assigned to user's lab (via TemplateLabAssignment)
    2. Template is lab-specific and belongs to user's lab (template.lab_id in permitted labs)
    3. Template is global (is_global=True)
    
    Writing/Editing rules:
    - Super Admin can write/edit all templates.
    - Lab Admin CANNOT edit global templates (must use copy-on-write or create lab template).
    - Lab Admin can ONLY edit templates that belong specifically to their lab (template.lab_id in permitted).
    """
    if current_user.is_super_admin:
        return True

    if not current_user.is_lab_admin:
        raise ForbiddenException("Lab Administrator permissions required.")

    permitted_lab_ids = await get_user_permitted_lab_ids(current_user, db)
    if not permitted_lab_ids:
        raise ForbiddenException("Access denied: You have no active lab memberships.")

    if require_write:
        # Writing requires the template to be specifically owned by the user's lab
        if template.is_global or template.lab_id is None:
            raise ForbiddenException(
                "Access denied: Global templates cannot be modified directly by Lab Admins. "
                "Please clone or create a lab-specific template."
            )
        if template.lab_id not in permitted_lab_ids:
            raise ForbiddenException(
                f"Access denied: Template belongs to lab #{template.lab_id}, which is not in your permitted labs."
            )
        return True

    # Read access rules:
    # Rule 3: Global template
    if template.is_global:
        return True

    # Rule 2: Lab-specific
    if template.lab_id is not None and template.lab_id in permitted_lab_ids:
        return True

    # Rule 1: Explicit assignment
    stmt = (
        select(TemplateLabAssignment)
        .where(
            TemplateLabAssignment.template_id == template.id,
            TemplateLabAssignment.lab_id.in_(permitted_lab_ids),
            TemplateLabAssignment.is_active.is_(True),
        )
    )
    assigned = (await db.execute(stmt)).scalars().first()
    if assigned:
        return True

    raise ForbiddenException("Access denied: Template is not available to your lab.")


async def resolve_creation_lab(
    current_user: User,
    requested_lab_id: Optional[int],
    db: AsyncSession,
) -> Optional[int]:
    """Resolves and securely validates the target lab_id for a new magazine or asset.
    - Super Admin: can specify any lab_id or None (for global).
    - Lab Admin:
        - If belongs to 1 lab and none requested -> auto-assigns to that lab.
        - If belongs to multiple labs and none requested -> raises 400.
        - If requested -> verifies requested_lab_id is in user's permitted labs.
    """
    if current_user.is_super_admin:
        return requested_lab_id

    permitted = await get_user_permitted_lab_ids(current_user, db)
    if not permitted:
        raise ForbiddenException("Access denied: You have no active lab memberships.")

    if requested_lab_id is not None:
        if requested_lab_id not in permitted:
            raise ForbiddenException(f"Access denied: You do not have permission for lab #{requested_lab_id}.")
        return requested_lab_id

    if len(permitted) == 1:
        return permitted[0]

    from fastapi import HTTPException
    raise HTTPException(
        status_code=400,
        detail="User belongs to multiple labs; please select a specific lab_id."
    )
