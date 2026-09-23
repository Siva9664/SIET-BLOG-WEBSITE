from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.modules.auth.models import User
from app.modules.labs.models import Lab, LabMembership, TemplateLabAssignment
from app.modules.labs.schemas import (
    LabCreate, LabResponse, LabUpdate,
    LabMembershipCreate, LabMembershipResponse,
    TemplateLabAssignmentCreate, TemplateLabAssignmentResponse,
)
from app.shared.auth.dependencies import (
    get_user_permitted_lab_ids,
    require_lab_admin,
    require_super_admin,
    verify_user_lab_access,
)
from app.shared.exceptions.custom import ForbiddenException, NotFoundException
from app.shared.responses.helpers import success

router = APIRouter(prefix="/admin/labs", tags=["Labs Management"])


@router.get("", response_model=List[LabResponse])
async def list_labs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lab_admin),
):
    """List labs.
    - SUPER_ADMIN: returns all active labs.
    - LAB_ADMIN: returns ONLY labs the user has an active membership in.
    """
    stmt = select(Lab).order_by(Lab.id.asc())
    if not current_user.is_super_admin:
        permitted = await get_user_permitted_lab_ids(current_user, db)
        stmt = stmt.where(Lab.id.in_(permitted))

    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=LabResponse, status_code=status.HTTP_201_CREATED)
async def create_lab(
    payload: LabCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Create a new Lab (SUPER_ADMIN only)."""
    # Check uniqueness of name/code/slug
    existing = await db.execute(
        select(Lab).where(
            (Lab.name == payload.name) | (Lab.code == payload.code) | (Lab.slug == payload.slug)
        )
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="A lab with this name, code, or slug already exists.")

    lab = Lab(
        name=payload.name.strip(),
        code=payload.code.strip().upper(),
        slug=payload.slug.strip().lower(),
        department_id=payload.department_id,
        description=payload.description,
        is_active=payload.is_active,
    )
    db.add(lab)
    await db.commit()
    await db.refresh(lab)
    return lab


@router.get("/{lab_id}", response_model=LabResponse)
async def get_lab(
    lab_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lab_admin),
):
    """Get single lab details. Enforces lab membership access."""
    await verify_user_lab_access(current_user, lab_id, db)
    lab = await db.get(Lab, lab_id)
    if not lab:
        raise NotFoundException(f"Lab #{lab_id} not found.")
    return lab


@router.put("/{lab_id}", response_model=LabResponse)
async def update_lab(
    lab_id: int,
    payload: LabUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Update lab configuration (SUPER_ADMIN only)."""
    lab = await db.get(Lab, lab_id)
    if not lab:
        raise NotFoundException(f"Lab #{lab_id} not found.")

    if payload.name is not None:
        lab.name = payload.name.strip()
    if payload.code is not None:
        lab.code = payload.code.strip().upper()
    if payload.slug is not None:
        lab.slug = payload.slug.strip().lower()
    if payload.department_id is not None:
        lab.department_id = payload.department_id
    if payload.description is not None:
        lab.description = payload.description
    if payload.is_active is not None:
        lab.is_active = payload.is_active

    await db.commit()
    await db.refresh(lab)
    return lab


# ─── LAB MEMBERSHIPS (SUPER_ADMIN ONLY) ──────────────────────────────────────────

@router.get("/{lab_id}/members", response_model=List[LabMembershipResponse])
async def list_lab_members(
    lab_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lab_admin),
):
    """List members of a lab. Super Admin or members of the lab can view."""
    await verify_user_lab_access(current_user, lab_id, db)
    stmt = (
        select(LabMembership)
        .options(selectinload(LabMembership.user))
        .where(LabMembership.lab_id == lab_id)
    )
    result = await db.execute(stmt)
    memberships = list(result.scalars().all())
    return [
        LabMembershipResponse(
            id=m.id,
            user_id=m.user_id,
            lab_id=m.lab_id,
            role=m.role,
            is_active=m.is_active,
            user_name=m.user.name if m.user else None,
            user_email=m.user.email if m.user else None,
        )
        for m in memberships
    ]


