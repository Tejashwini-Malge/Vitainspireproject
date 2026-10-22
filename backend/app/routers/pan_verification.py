import hashlib

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.documents.validation import UploadError, safe_filename, validate_upload
from app.domain.pan import PanFormatError, is_pan_verified, normalize_pan
from app.models import PanVerification, PanVerificationDecision, User
from app.schemas import DecisionOut, PanVerificationOut, PanVerificationStatusOut
from app.storage_dep import get_storage

router = APIRouter(prefix="/me/pan-verification", tags=["pan-verification"])


def _latest_decisions(db: Session, submission_ids: list[str]) -> dict[str, DecisionOut]:
    if not submission_ids:
        return {}
    rows = db.scalars(
        select(PanVerificationDecision)
        .where(PanVerificationDecision.pan_verification_id.in_(submission_ids))
        .order_by(PanVerificationDecision.decided_at.desc(), PanVerificationDecision.id.desc())
    ).all()
    latest: dict[str, DecisionOut] = {}
    for d in rows:
        latest.setdefault(d.pan_verification_id, _decision_out(d))
    return latest


def _decision_out(d: PanVerificationDecision) -> DecisionOut:
    return DecisionOut(
        id=d.id,
        decision=d.decision,
        reason=d.reason,
        previous_status=d.previous_status,
        decided_at=d.decided_at,
    )


def _out(sub: PanVerification, latest: DecisionOut | None) -> PanVerificationOut:
    return PanVerificationOut(
        id=sub.id,
        user_id=sub.user_id,
        pan_number=sub.pan_number,
        original_filename=sub.original_filename,
        content_type=sub.content_type,
        size_bytes=sub.size_bytes,
        sha256=sub.sha256,
        review_status=sub.review_status,
        uploaded_at=sub.uploaded_at,
        latest_decision=latest,
    )


@router.post("", response_model=PanVerificationOut, status_code=status.HTTP_201_CREATED)
def upload_pan(
    pan_number: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PanVerificationOut:
    try:
        pan = normalize_pan(pan_number)
    except PanFormatError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))

    # Read one byte past the limit so an oversized file is detected without loading an unbounded body.
    content = file.file.read(settings.max_upload_bytes + 1)
    try:
        content_type = validate_upload(content, file.content_type or "", settings.max_upload_bytes)
    except UploadError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))

    digest = hashlib.sha256(content).hexdigest()
    duplicate = db.scalar(
        select(PanVerification.id).where(PanVerification.user_id == user.id, PanVerification.sha256 == digest)
    )
    if duplicate is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This exact file has already been submitted for PAN verification")

    storage = get_storage()
    key = storage.put(content)
    try:
        sub = PanVerification(
            user_id=user.id,
            pan_number=pan,
            original_filename=safe_filename(file.filename),
            content_type=content_type,
            size_bytes=len(content),
            sha256=digest,
            storage_key=key,
        )
        db.add(sub)
        db.flush()
        record_audit(
            db,
            action="pan_verification.uploaded",
            resource_type="pan_verification",
            resource_id=sub.id,
            actor_user_id=user.id,
            details={"sha256": digest, "size_bytes": len(content)},
        )
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(key)
        raise
    return _out(sub, None)


@router.get("", response_model=list[PanVerificationOut])
def list_my_pan_submissions(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[PanVerificationOut]:
    subs = db.scalars(
        select(PanVerification).where(PanVerification.user_id == user.id).order_by(PanVerification.uploaded_at.desc())
    ).all()
    latest = _latest_decisions(db, [s.id for s in subs])
    return [_out(s, latest.get(s.id)) for s in subs]


@router.get("/status", response_model=PanVerificationStatusOut)
def pan_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PanVerificationStatusOut:
    verified = is_pan_verified(db, user.id)
    latest = db.scalar(
        select(PanVerification).where(PanVerification.user_id == user.id).order_by(PanVerification.uploaded_at.desc())
    )
    return PanVerificationStatusOut(
        verified=verified,
        status=latest.review_status if latest else None,
        pan_number=latest.pan_number if latest else None,
    )


@router.get("/{submission_id}/decisions", response_model=list[DecisionOut])
def list_decisions(submission_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[DecisionOut]:
    sub = db.scalar(select(PanVerification).where(PanVerification.id == submission_id, PanVerification.user_id == user.id))
    if sub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PAN verification submission not found")
    rows = db.scalars(
        select(PanVerificationDecision)
        .where(PanVerificationDecision.pan_verification_id == submission_id)
        .order_by(PanVerificationDecision.decided_at, PanVerificationDecision.id)
    ).all()
    return [_decision_out(d) for d in rows]
