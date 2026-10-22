"""Email service for sending notifications. Pluggable design supports multiple providers."""

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger("vitainspire.email")


class EventType(str, Enum):
    """Email event types that trigger notifications."""
    DONATION_RECEIVED = "donation_received"
    DONATION_CONFIRMATION = "donation_confirmation"
    TAX_RECEIPT_ISSUED = "tax_receipt_issued"
    CAMPAIGN_PUBLISHED = "campaign_published"
    MILESTONE_REACHED = "milestone_reached"
    NGO_VERIFIED = "ngo_verified"
    DONOR_DIGEST = "donor_digest"


@dataclass
class EmailMessage:
    """Represents an email to send."""
    recipient_email: str
    recipient_user_id: Optional[str]
    event_type: str
    subject: str
    html_body: str
    text_body: Optional[str] = None
    template_name: str = ""
    template_data: Optional[dict] = None


class EmailProvider(ABC):
    """Abstract base for email providers."""

    @abstractmethod
    async def send(self, message: EmailMessage) -> tuple[bool, Optional[str]]:
        """Send an email. Returns (success, external_message_id or error_message)."""
        pass


class MockEmailProvider(EmailProvider):
    """Mock provider for development. Logs emails instead of sending them."""

    async def send(self, message: EmailMessage) -> tuple[bool, Optional[str]]:
        """Log the email and return success."""
        logger.info(
            "mock_email_sent recipient=%s event_type=%s subject=%s",
            message.recipient_email, message.event_type, message.subject,
        )
        return True, f"mock-{message.event_type}-{message.recipient_email}"


class SendGridEmailProvider(EmailProvider):
    """SendGrid email provider. Requires SENDGRID_API_KEY in environment."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize with optional API key (defaults to env var)."""
        self.api_key = api_key or os.getenv("SENDGRID_API_KEY")
        if not self.api_key:
            logger.warning("SendGrid API key not configured, falling back to mock provider")
            self.use_mock = True
        else:
            self.use_mock = False

    async def send(self, message: EmailMessage) -> tuple[bool, Optional[str]]:
        """Send email via SendGrid. Falls back to mock if not configured."""
        if self.use_mock:
            mock = MockEmailProvider()
            return await mock.send(message)

        try:
            # Import here to avoid hard dependency
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To, Content

            mail = Mail(
                from_email=Email("noreply@imparency.org", "Imparency"),
                to_emails=To(message.recipient_email),
                subject=message.subject,
                plain_text_content=message.text_body or message.html_body,
                html_content=message.html_body,
            )

            sg = SendGridAPIClient(self.api_key)
            response = sg.send(mail)

            if response.status_code == 202:
                logger.info(
                    "email_sent_via_sendgrid recipient=%s event_type=%s",
                    message.recipient_email, message.event_type,
                )
                return True, response.headers.get("X-Message-ID")
            else:
                logger.error("sendgrid_send_failed status=%s body=%s", response.status_code, response.body)
                return False, f"SendGrid returned {response.status_code}"

        except ImportError:
            logger.warning("sendgrid library not installed, using mock provider")
            mock = MockEmailProvider()
            return await mock.send(message)
        except Exception as e:
            logger.error("sendgrid_send_error: %s", e)
            return False, str(e)


def get_email_provider() -> EmailProvider:
    """Get the configured email provider."""
    provider_name = os.getenv("EMAIL_PROVIDER", "mock").lower()

    if provider_name == "sendgrid":
        return SendGridEmailProvider()
    else:
        return MockEmailProvider()


# Email template constants
EMAIL_TEMPLATES = {
    EventType.DONATION_RECEIVED: {
        "subject": "You received a donation: ₹{amount}",
        "template": "donation_received",
    },
    EventType.DONATION_CONFIRMATION: {
        "subject": "Your donation to {ngo_name} was received",
        "template": "donation_confirmation",
    },
    EventType.TAX_RECEIPT_ISSUED: {
        "subject": "Your 80G tax certificate for your donation to {ngo_name}",
        "template": "tax_receipt_issued",
    },
    EventType.CAMPAIGN_PUBLISHED: {
        "subject": "{campaign_title} is now live for donations",
        "template": "campaign_published",
    },
    EventType.MILESTONE_REACHED: {
        "subject": "{campaign_title} reached {milestone_title}",
        "template": "milestone_reached",
    },
    EventType.NGO_VERIFIED: {
        "subject": "Your organization is now verified on Imparency",
        "template": "ngo_verified",
    },
    EventType.DONOR_DIGEST: {
        "subject": "Your weekly Imparency digest",
        "template": "donor_digest",
    },
}
