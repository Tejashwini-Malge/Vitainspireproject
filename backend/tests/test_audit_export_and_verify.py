"""Audit export and hash-chain verification (ADM-017, NEG-013).

Every row in audit_events already goes through record_audit(), which now chains each row
to the one before it (seq order, not wall-clock) with a sha256 hash covering both the
row's own content and the previous row's hash. GET /audit/export makes the trail
retrievable; GET /audit/verify recomputes the chain and reports the first break, if any.

The append-only trigger (migration 0002) blocks UPDATE/DELETE outright, so "tampering" here
is simulated the only way that is actually possible without superuser access: INSERTing a
row directly (bypassing record_audit) with a prev_hash/row_hash that does not fit the chain.
"""

import hashlib

from sqlalchemy import select

from app.audit import _row_hash
from app.db import SessionLocal
from app.models import AuditEvent
from tests.helpers import auth, login, make_platform_admin, user_token


def _admin(client) -> str:
    user_token(client, "ops@platform.org")
    make_platform_admin("ops@platform.org")
    return login(client, "ops@platform.org")


def _pending_org(client, owner_token) -> str:
    return client.post("/orgs", json={"name": "Shanti Trust", "org_type": "NGO"}, headers=auth(owner_token)).json()["id"]


def test_export_is_admin_only(client):
    owner = user_token(client, "owner@ngo.org")
    assert client.get("/admin/audit/export", headers=auth(owner)).status_code == 403


def test_export_returns_rows_with_hash_chain_fields(client):
    owner = user_token(client, "owner@ngo.org")
    org_id = _pending_org(client, owner)
    admin = _admin(client)
    client.post(f"/admin/organizations/{org_id}/verification", json={"decision": "APPROVED"}, headers=auth(admin))

    rows = client.get(f"/admin/audit/export?resource_type=organization&org_id={org_id}", headers=auth(admin)).json()
    assert len(rows) >= 1
    row = next(r for r in rows if r["action"] == "org.verification_decided")
    assert row["row_hash"] is not None
    assert isinstance(row["seq"], int)
    # seq strictly increases in export order
    assert all(rows[i]["seq"] < rows[i + 1]["seq"] for i in range(len(rows) - 1))


def test_export_filters_by_action_and_resource_type(client):
    owner = user_token(client, "owner@ngo.org")
    org_id = _pending_org(client, owner)
    admin = _admin(client)
    client.post(f"/admin/organizations/{org_id}/verification", json={"decision": "APPROVED"}, headers=auth(admin))

    rows = client.get(
        f"/admin/audit/export?action=org.verification_decided&resource_type=organization", headers=auth(admin)
    ).json()
    assert len(rows) >= 1
    assert all(r["action"] == "org.verification_decided" for r in rows)
    assert all(r["resource_type"] == "organization" for r in rows)


def test_export_rejects_an_out_of_range_limit(client):
    admin = _admin(client)
    assert client.get("/admin/audit/export?limit=0", headers=auth(admin)).status_code == 422
    assert client.get("/admin/audit/export?limit=5001", headers=auth(admin)).status_code == 422


def test_verify_is_admin_only(client):
    owner = user_token(client, "owner@ngo.org")
    assert client.get("/admin/audit/verify", headers=auth(owner)).status_code == 403


def test_verify_reports_the_chain_valid_after_several_actions(client):
    owner = user_token(client, "owner@ngo.org")
    with SessionLocal() as db:
        pre_existing_seq = db.scalar(select(AuditEvent.seq).order_by(AuditEvent.seq.desc()).limit(1)) or 0

    org_id = _pending_org(client, owner)
    admin = _admin(client)
    client.post(f"/admin/organizations/{org_id}/verification", json={"decision": "APPROVED"}, headers=auth(admin))
    client.post(f"/admin/organizations/{org_id}/request-review", json={"reason": "renewal"}, headers=auth(admin))
    client.post(f"/admin/organizations/{org_id}/dismiss-review", headers=auth(admin))

    # Scoped so this test does not depend on no other test in this file having injected a
    # deliberately-broken row earlier (audit_events is never truncated between tests).
    result = client.get(f"/admin/audit/verify?since_seq={pre_existing_seq + 1}", headers=auth(admin)).json()
    assert result["valid"] is True
    assert result["first_broken_seq"] is None
    assert result["checked"] >= 3


