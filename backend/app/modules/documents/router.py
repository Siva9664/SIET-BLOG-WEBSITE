from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.analysis import analyze_document
from app.core.database import get_db
from app.modules.auth.models import User
from app.modules.documents.chunker import chunk_document_spans
from pydantic import BaseModel, Field
from app.modules.documents.embeddings import backfill_embeddings, embed_text
from app.modules.documents.models import DocumentChunk, SourceDocument
from app.modules.documents.reranker import rerank
from app.modules.documents.retriever import retrieve
from app.modules.ingestion import (
    UnsupportedDocumentType,
    document_to_spans,
    parse_document,
)
from app.shared.auth.dependencies import (
    check_object_lab_access,
    get_user_permitted_lab_ids,
    require_admin,
    require_lab_admin,
    require_super_admin,
    verify_user_lab_access,
)
from app.shared.exceptions.custom import ForbiddenException, NotFoundException
from app.shared.responses.helpers import success

UPLOAD_DOCS_DIR = "uploads/documents"

router = APIRouter(prefix="/admin/documents", tags=["Admin Documents"])


class RetrieveRequest(BaseModel):
    query: str = Field(..., description="Content brief / search query")
    top_k: int = Field(20, ge=1, le=100)
    top_n: int = Field(5, ge=1, le=50)
    filters: dict | None = Field(default=None, description="Optional metadata filters e.g. {'document_id': 1}")


