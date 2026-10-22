from tests.helpers import PASSWORD, auth, expire_sessions_for, login, register


def test_register_then_login_then_me(client):
    register(client, "ada@example.org", "Ada")
    token = login(client, "ada@example.org")
    r = client.get("/auth/me", headers=auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "ada@example.org"
    assert body["is_platform_admin"] is False


def test_email_is_normalised_case_insensitively(client):
    register(client, "Ada@Example.org")
    assert login(client, "ada@example.ORG")


def test_wrong_password_and_unknown_email_return_identical_error(client):
    register(client, "ada@example.org")
    wrong = client.post("/auth/login", json={"email": "ada@example.org", "password": "nope-nope-nope"})
    unknown = client.post("/auth/login", json={"email": "ghost@example.org", "password": "nope-nope-nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_duplicate_email_is_rejected_and_writes_no_second_audit_row(client):
    first = register(client, "ada@example.org")
    r = client.post("/auth/register", json={"email": "ADA@example.org", "password": PASSWORD, "full_name": "X"})
    assert r.status_code == 409
    from sqlalchemy import func, select
    from app.db import SessionLocal
    from app.models import AuditEvent

    with SessionLocal() as db:
        count = db.scalar(
            select(func.count()).select_from(AuditEvent).where(
                AuditEvent.action == "user.registered", AuditEvent.resource_id == first["id"]
            )
        )
    assert count == 1, "a failed registration must not leave an audit row behind"


def test_short_password_rejected(client):
    r = client.post("/auth/register", json={"email": "a@example.org", "password": "short", "full_name": "A"})
    assert r.status_code == 422


def test_logout_revokes_only_the_current_session(client):
    register(client, "ada@example.org")
    first = login(client, "ada@example.org")
    second = login(client, "ada@example.org")
    assert client.post("/auth/logout", headers=auth(first)).status_code == 204
    assert client.get("/auth/me", headers=auth(first)).status_code == 401
    assert client.get("/auth/me", headers=auth(second)).status_code == 200


def test_expired_session_is_rejected(client):
    register(client, "ada@example.org")
    token = login(client, "ada@example.org")
    expire_sessions_for("ada@example.org")
    assert client.get("/auth/me", headers=auth(token)).status_code == 401


def test_missing_or_garbage_token_rejected(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers=auth("not-a-real-token")).status_code == 401