@router.post("/{lab_id}/members", response_model=LabMembershipResponse, status_code=status.HTTP_201_CREATED)
async def assign_lab_member(
    lab_id: int,
    payload: LabMembershipCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Assign a user to a lab (SUPER_ADMIN only)."""
    lab = await db.get(Lab, lab_id)
    if not lab:
        raise NotFoundException(f"Lab #{lab_id} not found.")

    target_user = await db.get(User, payload.user_id)
    if not target_user:
        raise NotFoundException(f"User #{payload.user_id} not found.")

    # Check if membership already exists
    stmt = select(LabMembership).where(
        LabMembership.lab_id == lab_id,
        LabMembership.user_id == payload.user_id
    )
    existing = (await db.execute(stmt)).scalars().first()
    if existing:
        existing.is_active = payload.is_active
        existing.role = payload.role
        await db.commit()
        await db.refresh(existing)
        return LabMembershipResponse(
            id=existing.id,
            user_id=existing.user_id,
            lab_id=existing.lab_id,
            role=existing.role,
            is_active=existing.is_active,
            user_name=target_user.name,
            user_email=target_user.email,
        )

    membership = LabMembership(
        user_id=payload.user_id,
        lab_id=lab_id,
        role=payload.role,
        is_active=payload.is_active,
    )
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return LabMembershipResponse(
        id=membership.id,
        user_id=membership.user_id,
        lab_id=membership.lab_id,
        role=membership.role,
        is_active=membership.is_active,
        user_name=target_user.name,
        user_email=target_user.email,
    )


@router.delete("/{lab_id}/members/{user_id}")
async def remove_lab_member(
    lab_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Remove user from lab (SUPER_ADMIN only)."""
    stmt = select(LabMembership).where(
        LabMembership.lab_id == lab_id,
        LabMembership.user_id == user_id
    )
    membership = (await db.execute(stmt)).scalars().first()
    if not membership:
        raise NotFoundException("Lab membership not found.")
    await db.delete(membership)
    await db.commit()
    return {"message": "Membership removed successfully."}


# ─── TEMPLATE LAB ASSIGNMENTS ──────────────────────────────────────────────────

@router.get("/{lab_id}/templates", response_model=List[TemplateLabAssignmentResponse])
async def list_lab_assigned_templates(
    lab_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lab_admin),
):
    """List templates assigned to this lab."""
    await verify_user_lab_access(current_user, lab_id, db)
    stmt = (
        select(TemplateLabAssignment)
        .options(selectinload(TemplateLabAssignment.template))
        .where(TemplateLabAssignment.lab_id == lab_id, TemplateLabAssignment.is_active == True)
    )
    result = await db.execute(stmt)
    assignments = list(result.scalars().all())
    return [
        TemplateLabAssignmentResponse(
            id=a.id,
            template_id=a.template_id,
            lab_id=a.lab_id,
            is_active=a.is_active,
            template_name=a.template.name if a.template else None,
        )
        for a in assignments
    ]


@router.post("/{lab_id}/templates", response_model=TemplateLabAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign_template_to_lab(
    lab_id: int,
    payload: TemplateLabAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Assign a template to a lab (SUPER_ADMIN only)."""
    from app.modules.magazine.models import MagazineTemplate
    lab = await db.get(Lab, lab_id)
    if not lab:
        raise NotFoundException(f"Lab #{lab_id} not found.")

    tmpl = await db.get(MagazineTemplate, payload.template_id)
    if not tmpl:
        raise NotFoundException(f"Template #{payload.template_id} not found.")

    stmt = select(TemplateLabAssignment).where(
        TemplateLabAssignment.lab_id == lab_id,
        TemplateLabAssignment.template_id == payload.template_id
    )
    existing = (await db.execute(stmt)).scalars().first()
    if existing:
        existing.is_active = payload.is_active
        await db.commit()
        await db.refresh(existing)
        return TemplateLabAssignmentResponse(
            id=existing.id,
            template_id=existing.template_id,
            lab_id=existing.lab_id,
            is_active=existing.is_active,
            template_name=tmpl.name,
        )

    assignment = TemplateLabAssignment(
        template_id=payload.template_id,
        lab_id=lab_id,
        is_active=payload.is_active,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return TemplateLabAssignmentResponse(
        id=assignment.id,
        template_id=assignment.template_id,
        lab_id=assignment.lab_id,
        is_active=assignment.is_active,
        template_name=tmpl.name,
    )
