"""Onboarding progress for a CSR or NGO workspace. Deterministic: every step is computed from
existing org data, same spirit as publish_blockers -- no judgment calls, no LLM involved.
"""

from dataclasses import dataclass

from app.models import NgoProfile, Opportunity, Organization, Project, ProjectStatus, Proposal


@dataclass
class OnboardingStep:
    key: str
    label: str
    done: bool
    cta_href: str


def compute_ngo_steps(
    org: Organization,
    profile: NgoProfile | None,
    has_document: bool,
    has_approved_document: bool,
    projects: list[Project],
) -> list[OnboardingStep]:
    profile_started = profile is not None and bool(profile.mission.strip()) and bool(profile.sectors) and bool(profile.geographies)
    profile_published = profile is not None and profile.status.value == "PUBLISHED"
    has_published_project = any(p.status is ProjectStatus.PUBLISHED for p in projects)

    return [
        OnboardingStep(
            key="profile_started",
            label="Add your mission, sectors and geographies",
            done=profile_started,
            cta_href=f"/orgs/{org.id}/profile",
        ),
        OnboardingStep(
            key="document_uploaded",
            label="Upload a compliance document (registration, 80G, FCRA, etc.)",
            done=has_document,
            cta_href=f"/orgs/{org.id}/documents",
        ),
        OnboardingStep(
            key="document_approved",
            label="Get your compliance document approved by the Imparency team",
            done=has_approved_document,
            cta_href=f"/orgs/{org.id}/documents",
        ),
        OnboardingStep(
            key="profile_published",
            label="Publish your public profile",
            done=profile_published,
            cta_href=f"/orgs/{org.id}/profile",
        ),
        OnboardingStep(
            key="project_created",
            label="Create your first project",
            done=len(projects) > 0,
            cta_href=f"/orgs/{org.id}/projects",
        ),
        OnboardingStep(
            key="project_published",
            label="Get a project published to the public feed",
            done=has_published_project,
            cta_href=f"/orgs/{org.id}/projects",
        ),
    ]


def compute_csr_steps(
    org: Organization,
    opportunities: list[Opportunity],
    proposals: list[Proposal],
) -> list[OnboardingStep]:
    org_verified = org.verification_status.value == "APPROVED"
    has_published_opportunity = any(o.status == "PUBLISHED" for o in opportunities)
    has_received_proposal = len(proposals) > 0
    has_responded_to_proposal = any(p.status != "SUBMITTED" for p in proposals)

    return [
        OnboardingStep(
            key="org_verified",
            label="Get your organization verified by the Imparency team",
            done=org_verified,
            cta_href=f"/orgs/{org.id}",
        ),
        OnboardingStep(
            key="opportunity_created",
            label="Post your first funding opportunity",
            done=len(opportunities) > 0,
            cta_href="/csr/opportunities/create",
        ),
        OnboardingStep(
            key="opportunity_published",
            label="Publish the opportunity so NGOs can apply",
            done=has_published_opportunity,
            cta_href="/csr/opportunities",
        ),
        OnboardingStep(
            key="proposal_received",
            label="Receive your first proposal",
            done=has_received_proposal,
            cta_href="/csr/proposals",
        ),
        OnboardingStep(
            key="proposal_reviewed",
            label="Respond to a proposal",
            done=has_responded_to_proposal,
            cta_href="/csr/proposals",
        ),
    ]


def next_step(steps: list[OnboardingStep]) -> OnboardingStep | None:
    return next((s for s in steps if not s.done), None)


def completion_pct(steps: list[OnboardingStep]) -> int:
    if not steps:
        return 100
    done = sum(1 for s in steps if s.done)
    return round(done / len(steps) * 100)
