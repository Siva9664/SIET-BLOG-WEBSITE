import io
import os
from typing import Dict, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.magazine.models import Magazine
from app.modules.template_engine.analyzer import analyze_docx_template
from app.modules.template_engine.composer import generate_docx_from_blueprint
from app.modules.template_engine.models import DocxTemplateBlueprint
from app.shared.auth.dependencies import require_admin
from app.shared.responses.helpers import success

template_router = APIRouter(prefix="/admin/templates", tags=["DOCX Template Engine"])


class ConfirmBlueprintRequest(BaseModel):
    section_role_overrides: Optional[Dict[int, str]] = None  # {order: new_role}


class GenerateDocxRequest(BaseModel):
    content: Optional[Dict[str, str]] = None
    magazine_id: Optional[int] = None
    template_bytes_base64: Optional[str] = None


@template_router.post("/analyze")
async def api_analyze_docx_template(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    """
    Upload a .docx template file to analyze its structure, styles, tables, images, and placeholder roles.
    Persists an unconfirmed DocxTemplateBlueprint row.
    """
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Uploaded template file must be a .docx document.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    blueprint = analyze_docx_template(file_bytes, file.filename)

    record = DocxTemplateBlueprint(
        name=file.filename,
        blueprint_json=blueprint,
        is_confirmed=not blueprint.get("has_inferred_roles", False),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return success({
        "blueprint_id": record.id,
        "name": record.name,
        "is_confirmed": record.is_confirmed,
        "blueprint": blueprint,
    })


@template_router.post("/{blueprint_id}/confirm")
async def api_confirm_docx_blueprint(
    blueprint_id: int,
    payload: ConfirmBlueprintRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    """
    Admin Confirmation Endpoint:
    Review and override section role assignments (especially for inferred roles) before using for document generation.
    """
    record = await db.get(DocxTemplateBlueprint, blueprint_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"DocxTemplateBlueprint #{blueprint_id} not found.")

    bp = record.blueprint_json
    if payload.section_role_overrides:
        for sec in bp.get("sections", []):
            order = sec.get("order")
            if order in payload.section_role_overrides:
                sec["role"] = payload.section_role_overrides[order]
                sec["role_source"] = "admin_overridden"

    record.blueprint_json = bp
    record.is_confirmed = True
    await db.commit()

    return success({
        "blueprint_id": record.id,
        "is_confirmed": record.is_confirmed,
        "blueprint": record.blueprint_json,
    })


@template_router.post("/{blueprint_id}/generate")
async def api_generate_docx_document(
    blueprint_id: int,
    payload: GenerateDocxRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    """
    Document Generation Endpoint:
    Fills content into the specified DocxTemplateBlueprint and returns the generated .docx file.
    """
    record = await db.get(DocxTemplateBlueprint, blueprint_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"DocxTemplateBlueprint #{blueprint_id} not found.")

    # Read base template bytes
    template_bytes = b""
    if payload.template_bytes_base64:
        import base64
        template_bytes = base64.b64decode(payload.template_bytes_base64)
    else:
        # Load fallback template from Downloads/uploads if available
        siet_tmpl_path = "/home/shiva/Downloads/SIET-Magazine-Template.docx"
        if os.path.exists(siet_tmpl_path):
            with open(siet_tmpl_path, "rb") as f:
                template_bytes = f.read()

    if not template_bytes:
        raise HTTPException(status_code=400, detail="Base template .docx file is required.")

    content_dict: Dict[str, str] = payload.content or {}

    # If magazine_id provided, pull grounded magazine content from DB
    if payload.magazine_id:
        mag = await db.get(Magazine, payload.magazine_id)
        if mag:
            content_dict.update({
                "issue_title": mag.title,
                "writeup_headline": mag.title,
                "article_body": mag.description or "",
            })

    output_bytes = generate_docx_from_blueprint(
        blueprint=record.blueprint_json,
        content=content_dict,
        template_bytes=template_bytes,
    )

    filename = f"generated_{record.name}"
    return Response(
        content=output_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
