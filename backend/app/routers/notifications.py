from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Notification, User
from app.schemas import NotificationOut, NotificationSummaryOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def get_notifications(
    user: User = Depends(get_current_user),
    unread_only: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[NotificationOut]:
    """Get notifications for current user."""
    query = select(Notification).where(
        Notification.recipient_user_id == user.id
    ).order_by(Notification.created_at.desc()).limit(limit)

    if unread_only:
        query = query.where(Notification.is_read == False)

    notifications = db.scalars(query).all()
    return [_notification_out(n) for n in notifications]


@router.get("/summary", response_model=NotificationSummaryOut)
def get_notification_summary(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationSummaryOut:
    """Get notification summary (unread count + recent notifications)."""
    unread_count = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.recipient_user_id == user.id,
            Notification.is_read == False,
        )
    ) or 0

    total_count = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.recipient_user_id == user.id)
    ) or 0

    recent = db.scalars(
        select(Notification)
        .where(Notification.recipient_user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(10)
    ).all()

    return NotificationSummaryOut(
        unread_count=unread_count,
        total_count=total_count,
        recent_notifications=[_notification_out(n) for n in recent],
    )


@router.put("/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationOut:
    """Mark a notification as read."""
    notif = db.get(Notification, notification_id)
    if notif is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")

    if notif.recipient_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot read other user's notification")

    notif.is_read = True
    notif.read_at = datetime.now(UTC)
    db.commit()

    return _notification_out(notif)


@router.put("/mark-all-read", response_model=dict)
def mark_all_notifications_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Mark all notifications as read."""
    db.execute(
        select(Notification)
        .where(
            Notification.recipient_user_id == user.id,
            Notification.is_read == False,
        )
    )
    unread = db.scalars(
        select(Notification).where(
            Notification.recipient_user_id == user.id,
            Notification.is_read == False,
        )
    ).all()

    for notif in unread:
        notif.is_read = True
        notif.read_at = datetime.now(UTC)

    db.commit()
    return {"marked_read": len(unread)}


def _notification_out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=n.id,
        recipient_user_id=n.recipient_user_id,
        proposal_id=n.proposal_id,
        notification_type=n.notification_type,
        title=n.title,
        message=n.message,
        actor_user_id=n.actor_user_id,
        is_read=n.is_read,
        created_at=n.created_at,
        read_at=n.read_at,
    )