def _current_user_id(current_user: any) -> int | None:
    if hasattr(current_user, "id"):
        return int(current_user.id)
    if isinstance(current_user, dict) and "id" in current_user:
        return int(current_user["id"])
    return None


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_source_document(
    file: UploadFile = File(...),
    lab_id: Optional[int] = Query(None, description="Lab to assign document to"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lab_admin),
):
    """
    Phase 1 Document Intelligence Endpoint:
    Uploads a PDF, DOCX, PPTX, HTML, or text source document, then persists
    page-aware chunks compatible with the existing RAG retrieval path.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    # Determine and verify target lab
    target_lab_id: Optional[int] = None
    if current_user.is_super_admin:
        target_lab_id = lab_id
    else:
        permitted = await get_user_permitted_lab_ids(current_user, db)
        if not permitted:
            raise ForbiddenException("Access denied: You have no active lab membership.")
        if lab_id is not None:
            if lab_id not in permitted:
                raise ForbiddenException("Access denied: You do not have permission for this lab.")
            target_lab_id = lab_id
        elif len(permitted) == 1:
            target_lab_id = permitted[0]
        else:
            raise HTTPException(
                status_code=400,
                detail="User belongs to multiple labs; please provide lab_id query parameter."
            )

    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".pdf", ".docx", ".pptx", ".html", ".htm", ".txt", ".md"]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file format '{ext}'. Supported formats are PDF, DOCX, "
                "PPTX, HTML, and text."
            ),
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    os.makedirs(UPLOAD_DOCS_DIR, exist_ok=True)
    saved_filename = f"doc_{int(uuid.uuid1().time)}_{uuid.uuid4().hex[:6]}{ext}"
    storage_path = os.path.join(UPLOAD_DOCS_DIR, saved_filename)
    with open(storage_path, "wb") as f:
        f.write(file_bytes)

    # 1. Parse source document and derive structure without a model call.
    try:
        structured_document = parse_document(
            file_bytes,
            filename,
            file.content_type,
        )
        spans = document_to_spans(structured_document)
        structure = analyze_document(structured_document)
    except UnsupportedDocumentType as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse document '{filename}': {str(e)}"
        )

    if not spans:
        raise HTTPException(
            status_code=400,
            detail="No readable text content could be extracted from the document."
        )

    # 2. Chunk document spans
    chunks_data = chunk_document_spans(spans)

    total_chars = sum(len(c["text"]) for c in chunks_data)
    user_id = _current_user_id(current_user)

    doc_record = SourceDocument(
        filename=filename,
        mime_type=file.content_type or f"application/{ext.lstrip('.')}",
        storage_path=storage_path,
        uploaded_by=user_id,
        lab_id=target_lab_id,
        status="processed",
        char_count=total_chars,
    )
    db.add(doc_record)
    await db.commit()
    await db.refresh(doc_record)

    # 3. Create DocumentChunk records
    db_chunks = [
        DocumentChunk(
            document_id=doc_record.id,
            page_number=c["page_number"],
            section_label=c.get("section_label"),
            text=c["text"],
            char_start=c["char_start"],
            char_end=c["char_end"],
        )
        for c in chunks_data
    ]
    db.add_all(db_chunks)
    await db.commit()

    return success({
        "document_id": doc_record.id,
        "filename": doc_record.filename,
        "char_count": doc_record.char_count,
        "chunk_count": len(db_chunks),
        "status": doc_record.status,
        "storage_path": doc_record.storage_path,
        "created_at": doc_record.created_at.isoformat(),
        "structure": structure.to_dict(),
    })


@router.get("")
async def list_source_documents(
    lab_id: Optional[int] = Query(None, description="Filter documents by lab ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lab_admin),
):
    """Lists source documents scoped strictly to authorized labs:
    - Super Admin: sees all documents or filtered by lab_id.
    - Lab Admin: sees only documents belonging to their assigned active labs.
    """
    query = (
        select(SourceDocument)
        .options(selectinload(SourceDocument.chunks))
        .order_by(SourceDocument.id.desc())
    )

    if current_user.is_super_admin:
        if lab_id is not None:
            query = query.where(SourceDocument.lab_id == lab_id)
    else:
        permitted_ids = await get_user_permitted_lab_ids(current_user, db)
        if not permitted_ids:
            return success([])
        if lab_id is not None:
            if lab_id not in permitted_ids:
                raise ForbiddenException("Access denied: You do not have permission to view documents for this lab.")
            query = query.where(SourceDocument.lab_id == lab_id)
        else:
            query = query.where(SourceDocument.lab_id.in_(permitted_ids))

    rows = list((await db.execute(query)).scalars().all())

    result = [
        {
            "id": doc.id,
            "filename": doc.filename,
            "mime_type": doc.mime_type,
            "storage_path": doc.storage_path,
            "status": doc.status,
            "char_count": doc.char_count,
            "chunk_count": len(doc.chunks),
            "created_at": doc.created_at.isoformat(),
        }
        for doc in rows
    ]
    return success(result)


@router.get("/{document_id}/chunks")
async def get_document_chunks(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lab_admin),
):
    """Retrieves all chunks for a specific document with full page & section provenance.
    Strictly verifies object-level lab access (prevents IDOR).
    """
    doc = await db.get(SourceDocument, document_id)
    if not doc:
        raise NotFoundException(f"Source document #{document_id} not found.")

    await check_object_lab_access(current_user, doc.lab_id, db)

    query = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.page_number.asc(), DocumentChunk.char_start.asc())
    )
    chunks = list((await db.execute(query)).scalars().all())

    return success({
        "document": {
            "id": doc.id,
            "filename": doc.filename,
            "mime_type": doc.mime_type,
            "char_count": doc.char_count,
            "chunk_count": len(chunks),
        },
        "chunks": [
            {
                "id": c.id,
                "document_id": c.document_id,
                "page_number": c.page_number,
                "section_label": c.section_label,
                "text": c.text,
                "char_start": c.char_start,
                "char_end": c.char_end,
                "created_at": c.created_at.isoformat(),
            }
            for c in chunks
        ],
    })


@router.delete("/{document_id}")
async def delete_source_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lab_admin),
):
    """Deletes source document record, physical file, and associated chunks.
    Strictly verifies object-level lab access (prevents IDOR).
    """
    doc = await db.get(SourceDocument, document_id)
    if not doc:
        raise NotFoundException(f"Source document #{document_id} not found.")

    await check_object_lab_access(current_user, doc.lab_id, db)

    if doc.storage_path and os.path.exists(doc.storage_path):
        try:
            os.remove(doc.storage_path)
        except OSError:
            pass

    await db.delete(doc)
    await db.commit()
    return success({"message": f"Source document #{document_id} deleted successfully."})


@router.post("/backfill-embeddings")
async def trigger_backfill_embeddings(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    """
    Triggers batch calculation of embeddings for any chunk missing a vector representation.
    """
    updated_count = await backfill_embeddings(db)
    return success({
        "message": f"Backfilled embeddings for {updated_count} chunks.",
        "backfilled_count": updated_count,
    })


@router.post("/retrieve")
async def retrieve_passages(
    payload: RetrieveRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    """
    Phase 2 RAG Retrieval Inspection Endpoint:
    Given a content brief query, performs hybrid semantic & keyword retrieval,
    reranks candidates, and returns results with full provenance and confidence bands.
    """
    # 1. Backfill any missing embeddings first to ensure full coverage
    await backfill_embeddings(db)

    # 2. Hybrid Retrieval
    candidates = await retrieve(
        db=db,
        query=payload.query,
        top_k=payload.top_k,
        filters=payload.filters,
    )

    if not candidates:
        return success({
            "query": payload.query,
            "results_count": 0,
            "results": [],
        })

    # 3. Candidate Reranking
    reranked = await rerank(
        query=payload.query,
        candidates=candidates,
        top_n=payload.top_n,
    )

    return success({
        "query": payload.query,
        "results_count": len(reranked),
        "results": reranked,
    })
