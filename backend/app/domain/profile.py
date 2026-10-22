"""Publication gate for NGO profiles. Deterministic: lists every blocker, not just the first."""

from app.models import NgoProfile, OrgType, VerificationStatus


def publish_blockers(org_type: OrgType, verification: VerificationStatus, profile: NgoProfile | None) -> list[str]:
    blockers: list[str] = []
    if org_type is not OrgType.NGO:
        blockers.append("Only NGO organizations can publish a public profile")
    if verification is not VerificationStatus.APPROVED:
        blockers.append("The organization must be verified by Imparency before its profile can be published")
    if profile is None or not profile.mission.strip():
        blockers.append("Add a mission statement")
    if profile is None or not profile.sectors:
        blockers.append("Add at least one sector of work")
    if profile is None or not profile.geographies:
        blockers.append("Add at least one geography where you work")
    return blockers