def test_verify_detects_a_row_with_a_forged_prev_hash(client):
    """Simulates a write that bypassed record_audit(): a row claiming a prev_hash that
    does not match the actual previous row's row_hash."""
    owner = user_token(client, "owner@ngo.org")
    org_id = _pending_org(client, owner)
    admin = _admin(client)
    client.post(f"/admin/organizations/{org_id}/verification", json={"decision": "APPROVED"}, headers=auth(admin))

    with SessionLocal() as db:
        last = db.scalar(select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(1))
        from datetime import UTC, datetime
        forged = AuditEvent(
            occurred_at=datetime.now(UTC), action="org.verification_decided", resource_type="organization",
            resource_id=org_id, actor_user_id=None, org_id=org_id, details={}, correlation_id=None,
            prev_hash="0" * 64,  # wrong -- does not match `last.row_hash`
            row_hash=hashlib.sha256(b"doesn't matter, prev_hash check fails first").hexdigest(),
        )
        db.add(forged)
        db.commit()
        forged_seq = forged.seq
        anchor_seq = last.seq

    # audit_events is never truncated between tests (it is append-only by design), so
    # scope the check to this test's own window -- otherwise an earlier test in this file
    # that injected its own broken row would be reported first instead.
    result = client.get(f"/admin/audit/verify?since_seq={anchor_seq}", headers=auth(admin)).json()
    assert result["valid"] is False
    assert result["first_broken_seq"] == forged_seq
    assert "prev_hash" in result["reason"]


def test_verify_detects_a_row_whose_content_was_altered_after_writing(client):
    """A row whose prev_hash correctly chains, but whose row_hash does not match its own
    (altered) content -- simulating an edit that bypassed the append-only trigger."""
    owner = user_token(client, "owner@ngo.org")
    org_id = _pending_org(client, owner)
    admin = _admin(client)
    client.post(f"/admin/organizations/{org_id}/verification", json={"decision": "APPROVED"}, headers=auth(admin))

    with SessionLocal() as db:
        last = db.scalar(select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(1))
        from datetime import UTC, datetime
        occurred_at = datetime.now(UTC)
        correct_hash = _row_hash(
            occurred_at=occurred_at, action="org.verification_decided", resource_type="organization",
            resource_id=org_id, actor_user_id=None, org_id=org_id, details={"note": "original"},
            correlation_id_value=None, prev_hash=last.row_hash,
        )
        altered = AuditEvent(
            occurred_at=occurred_at, action="org.verification_decided", resource_type="organization",
            resource_id=org_id, actor_user_id=None, org_id=org_id,
            details={"note": "tampered after the hash was computed"},  # mismatched vs correct_hash
            correlation_id=None, prev_hash=last.row_hash, row_hash=correct_hash,
        )
        db.add(altered)
        db.commit()
        altered_seq = altered.seq
        anchor_seq = last.seq

    result = client.get(f"/admin/audit/verify?since_seq={anchor_seq}", headers=auth(admin)).json()
    assert result["valid"] is False
    assert result["first_broken_seq"] == altered_seq
    assert "own stored content" in result["reason"]


def test_verify_skips_pre_chain_rows_with_a_null_row_hash(client):
    """A legacy row from before the chain existed must not be flagged as corrupt."""
    owner = user_token(client, "owner@ngo.org")
    org_id = _pending_org(client, owner)
    admin = _admin(client)

    with SessionLocal() as db:
        pre_existing_seq = db.scalar(select(AuditEvent.seq).order_by(AuditEvent.seq.desc()).limit(1)) or 0
        from datetime import UTC, datetime
        legacy = AuditEvent(
            occurred_at=datetime.now(UTC), action="legacy.action", resource_type="organization",
            resource_id=org_id, actor_user_id=None, org_id=org_id, details={}, correlation_id=None,
            prev_hash=None, row_hash=None,
        )
        db.add(legacy)
        db.commit()

    client.post(f"/admin/organizations/{org_id}/verification", json={"decision": "APPROVED"}, headers=auth(admin))
    # Scope past this file's earlier, intentionally-broken test rows (audit_events is never
    # truncated between tests); start right after the legacy row's predecessor so the
    # legacy row itself is included and confirmed skipped, not just absent from the window.
    result = client.get(f"/admin/audit/verify?since_seq={pre_existing_seq + 1}", headers=auth(admin)).json()
    assert result["valid"] is True


def test_verify_since_seq_narrows_the_checked_range(client):
    owner = user_token(client, "owner@ngo.org")
    org_id = _pending_org(client, owner)
    admin = _admin(client)
    client.post(f"/admin/organizations/{org_id}/verification", json={"decision": "APPROVED"}, headers=auth(admin))

    with SessionLocal() as db:
        latest_seq = db.scalar(select(AuditEvent.seq).order_by(AuditEvent.seq.desc()).limit(1))

    result = client.get(f"/admin/audit/verify?since_seq={latest_seq}", headers=auth(admin)).json()
    assert result["valid"] is True
    assert result["checked"] == 1
