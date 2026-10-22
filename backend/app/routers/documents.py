import hashlib
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.config import settings
from app.db import get_db
from app.deps import get_current_user, require_membership
from app.documents.validation import UploadError, safe_filename, validate_upload
from app.models import Document, DocumentReviewDecision, DocumentType, Organization, OrgType, ReviewStatus, Role, User
from app.schemas import DecisionOut, DocumentOut
from app.storage_dep import get_storage

router = APIRouter(prefix="/orgs/{org_id}/documents", tags=["documents"])

MANAGE = frozenset({Role.OWNER, Role.ADMIN})


def _latest_decisions(db: Session, doc_ids: list[str]) -> dict[str, DecisionOut]:
    if not doc_ids:
        return {}
    rows = db.scalars(
        select(DocumentReviewDecision)
        .where(DocumentReviewDecision.document_id.in_(doc_ids))
        .order_by(DocumentReviewDecision.decided_at.desc(), DocumentReviewDecision.id.desc())
    ).all()
    latest: dict[str, DecisionOut] = {}
    for d in rows:
        latest.setdefault(d.document_id, _decision_out(d))  # first row per document is the newest
    return latest


def _decision_out(d: DocumentReviewDecision) -> DecisionOut:
    return DecisionOut(
        id=d.id,
        decision=d.decision,
        reason=d.reason,
        previous_status=d.previous_status,
        decided_at=d.decided_at,
    )


def _doc_out(doc: Document, latest: DecisionOut | None) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        org_id=doc.org_id,
        doc_type=doc.doc_type,
        title=doc.title,
        original_filename=doc.original_filename,
        content_type=doc.content_type,
        size_bytes=doc.size_bytes,
        sha256=doc.sha256,
        valid_until_stated=doc.valid_until_stated,
        review_status=doc.review_status,
        uploaded_at=doc.uploaded_at,
        latest_decision=latest,
    )


def file_response(content: bytes, content_type: str, filename: str) -> Response:
    # attachment + nosniff: the browser saves the file rather than rendering it inline.
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def upload_document(
    org_id: str,
    doc_type: DocumentType = Form(...),
    title: str = Form(..., min_length=1, max_length=200),
    valid_until: date | None = Form(default=None),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentOut:
    require_membership(db, user, org_id, allowed_roles=MANAGE)
    org = db.get(Organization, org_id)
    if org is None:
        raise RuntimeError(f"Membership references missing organization {org_id}")
    if org.org_type is not OrgType.NGO:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Compliance documents are collected for NGO organizations")

    # Read one byte past the limit so an oversized file is detected without loading an unbounded body.
    content = file.file.read(settings.max_upload_bytes + 1)
    try:
        content_type = validate_upload(content, file.content_type or "", settings.max_upload_bytes)
    except UploadError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))

    digest = hashlib.sha256(content).hexdigest()
    # Scoped to the document type: the same scanned page can legitimately serve as evidence
    # for two different document types, but re-uploading it for the same type is a duplicate.
    duplicate = db.scalar(
        select(Document.id).where(
            Document.org_id == org_id,
            Document.doc_type == doc_type,
            Document.sha256 == digest,
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This exact file has already been uploaded as your {doc_type.value} document",
        )

    storage = get_storage()
    key = storage.put(content)
    try:
        doc = Document(
            org_id=org_id,
            doc_type=doc_type,
            title=title.strip(),
            original_filename=safe_filename(file.filename),
            content_type=content_type,
            size_bytes=len(content),
            sha256=digest,
            storage_key=key,
            valid_until_stated=valid_until,
            uploaded_by_user_id=user.id,
        )
        db.add(doc)
        db.flush()
        record_audit(
            db,
            action="document.uploaded",
            resource_type="document",
            resource_id=doc.id,
            actor_user_id=user.id,
            org_id=org_id,
            details={"doc_type": doc_type.value, "sha256": digest, "size_bytes": len(content)},
        )
        db.commit()
    except Exception:
        # The file was written before the row existed. If the row cannot be saved, remove the orphan and re-raise.
        db.rollback()
        storage.delete(key)
        raise
    return _doc_out(doc, None)


@router.get("", response_model=list[DocumentOut])
def list_documents(org_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[DocumentOut]:
    require_membership(db, user, org_id)
    docs = db.scalars(
        select(Document).where(Document.org_id == org_id).order_by(Document.uploaded_at.desc(), Document.id)
    ).all()
    latest = _latest_decisions(db, [d.id for d in docs])
    return [_doc_out(d, latest.get(d.id)) for d in docs]


@router.get("/{doc_id}/decisions", response_model=list[DecisionOut])
def list_decisions(
    org_id: str, doc_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[DecisionOut]:
    require_membership(db, user, org_id)
    doc = db.scalar(select(Document).where(Document.id == doc_id, Document.org_id == org_id))
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    rows = db.scalars(
        select(DocumentReviewDecision)
        .where(DocumentReviewDecision.document_id == doc_id)
        .order_by(DocumentReviewDecision.decided_at, DocumentReviewDecision.id)
    ).all()
    return [_decision_out(d) for d in rows]


@router.get("/{doc_id}/download")
def download_document(
    org_id: str, doc_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    require_membership(db, user, org_id)
    doc = db.scalar(select(Document).where(Document.id == doc_id, Document.org_id == org_id))
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    content = get_storage().read(doc.storage_key)
    record_audit(
        db,
        action="document.downloaded",
        resource_type="document",
        resource_id=doc.id,
        actor_user_id=user.id,
        org_id=org_id,
    )
    db.commit()
    return file_response(content, doc.content_type, doc.original_filename)
