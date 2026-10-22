"""PAN number format and verification status. Deterministic: no AI output reaches this code path."""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PanVerification, ReviewStatus

# Indian PAN: five letters, four digits, one letter (e.g. ABCDE1234F). Format only -
# this does not confirm the number is real or belongs to the uploader; a human reviewer does that.
PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


class PanFormatError(ValueError):
    """Raised when a PAN number does not match the expected format. The message is shown to the uploader."""


def normalize_pan(raw: str) -> str:
    value = raw.strip().upper()
    if not PAN_PATTERN.match(value):
        raise PanFormatError("PAN must be 10 characters in the format ABCDE1234F")
    return value


def is_pan_verified(db: Session, user_id: str) -> bool:
    """True once at least one of the user's PAN submissions has been approved."""
    return (
        db.scalar(
            select(PanVerification.id).where(
                PanVerification.user_id == user_id, PanVerification.review_status == ReviewStatus.APPROVED
            )
        )
        is not None
    )
