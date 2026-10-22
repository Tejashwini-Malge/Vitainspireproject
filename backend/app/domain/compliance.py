"""Which compliance documents an NGO must have approved before it can act publicly.

Deterministic: this decides eligibility, so it lives in the domain layer and is the
single source of truth for both project publishing and proposal submission.
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, DocumentReviewDecision, DocumentType, ReviewStatus

# FCRA is deliberately NOT required. Under the Foreign Contribution (Regulation) Act it
# applies only to organisations that receive foreign contributions; most domestic Indian
# NGOs never hold one and can never obtain it. Requiring it universally would permanently
# block them from publishing a project or submitting a proposal.
REQUIRED_DOC_TYPES: frozenset[DocumentType] = frozenset(
    {
        DocumentType.PAN,
        DocumentType.REGISTRATION,
        DocumentType.SECTION_12A,
        DocumentType.SECTION_80G,
    }
)

_FRIENDLY_NAMES: dict[DocumentType, str] = {
    DocumentType.PAN: "PAN",
    DocumentType.REGISTRATION: "Registration certificate",
    DocumentType.SECTION_12A: "Section 12A",
    DocumentType.SECTION_80G: "Section 80G",
    DocumentType.FCRA: "FCRA",
}


def approved_doc_types(db: Session, org_id: str) -> set[DocumentType]:
    """Document types this organisation has had approved by a reviewer."""
    return set(
        db.scalars(
            select(Document.doc_type)
            .join(DocumentReviewDecision, Document.id == DocumentReviewDecision.document_id)
            .where(
                Document.org_id == org_id,
                DocumentReviewDecision.decision == ReviewStatus.APPROVED,
            )
            .distinct()
        ).all()
    )


def missing_required_documents(db: Session, org_id: str) -> set[DocumentType]:
    """Required document types that are not yet approved. Empty means the org is clear."""
    return set(REQUIRED_DOC_TYPES) - approved_doc_types(db, org_id)


def require_compliance_documents(db: Session, org_id: str, action: str) -> None:
    """Raise 403 naming exactly what is still missing, or return if the org is clear.

    `action` completes the sentence "before <action>", e.g. "publishing a project".
    """
    missing = missing_required_documents(db, org_id)
    if not missing:
        return

    names = ", ".join(sorted(_FRIENDLY_NAMES[d] for d in missing))
    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        f"Before {action}, these documents must be uploaded and approved by a reviewer: {names}.",
    )
