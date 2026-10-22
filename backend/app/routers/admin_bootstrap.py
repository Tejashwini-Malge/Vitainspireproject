"""One-time bootstrap for the very first platform admin.

Every other admin-granting path requires direct database access (see app.cli), which is a
deliberate trust boundary: admin power requires infrastructure access, not an app account.
This endpoint exists for hosts that give an operator infrastructure-level control (they can set
environment variables) but no database shell (e.g. Render's free tier) -- it is gated by a
token that only exists if an operator deliberately set VITA_ADMIN_BOOTSTRAP_TOKEN in the host's
environment, never through the app itself, and it is never set in this repository.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.config import settings
from app.db import get_db
from app.models import User

router = APIRouter(prefix="/admin", tags=["admin"])


class BootstrapAdminIn(BaseModel):
    email: str
    token: str


@router.post("/bootstrap", status_code=status.HTTP_200_OK)
def bootstrap_platform_admin(payload: BootstrapAdminIn, db: Session = Depends(get_db)) -> dict:
    if not settings.admin_bootstrap_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bootstrap is not enabled on this deployment")
    if not secrets.compare_digest(payload.token, settings.admin_bootstrap_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid bootstrap token")

    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No user with email {payload.email}")

    user.is_platform_admin = True
    record_audit(
        db,
        action="platform.admin_granted",
        resource_type="user",
        resource_id=user.id,
        actor_user_id=None,
        details={"granted_by": "bootstrap_token"},
    )
    db.commit()
    return {"granted": True, "email": user.email}
