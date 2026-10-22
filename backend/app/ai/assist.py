"""Verification-assist drafting.

This produces a *proposal* for the human reviewer: a plain-language summary and a list of
flags, each citing where it came from. It never decides anything -- app.domain.review and
app.routers.admin own the actual verification decision, and nothing here writes to the
database or changes organization state.

Two code paths:
  - Deterministic (default): built entirely from rows already in the database. No network
    call, no model, always available, always the same for the same input.
  - LLM-assisted (only when VITA_LLM_API_KEY is set): asks a model to phrase the same facts
    more usefully for a reviewer. If the call fails for any reason, this falls back to the
    deterministic draft rather than raising -- an admin should never be blocked from the
    queue by an optional convenience feature.
"""

from dataclasses import dataclass, field

import httpx

from app.config import settings
from app.models import Document, DocumentType, NgoProfile, Organization, ReviewStatus

_REQUIRED_NGO_DOC_TYPES = (DocumentType.PAN, DocumentType.REGISTRATION)


@dataclass
class AssistDraft:
    summary: str
    flags: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    generated_by: str = "rules"


def _deterministic_draft(org: Organization, profile: NgoProfile | None, documents: list[Document]) -> AssistDraft:
    sources: list[str] = [f"organization:{org.id}"]
    flags: list[str] = []

    if profile is not None:
        sources.append(f"ngo_profile:{profile.id}")
        parts = [f"Mission: {profile.mission.strip() or '(not provided)'}."]
        if profile.sectors:
            parts.append(f"Sectors: {', '.join(profile.sectors)}.")
        if profile.geographies:
            parts.append(f"Operates in: {', '.join(profile.geographies)}.")
        summary = " ".join(parts)
    else:
        summary = f"{org.name} has not submitted a profile yet."
        flags.append("No profile submitted")

    present_types = {d.doc_type for d in documents}
    for doc in documents:
        sources.append(f"document:{doc.id}:{doc.doc_type.value}")
    for required in _REQUIRED_NGO_DOC_TYPES:
        if required not in present_types:
            flags.append(f"Missing {required.value} document")
    pending = [d for d in documents if d.review_status == ReviewStatus.PENDING_REVIEW]
    if pending:
        flags.append(f"{len(pending)} document(s) awaiting review")
    if not documents:
        flags.append("No compliance documents uploaded")

    return AssistDraft(summary=summary, flags=flags, sources=sources, generated_by="rules")


def _llm_draft(org: Organization, base: AssistDraft) -> AssistDraft | None:
    """Ask a model to phrase `base` more usefully. Returns None on any failure."""
    if not settings.llm_api_key:
        return None
    prompt = (
        "You are drafting a note for a human reviewer who verifies nonprofit organizations. "
        "Rewrite the following facts as a short, neutral summary for the reviewer. "
        "Do not add any fact that is not listed below. Do not make a verification recommendation.\n\n"
        f"Organization: {org.name}\n"
        f"Facts: {base.summary}\n"
        f"Flags already identified: {'; '.join(base.flags) if base.flags else 'none'}\n"
    )
    try:
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.llm_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": settings.llm_model,
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=10.0,
        )
        response.raise_for_status()
        text = response.json()["content"][0]["text"].strip()
        if not text:
            return None
        return AssistDraft(summary=text, flags=base.flags, sources=base.sources, generated_by=f"llm:{settings.llm_model}")
    except Exception:
        # Any network, auth, schema or timeout failure: the reviewer gets the deterministic
        # draft instead. This is a convenience layer, not a dependency.
        return None


def draft_verification_assist(org: Organization, profile: NgoProfile | None, documents: list[Document]) -> AssistDraft:
    base = _deterministic_draft(org, profile, documents)
    return _llm_draft(org, base) or base
