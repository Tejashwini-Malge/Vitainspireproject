from sqlalchemy.orm import Session

from app.context import correlation_id
from app.models import AuditEvent


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
    """
    db.add(
        AuditEvent(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            actor_user_id=actor_user_id,
            org_id=org_id,
            details=details or {},
            correlation_id=correlation_id.get(),
        )
    )
