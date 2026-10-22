from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import get_current_user, require_membership
from app.domain.compliance import require_compliance_documents
from app.domain.project import submission_blockers
from app.models import Campaign, Document, DocumentReviewDecision, DocumentType, Organization, OrgType, Project, ProjectStatus, ReviewStatus, Role, User
from app.schemas import ProjectIn, ProjectOut

router = APIRouter(prefix="/orgs/{org_id}/projects", tags=["projects"])

MANAGE = frozenset({Role.OWNER, Role.ADMIN})


def _project_out(p: Project) -> ProjectOut:
    return ProjectOut(
        id=p.id,
        org_id=p.org_id,
        title=p.title,
        summary=p.summary,
        description=p.description,
        campaign_id=p.campaign_id,
        status=p.status,
        review_feedback=p.review_feedback,
        published_at=p.published_at,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _load_org(db: Session, org_id: str) -> Organization:
    org = db.get(Organization, org_id)
    if org is None:  # Membership was checked first, so this means the data is inconsistent. Fail loudly.
        raise RuntimeError(f"Membership references missing organization {org_id}")
    return org


def _validate_campaign(db: Session, org_id: str, campaign_id: str | None) -> None:
    """A project may only reference a campaign owned by the same organisation.

    Returns 404 rather than 403 for someone else's campaign: whether that id exists
    is not this organisation's business.
    """
    if campaign_id is None:
        return
    campaign = db.get(Campaign, campaign_id)
    if campaign is None or campaign.ngo_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")


def _project_or_404(db: Session, org_id: str, project_id: str) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id, Project.org_id == org_id))
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(org_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ProjectOut]:
    require_membership(db, user, org_id)
    projects = db.scalars(select(Project).where(Project.org_id == org_id).order_by(Project.created_at.desc())).all()
    return [_project_out(p) for p in projects]


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    org_id: str,
    payload: ProjectIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectOut:
    require_membership(db, user, org_id, allowed_roles=MANAGE)
    org = _load_org(db, org_id)
    if org.org_type is not OrgType.NGO:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Projects are available for NGO organizations")
    _validate_campaign(db, org_id, payload.campaign_id)
    project = Project(
        org_id=org_id,
        title=payload.title,
        summary=payload.summary,
        description=payload.description,
        campaign_id=payload.campaign_id,
    )
    db.add(project)
    db.flush()
    record_audit(
        db,
        action="project.created",
        resource_type="project",
        resource_id=project.id,
        actor_user_id=user.id,
        org_id=org_id,
    )
    db.commit()
    return _project_out(project)


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(
    org_id: str,
    project_id: str,
    payload: ProjectIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectOut:
    require_membership(db, user, org_id, allowed_roles=MANAGE)
    project = _project_or_404(db, org_id, project_id)
    if project.status not in (ProjectStatus.DRAFT, ProjectStatus.CHANGES_REQUESTED):
        raise HTTPException(status.HTTP_409_CONFLICT, f"A project that is {project.status.value} cannot be edited directly")
    _validate_campaign(db, org_id, payload.campaign_id)
    changed = []
    for field, value in {
        "title": payload.title,
        "summary": payload.summary,
        "description": payload.description,
        "campaign_id": payload.campaign_id,
    }.items():
        if getattr(project, field) != value:
            setattr(project, field, value)
            changed.append(field)
    project.updated_at = datetime.now(UTC)
    db.flush()
    record_audit(
        db,
        action="project.updated",
        resource_type="project",
        resource_id=project.id,
        actor_user_id=user.id,
        org_id=org_id,
        details={"changed_fields": changed},
    )
    db.commit()
    return _project_out(project)


@router.post("/{project_id}/submit-for-review", response_model=ProjectOut)
def submit_project_for_review(
    org_id: str,
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectOut:
    """Send a project to the admin review queue. Admin approval is required before it goes live
    (see POST /admin/projects/{project_id}/decisions) -- an NGO can no longer publish directly."""
    require_membership(db, user, org_id, allowed_roles=MANAGE)
    org = _load_org(db, org_id)
    project = _project_or_404(db, org_id, project_id)

    if project.status not in (ProjectStatus.DRAFT, ProjectStatus.CHANGES_REQUESTED):
        raise HTTPException(status.HTTP_409_CONFLICT, f"A project that is {project.status.value} cannot be submitted again")

    require_compliance_documents(db, org_id, "submitting a project for review")

    blockers = submission_blockers(org.org_type, org.verification_status, project)
    if blockers:
        raise HTTPException(status.HTTP_409_CONFLICT, {"message": "The project cannot be submitted yet", "blockers": blockers})

    project.status = ProjectStatus.PENDING_REVIEW
    project.review_feedback = None
    db.flush()
    record_audit(
        db,
        action="project.submitted_for_review",
        resource_type="project",
        resource_id=project.id,
        actor_user_id=user.id,
        org_id=org_id,
    )
    db.commit()
    return _project_out(project)


@router.post("/{project_id}/unpublish", response_model=ProjectOut)
def unpublish_project(
    org_id: str,
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectOut:
    """Withdraw a project: takes a PUBLISHED project down, or withdraws one still pending review.

    Going live again requires a fresh admin approval, same as any other submission.
    """
    require_membership(db, user, org_id, allowed_roles=MANAGE)
    project = _project_or_404(db, org_id, project_id)
    if project.status is ProjectStatus.DRAFT:
        return _project_out(project)
    project.status = ProjectStatus.DRAFT
    project.published_at = None
    db.flush()
    record_audit(
        db,
        action="project.unpublished",
        resource_type="project",
        resource_id=project.id,
        actor_user_id=user.id,
        org_id=org_id,
    )
    db.commit()
    return _project_out(project)
