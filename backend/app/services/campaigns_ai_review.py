"""AI-assisted campaign review for trustworthiness scoring."""

import json
from datetime import datetime, UTC

from sqlalchemy.orm import Session
from anthropic import Anthropic

from app.models import Campaign, CampaignReview, CampaignMilestone
from app.config import settings


def review_campaign(db: Session, campaign_id: str) -> dict:
    """
    Run AI analysis on a campaign for trustworthiness.
    Returns structured review with score, flags, and recommendation.
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        return {"error": "Campaign not found"}

    # Get milestones
    milestones = db.query(CampaignMilestone).filter(
        CampaignMilestone.campaign_id == campaign_id
    ).order_by(CampaignMilestone.sequence_num).all()

    # Build campaign summary for AI
    campaign_data = {
        "title": campaign.title,
        "mission": campaign.mission,
        "description": campaign.description,
        "beneficiary_count": campaign.beneficiary_count,
        "beneficiary_description": campaign.beneficiary_description,
        "impact_statement": campaign.impact_statement,
        "budget_total": campaign.budget_total,
        "currency": campaign.currency,
        "budget_breakdown": campaign.budget_breakdown or {},
        "duration_months": campaign.duration_months,
        "milestones": [
            {
                "sequence": m.sequence_num,
                "title": m.title,
                "target_date": m.target_date.isoformat(),
                "target_amount": m.target_amount,
            }
            for m in milestones
        ],
    }

    # Call Claude API for review
    try:
        client = Anthropic(api_key=settings.llm_api_key)

        prompt = _build_review_prompt(campaign_data)

        message = client.messages.create(
            model=settings.llm_model,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        response_text = message.content[0].text
        analysis = _parse_ai_response(response_text)

    except Exception as e:
        # Fallback to deterministic review if AI fails
        analysis = _deterministic_review(campaign_data)
        analysis["error"] = str(e)

    # Store review results
    review = db.query(CampaignReview).filter(CampaignReview.campaign_id == campaign_id).first()
    if review:
        review.ai_review_at = datetime.now(UTC)
        review.ai_model = settings.llm_model
        review.ai_analysis = analysis
        review.ai_flags = analysis.get("flags", [])
        review.ai_recommendation = analysis.get("recommendation", "NEEDS_MANUAL_REVIEW")
        review.trustworthiness_score = analysis.get("trustworthiness_score", 0)
        campaign.is_ai_reviewed = True
        campaign.ai_review_summary = analysis.get("summary", "")
        campaign.ai_flags = analysis.get("flag_keys", [])
        db.commit()

    return analysis


def _build_review_prompt(campaign_data: dict) -> str:
    """Build the prompt for Claude to review campaign trustworthiness."""
    return f"""You are an expert reviewer for NGO fundraising campaigns. Review this campaign for trustworthiness and feasibility.

Campaign Details:
Title: {campaign_data['title']}
Mission: {campaign_data['mission']}
Duration: {campaign_data['duration_months']} months
Budget: {campaign_data['currency']} {campaign_data['budget_total']:,}

Beneficiaries: {campaign_data['beneficiary_count'] or 'Not specified'} people
Description: {campaign_data['beneficiary_description'][:500]}...

Budget Breakdown: {json.dumps(campaign_data['budget_breakdown'])}

Impact: {campaign_data['impact_statement']}

Milestones ({len(campaign_data['milestones'])} total):
{_format_milestones(campaign_data['milestones'])}

Please evaluate this campaign on:
1. **Budget Reasonableness** - Is the budget realistic for the stated scope?
2. **Milestone Feasibility** - Are the milestones achievable in the stated timeframe?
3. **Content Quality** - Is the campaign clearly written and professionally presented?
4. **Specificity** - Are beneficiaries and impact clearly defined?
5. **Red Flags** - Any concerns about authenticity, transparency, or feasibility?

Respond in JSON format with:
{{
    "trustworthiness_score": <0-100>,
    "recommendation": "<APPROVE|NEEDS_CHANGES|REJECT>",
    "summary": "<2-3 sentence summary>",
    "flags": [
        {{"category": "<category>", "severity": "<low|medium|high>", "message": "<specific message>"}},
        ...
    ],
    "strengths": ["<strength1>", "<strength2>", ...],
    "concerns": ["<concern1>", "<concern2>", ...]
}}

Ensure valid JSON output only."""


def _format_milestones(milestones: list) -> str:
    """Format milestones for prompt."""
    lines = []
    for m in milestones:
        lines.append(
            f"  {m['sequence']}. {m['title']} (Target: {m['target_amount']:,}, Date: {m['target_date']})"
        )
    return "\n".join(lines)


def _parse_ai_response(response_text: str) -> dict:
    """Extract JSON from AI response."""
    try:
        # Try to extract JSON from response
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = response_text[start:end]
            data = json.loads(json_str)

            # Ensure required fields
            data.setdefault("trustworthiness_score", 50)
            data.setdefault("recommendation", "NEEDS_MANUAL_REVIEW")
            data.setdefault("summary", "AI review completed")
            data.setdefault("flags", [])
            data.setdefault("strengths", [])
            data.setdefault("concerns", [])

            # Extract flag keys for storage
            data["flag_keys"] = [f"{f.get('category', 'unknown')}:{f.get('severity', 'unknown')}"
                                 for f in data.get("flags", [])]

            return data
    except json.JSONDecodeError:
        pass

    return _deterministic_review({})


def _deterministic_review(campaign_data: dict) -> dict:
    """Fallback deterministic review if AI fails."""
    flags = []
    score = 75

    # Check budget
    if campaign_data.get("budget_total", 0) > 10000000:  # > 1 crore
        flags.append({
            "category": "high_budget",
            "severity": "medium",
            "message": "Budget exceeds typical campaign range. Verify feasibility."
        })
        score -= 10

    # Check milestone count
    milestones = campaign_data.get("milestones", [])
    if len(milestones) < 2:
        flags.append({
            "category": "insufficient_milestones",
            "severity": "medium",
            "message": "Campaign should have at least 2 milestones for tracking progress."
        })
        score -= 5

    # Check beneficiary specificity
    beneficiary_desc = campaign_data.get("beneficiary_description", "")
    if len(beneficiary_desc) < 50:
        flags.append({
            "category": "vague_beneficiaries",
            "severity": "low",
            "message": "Beneficiary description is too brief. Provide more context."
        })
        score -= 5

    return {
        "trustworthiness_score": max(0, min(100, score)),
        "recommendation": "APPROVE" if score > 60 else "NEEDS_CHANGES",
        "summary": "Deterministic review completed. AI analysis unavailable.",
        "flags": flags,
        "strengths": ["Campaign structure is present"],
        "concerns": [] if not flags else ["Address the flags above"],
        "flag_keys": [f"{f['category']}:{f['severity']}" for f in flags],
    }
