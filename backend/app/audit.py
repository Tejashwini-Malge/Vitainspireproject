import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.context import correlation_id
from app.models import AuditEvent


def _row_hash(
    *,
    occurred_at: datetime,
    action: str,
    resource_type: str,
    resource_id: str,
    actor_user_id: str | None,
    org_id: str | None,
    details: dict,
    correlation_id_value: str | None,
    prev_hash: str | None,
) -> str:
    """Deterministic hash of one audit row's content plus the previous row's hash.

    json.dumps with sort_keys makes `details` order-independent; everything else is a
    plain scalar already in a stable order. Changing any field, or the chain position,
    changes this hash -- that is the entire point.

    occurred_at is normalised to UTC before formatting: Postgres returns a TIMESTAMPTZ
    localised to the session's timezone, not necessarily the UTC it was written in, so the
    same instant can come back with a different offset in its isoformat() string. Hashing
    the un-normalised string would make verification depend on the DB session's timezone
    setting rather than the row's actual content.
    """
    payload = "|".join(
        [
            occurred_at.astimezone(UTC).isoformat(),
            action,
            resource_type,
            resource_id,
            actor_user_id or "",
            org_id or "",
            json.dumps(details, sort_keys=True, default=str),
            correlation_id_value or "",
            prev_hash or "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def record_audit(
    db: Session,
    *,
    action: str,
    resource_type: str,
    resource_id: str,
    actor_user_id: str | None,
    org_id: str | None = None,
    details: dict | None = None,
) -> None:
    """Stage an audit row in the caller's transaction. The caller commits.

    Deliberately no separate commit: if the business change rolls back, the audit
    row rolls back with it, so the log never claims an action that did not happen.

    Each row is chained to the previous one via prev_hash/row_hash (see AuditEvent and
    GET /admin/audit/verify). Looking up the previous hash by `seq` rather than
    `occurred_at` keeps the chain correct even when two audit rows are staged within the
    same transaction (flush below makes the first visible to the lookup for the second).
    """
    details = details or {}
    occurred_at = datetime.now(UTC)
    prev_hash = db.scalar(select(AuditEvent.row_hash).order_by(AuditEvent.seq.desc()).limit(1))
    row_hash = _row_hash(
        occurred_at=occurred_at,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        actor_user_id=actor_user_id,
        org_id=org_id,
        details=details,
        correlation_id_value=correlation_id.get(),
        prev_hash=prev_hash,
    )
    db.add(
        AuditEvent(
            occurred_at=occurred_at,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            actor_user_id=actor_user_id,
            org_id=org_id,
            details=details,
            correlation_id=correlation_id.get(),
            prev_hash=prev_hash,
            row_hash=row_hash,
        )
    )
    db.flush()
