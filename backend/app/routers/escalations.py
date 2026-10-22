"""Admin endpoints for escalation management."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import User, ProposalEscalation, Proposal, Organization
from app.schemas import ProposalEscalationOut
from app.services.escalations import (
    check_and_create_escalations,
    resolve_escalation,
    send_admin_follow_up,
)

router = APIRouter(prefix="/admin/escalations", tags=["admin-escalations"])


@router.get("/pending", response_model=list[ProposalEscalationOut])
def get_pending_escalations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProposalEscalationOut]:
    """Get all pending escalations. Admin only."""
    if not user.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")

    escalations = db.scalars(
        select(ProposalEscalation)
        .where(ProposalEscalation.status == "PENDING")
        .order_by(ProposalEscalation.escalated_at.desc())
        .limit(100)
    ).all()

    return [
        ProposalEscalationOut(
            id=e.id,
            proposal_id=e.proposal_id,
            reason=e.reason,
            escalated_at=e.escalated_at,
            admin_notes=e.admin_notes,
            status=e.status,
            resolved_at=e.resolved_at,
        )
        for e in escalations
    ]


@router.post("/check-and-create")
def trigger_escalation_check(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Manually trigger escalation check.
    In production, this would be a scheduled task.
    Admin only.
    """
    if not user.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")

    result = check_and_create_escalations(db)
    return {
        "five_day_escalations": result["five_day"],
        "ten_day_escalations": result["ten_day"],
        "triggered_by": user.id,
    }


@router.get("/{escalation_id}", response_model=ProposalEscalationOut)
def get_escalation(
    escalation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProposalEscalationOut:
    """Get a specific escalation. Admin only."""
    if not user.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")

    escalation = db.get(ProposalEscalation, escalation_id)
    if not escalation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Escalation not found")

    return ProposalEscalationOut(
        id=escalation.id,
        proposal_id=escalation.proposal_id,
        reason=escalation.reason,
        escalated_at=escalation.escalated_at,
        admin_notes=escalation.admin_notes,
        status=escalation.status,
        resolved_at=escalation.resolved_at,
    )


@router.post("/{escalation_id}/resolve")
def resolve_escalation_endpoint(
    escalation_id: str,
    payload: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Resolve an escalation. Admin only."""
    if not user.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")

    escalation = db.get(ProposalEscalation, escalation_id)
    if not escalation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Escalation not found")

    resolve_escalation(db, escalation_id, payload.get("notes", ""))

    return {
        "escalation_id": escalation_id,
        "status": "RESOLVED",
        "resolved_by": user.id,
    }


@router.post("/{escalation_id}/send-follow-up")
def send_follow_up_message(
    escalation_id: str,
    payload: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Send follow-up message from admin to CSR or NGO.
    payload: {
        "recipient_type": "CSR" | "NGO",
        "message": "Your message here"
    }
    """
    if not user.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")

    escalation = db.get(ProposalEscalation, escalation_id)
    if not escalation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Escalation not found")

    send_admin_follow_up(
        db,
        escalation.proposal_id,
        user.id,
        payload.get("message", ""),
        payload.get("recipient_type", "CSR"),
    )

    return {
        "escalation_id": escalation_id,
        "message_sent": True,
        "sent_by": user.id,
    }


@router.get("/proposal/{proposal_id}/escalations", response_model=list[ProposalEscalationOut])
def get_proposal_escalations(
    proposal_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProposalEscalationOut]:
    """Get all escalations for a specific proposal. Admin only."""
    if not user.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")

    escalations = db.scalars(
        select(ProposalEscalation)
        .where(ProposalEscalation.proposal_id == proposal_id)
        .order_by(ProposalEscalation.escalated_at.desc())
    ).all()

    return [
        ProposalEscalationOut(
            id=e.id,
            proposal_id=e.proposal_id,
            reason=e.reason,
            escalated_at=e.escalated_at,
            admin_notes=e.admin_notes,
            status=e.status,
            resolved_at=e.resolved_at,
        )
        for e in escalations
    ]
