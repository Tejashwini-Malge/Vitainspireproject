"""Deterministic review gate. No AI output reaches this code path as a decision."""

from app.models import ReviewStatus


class ReviewError(ValueError):
    """Raised when a review decision is not allowed. The message is shown to the reviewer."""


def decide(current: ReviewStatus, decision: ReviewStatus, reason: str) -> ReviewStatus:
    if current is not ReviewStatus.PENDING_REVIEW:
        # Decided documents are final. A correction is a new upload, not an edit of history.
        raise ReviewError(f"This document is already {current.value.lower().replace('_', ' ')} and cannot be decided again")
    if decision not in (ReviewStatus.APPROVED, ReviewStatus.REJECTED):
        raise ReviewError("Decision must be APPROVED or REJECTED")
    if not reason.strip():
        raise ReviewError("A reason is required for every review decision")
    return decision
