"""Deterministic donation-target validation. No AI output reaches this code path."""

from app.models import Organization, OrgType, Project, ProjectStatus, ProfileStatus, VerificationStatus


class DonationError(ValueError):
    """Raised when a donation target is not valid. The message is shown to the donor."""


MAX_AMOUNT_MINOR = 10_00_00_000_00  # 1 crore rupees in paise; a sanity ceiling, not a business limit.


def validate_target(
    org: Organization | None,
    profile_status: ProfileStatus | None,
    project: Project | None,
    amount_minor: int,
) -> None:
    if org is None or org.org_type is not OrgType.NGO:
        raise DonationError("This NGO is not available for donations")
    if org.verification_status is not VerificationStatus.APPROVED:
        raise DonationError("This NGO is not yet verified")
    if profile_status is not ProfileStatus.PUBLISHED:
        raise DonationError("This NGO has not published a public profile yet")
    if project is not None:
        if project.org_id != org.id:
            raise DonationError("This project does not belong to the selected NGO")
        if project.status is not ProjectStatus.PUBLISHED:
            raise DonationError("This project is not currently open for donations")
    if amount_minor <= 0:
        raise DonationError("The donation amount must be greater than zero")
    if amount_minor > MAX_AMOUNT_MINOR:
        raise DonationError("The donation amount is larger than this form accepts")
