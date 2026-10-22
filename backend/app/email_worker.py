"""Background worker for processing the email queue. Can be run via Celery, APScheduler, or manually."""

import asyncio
from datetime import datetime
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.email_service import get_email_provider, EmailMessage
from app.models import EmailQueue, SentEmail

logger = structlog.get_logger(__name__)

# Maximum retries for failed emails
MAX_RETRIES = 3


async def process_email_queue(batch_size: int = 50) -> dict:
    """
    Process pending emails from the queue.

    Returns stats dict with:
    - sent: number of successfully sent emails
    - failed: number of emails that failed
    - retried: number of emails that exceeded retry limit
    """
    db = SessionLocal()
    try:
        provider = get_email_provider()
        stats = {"sent": 0, "failed": 0, "retried": 0}

        # Get pending emails
        pending = db.execute(
            select(EmailQueue)
            .where(EmailQueue.status == "PENDING")
            .order_by(EmailQueue.created_at)
            .limit(batch_size)
        ).scalars().all()

        if not pending:
            logger.info("email_queue_empty")
            return stats

        logger.info("processing_email_queue", count=len(pending))

        for queue_item in pending:
            try:
                # Create email message
                message = EmailMessage(
                    recipient_email=queue_item.recipient_email,
                    recipient_user_id=queue_item.recipient_user_id,
                    event_type=queue_item.event_type,
                    subject=queue_item.subject,
                    html_body=queue_item.html_body,
                    text_body=queue_item.text_body,
                    template_name=queue_item.template_name,
                    template_data=queue_item.template_data,
                )

                # Send via provider
                success, external_id = await provider.send(message)

                if success:
                    # Mark as sent
                    queue_item.status = "SENT"
                    queue_item.sent_at = datetime.now()

                    # Create audit record
                    sent_email = SentEmail(
                        id=queue_item.id,
                        email_queue_id=queue_item.id,
                        recipient_email=queue_item.recipient_email,
                        recipient_user_id=queue_item.recipient_user_id,
                        event_type=queue_item.event_type,
                        subject=queue_item.subject,
                        delivery_provider=provider.__class__.__name__,
                        external_message_id=external_id,
                    )
                    db.add(sent_email)
                    stats["sent"] += 1

                    logger.info(
                        "email_sent",
                        queue_id=queue_item.id,
                        recipient=queue_item.recipient_email,
                        event_type=queue_item.event_type,
                    )
                else:
                    # Retry logic
                    if queue_item.retry_count < MAX_RETRIES:
                        queue_item.retry_count += 1
                        queue_item.error_message = external_id or "Unknown error"
                        stats["failed"] += 1

                        logger.warning(
                            "email_send_failed_will_retry",
                            queue_id=queue_item.id,
                            retry_count=queue_item.retry_count,
                            error=external_id,
                        )
                    else:
                        queue_item.status = "FAILED"
                        queue_item.error_message = (
                            f"Exceeded max retries ({MAX_RETRIES}): {external_id}"
                        )
                        stats["retried"] += 1

                        logger.error(
                            "email_send_failed_max_retries",
                            queue_id=queue_item.id,
                            error=external_id,
                        )

            except Exception as e:
                logger.error(
                    "email_worker_exception",
                    queue_id=queue_item.id,
                    error=str(e),
                )
                queue_item.error_message = str(e)
                if queue_item.retry_count < MAX_RETRIES:
                    queue_item.retry_count += 1
                else:
                    queue_item.status = "FAILED"

        db.commit()
        logger.info("email_queue_processed", stats=stats)
        return stats

    except Exception as e:
        logger.error("email_worker_fatal_error", error=str(e))
        db.rollback()
        return {"sent": 0, "failed": 0, "retried": 0, "error": str(e)}
    finally:
        db.close()


def queue_email(
    db: Session,
    recipient_email: str,
    event_type: str,
    subject: str,
    html_body: str,
    recipient_user_id: Optional[str] = None,
    text_body: Optional[str] = None,
    template_name: str = "",
    template_data: Optional[dict] = None,
) -> str:
    """
    Add an email to the queue for sending.

    Returns the email ID.
    """
    import uuid

    email = EmailQueue(
        id=str(uuid.uuid4()),
        recipient_email=recipient_email,
        recipient_user_id=recipient_user_id,
        event_type=event_type,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        template_name=template_name,
        template_data=template_data,
        status="PENDING",
    )
    db.add(email)
    db.commit()
    return email.id


# Simple standalone runner for testing
if __name__ == "__main__":
    asyncio.run(process_email_queue())
