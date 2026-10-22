"""Operator commands. Run from backend/: python -m app.cli <command>. Schema: alembic upgrade head."""

import argparse
import sys

from sqlalchemy import select

from app import models  # noqa: F401
from app.audit import record_audit
from app.db import SessionLocal


def grant_platform_admin(email: str) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(models.User).where(models.User.email == email.lower()))
        if user is None:
            sys.exit(f"No user with email {email}")
        user.is_platform_admin = True
        record_audit(
            db,
            action="platform.admin_granted",
            resource_type="user",
            resource_id=user.id,
            actor_user_id=None,
            details={"granted_by": "operator_cli"},
        )
        db.commit()
        print(f"granted platform admin to {email}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    grant = sub.add_parser("grant-platform-admin")
    grant.add_argument("email")
    args = parser.parse_args()
    if args.cmd == "grant-platform-admin":
        grant_platform_admin(args.email)
