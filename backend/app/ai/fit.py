"""Candidate ranking for a CSR opportunity.

Follows the same contract as app.ai.assist: the numbers are deterministic, the model may
only rephrase them, and nothing here decides anything. The CSR still picks the shortlist.

  - Eligibility is a hard, deterministic gate: an NGO that is unverified, unpublished or
    missing a required compliance document cannot be a candidate at all. That mirrors the
    gate `app.domain.compliance` already enforces at proposal submission, so the CSR is
    never shown an NGO that would be refused three steps later.
  - The fit score is computed from rows in the database, never by a model. Same inputs,
    same score, every time.
  - The LLM pass, when a key is configured, rewrites the *explanation text only*. It is
    handed the score and may not change it. Any failure falls back to the computed wording.
"""

from dataclasses import dataclass, field

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.domain.compliance import approved_doc_types, missing_required_documents
from app.models import (
    DocumentType,
    NgoProfile,
    Opportunity,
    Organization,
    OrgType,
    ProfileStatus,
    VerificationStatus,
)

# Weights sum to 100. Sector and geography dominate because they are what a CSR filters on
# first; the compliance and track-record components break ties between equally aligned NGOs.
_W_SECTOR = 40
_W_GEOGRAPHY = 30
_W_COMPLIANCE = 15
_W_TRACK_RECORD = 15

MODEL_VERSION = "fit-rules-v1"


@dataclass
class Candidate:
    ngo_id: str
    ngo_name: str
    sectors: list[str]
    score: int
    explanation: str
    confidence: str
    sources: list[str] = field(default_factory=list)
    generated_by: str = "rules"


def _norm(values: list | None) -> set[str]:
    return {str(v).strip().lower() for v in (values or []) if str(v).strip()}


def _overlap_ratio(wanted: set[str], have: set[str]) -> float:
    """Share of what the opportunity asked for that this NGO covers."""
    if not wanted:
        # The opportunity named no constraint, so no NGO can be penalised on it.
        return 1.0
    if not have:
        return 0.0
    return len(wanted & have) / len(wanted)


def eligibility_reasons(
    db: Session, org: Organization, profile: NgoProfile | None, opp: Opportunity | None = None
) -> list[str]:
    """Deterministic hard gate. An empty list means this NGO may be shortlisted."""
    reasons: list[str] = []
    if org.org_type is not OrgType.NGO:
        reasons.append("Not an NGO organisation")
    if org.verification_status is not VerificationStatus.APPROVED:
        reasons.append("Organisation is not verified")
    if profile is None:
        reasons.append("No NGO profile submitted")
    elif profile.status is not ProfileStatus.PUBLISHED:
        reasons.append("NGO profile is not published")
    missing = missing_required_documents(db, org.id)
    if missing:
        names = ", ".join(sorted(d.value for d in missing))
        reasons.append(f"Missing approved compliance documents: {names}")
    if opp is not None and opp.fcra_required and DocumentType.FCRA not in approved_doc_types(db, org.id):
        reasons.append("This opportunity requires FCRA registration, which is not approved for this NGO")
    return reasons


