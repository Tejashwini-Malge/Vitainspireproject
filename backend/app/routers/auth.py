from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.models import SessionRecord, User
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.security import hash_password, hash_token, new_session_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_platform_admin=user.is_platform_admin,
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> UserOut:
    email = payload.email.lower()
    user = User(email=email, password_hash=hash_password(payload.password), full_name=payload.full_name)
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        # Same response shape either way is not required here; the email is
        # disclosed only to the person registering it, so a clear 409 is acceptable.
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    record_audit(db, action="user.registered", resource_type="user", resource_id=user.id, actor_user_id=user.id)
    db.commit()
    return _user_out(user)


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(user.password_hash, payload.password):
        # Same message for unknown email and wrong password, to avoid account enumeration.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect")
    token = new_session_token()
    db.add(
        SessionRecord(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=datetime.now(UTC) + timedelta(hours=settings.session_ttl_hours),
        )
    )
    record_audit(db, action="user.logged_in", resource_type="user", resource_id=user.id, actor_user_id=user.id)
    db.commit()
    return TokenOut(access_token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    authorization: str | None = Header(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    # The session that was just validated is revoked; other sessions for the user stay live.
    token_hash = hash_token(_bearer(authorization))
    record = db.scalar(select(SessionRecord).where(SessionRecord.token_hash == token_hash))
    if record is not None and record.revoked_at is None:
        record.revoked_at = datetime.now(UTC)
    record_audit(db, action="user.logged_out", resource_type="user", resource_id=user.id, actor_user_id=user.id)
    db.commit()


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return _user_out(user)


def _bearer(authorization: str | None) -> str:
    return (authorization or "").removeprefix("Bearer ").strip()
