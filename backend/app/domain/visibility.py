"""The public-visibility gate, shared by every public listing.

An NGO is visible publicly only once Imparency has verified it and it has chosen to publish
its profile. One definition, reused everywhere, so no listing can drift from this rule.
"""

from app.models import NgoProfile, Organization, OrgType, ProfileStatus, VerificationStatus

PUBLIC_NGO_FILTER = (
    Organization.org_type == OrgType.NGO,
    Organization.verification_status == VerificationStatus.APPROVED,
    NgoProfile.status == ProfileStatus.PUBLISHED,
)