def _score_candidate(
    db: Session, opp: Opportunity, org: Organization, profile: NgoProfile
) -> Candidate:
    wanted_sectors, have_sectors = _norm(opp.sectors), _norm(profile.sectors)
    wanted_geos, have_geos = _norm(opp.geographies), _norm(profile.geographies)

    sector_ratio = _overlap_ratio(wanted_sectors, have_sectors)
    geo_ratio = _overlap_ratio(wanted_geos, have_geos)

    # Compliance is already a pass/fail gate above; here the optional FCRA document and a
    # complete profile act as a positive differentiator rather than a blocker.
    compliance_points = _W_COMPLIANCE
    profile_gaps: list[str] = []
    for label, value in (
        ("mission", profile.mission),
        ("about", profile.about),
        ("registration number", profile.registration_number),
    ):
        if not (value or "").strip():
            profile_gaps.append(label)
    if profile_gaps:
        compliance_points -= min(_W_COMPLIANCE, 5 * len(profile_gaps))

    # Track record: years of operation, capped so an old NGO cannot outrank an aligned one.
    years = 0
    if profile.founded_year:
        from datetime import date as _date

        years = max(0, _date.today().year - profile.founded_year)
    track_points = min(_W_TRACK_RECORD, years)

    score = round(
        _W_SECTOR * sector_ratio
        + _W_GEOGRAPHY * geo_ratio
        + compliance_points
        + track_points
    )
    score = max(0, min(100, score))

    matched_sectors = sorted(wanted_sectors & have_sectors)
    matched_geos = sorted(wanted_geos & have_geos)
    parts = []
    parts.append(
        f"Sectors: {', '.join(matched_sectors)} match"
        if matched_sectors
        else ("Sectors: no overlap with the requested sectors" if wanted_sectors else "Sectors: unrestricted")
    )
    parts.append(
        f"Geography: works in {', '.join(matched_geos)}"
        if matched_geos
        else ("Geography: does not list the requested area" if wanted_geos else "Geography: unrestricted")
    )
    parts.append("Compliance: all required documents approved")
    if opp.fcra_required:
        # Reaching this point already means the FCRA gate in eligibility_reasons passed.
        parts.append("FCRA: registered, as this opportunity requires")
    parts.append(f"Operating for {years} years" if years else "Founding year not stated")
    if profile_gaps:
        parts.append(f"Profile incomplete: {', '.join(profile_gaps)}")

    # Confidence reflects how much evidence the score rests on, not how good the NGO is.
    evidence = sum(1 for x in (have_sectors, have_geos, profile.founded_year) if x)
    confidence = "HIGH" if evidence == 3 else "MEDIUM" if evidence == 2 else "LOW"

    return Candidate(
        ngo_id=org.id,
        ngo_name=org.name,
        sectors=list(profile.sectors or []),
        score=score,
        explanation=". ".join(parts) + ".",
        confidence=confidence,
        sources=[f"organization:{org.id}", f"ngo_profile:{profile.id}", f"opportunity:{opp.id}"],
    )


def _llm_explanations(opp: Opportunity, candidates: list[Candidate]) -> bool:
    """Rephrase each explanation for a human reader. Returns True if anything was rewritten.

    The model is given the computed score and told it may not change it; only the prose is
    replaced. Any failure leaves the deterministic wording untouched.
    """
    if not settings.llm_api_key or not candidates:
        return False

    listing = "\n".join(
        f"{i + 1}. {c.ngo_name} — score {c.score}/100 — facts: {c.explanation}"
        for i, c in enumerate(candidates)
    )
    prompt = (
        "You are helping a corporate social-responsibility officer read a ranked list of "
        "NGOs for a funding opportunity. For each NGO, rewrite the supplied facts as one "
        "short sentence explaining why it ranks where it does.\n"
        "Rules: do not change any score. Do not invent any fact that is not listed. Do not "
        "recommend who to pick. Return exactly one line per NGO, in the same order, "
        "formatted as '<number>. <sentence>'.\n\n"
        f"Opportunity: {opp.title}\n"
        f"Requested sectors: {', '.join(opp.sectors) or 'any'}\n"
        f"Requested geographies: {', '.join(opp.geographies) or 'any'}\n\n"
        f"NGOs:\n{listing}\n"
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
                "max_tokens": 800,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=15.0,
        )
        response.raise_for_status()
        text = response.json()["content"][0]["text"].strip()
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        parsed: dict[int, str] = {}
        for line in lines:
            head, _, body = line.partition(".")
            if head.strip().isdigit() and body.strip():
                parsed[int(head.strip()) - 1] = body.strip()
        if len(parsed) != len(candidates):
            # A partial answer would silently mix two voices across the list; take none.
            return False
        for i, c in enumerate(candidates):
            c.explanation = parsed[i]
            c.generated_by = f"llm:{settings.llm_model}"
        return True
    except Exception:
        return False


def rank_candidates(db: Session, opp: Opportunity) -> tuple[list[Candidate], list[tuple[str, list[str]]]]:
    """Return (ranked eligible candidates, [(ngo_id, blocking reasons)] for the rest)."""
    orgs = db.scalars(select(Organization).where(Organization.org_type == OrgType.NGO)).all()

    candidates: list[Candidate] = []
    ineligible: list[tuple[str, list[str]]] = []
    for org in orgs:
        profile = db.scalar(select(NgoProfile).where(NgoProfile.org_id == org.id))
        reasons = eligibility_reasons(db, org, profile, opp)
        if reasons or profile is None:
            ineligible.append((org.id, reasons))
            continue
        candidates.append(_score_candidate(db, opp, org, profile))

    candidates.sort(key=lambda c: (-c.score, c.ngo_name))
    _llm_explanations(opp, candidates)
    return candidates, ineligible
