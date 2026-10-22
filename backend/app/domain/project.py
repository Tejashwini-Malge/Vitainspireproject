"""Submission gate for NGO projects. Deterministic: lists every blocker, not just the first.

Clearing these blockers only gets a project to PENDING_REVIEW; an admin decision is
still required before it is PUBLISHED (see app/routers/admin.py).
"""

from app.models import OrgType, Project, VerificationStatus


def submission_blockers(org_type: OrgType, verification: VerificationStatus, project: Project) -> list[str]:
    blockers: list[str] = []
    if org_type is not OrgType.NGO:
        blockers.append("Only NGO organizations can publish projects")
    if verification is not VerificationStatus.APPROVED:
        blockers.append("The organization must be verified by Imparency before a project can be submitted for review")
    if not project.title.strip():
        blockers.append("Add a title")
    if not project.summary.strip():
        blockers.append("Add a short summary")
    return blockers
