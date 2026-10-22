"""POST /admin/bootstrap: the one-time, token-gated path to the first platform admin on hosts
with no database shell access. Disabled unless an operator set VITA_ADMIN_BOOTSTRAP_TOKEN.
"""

from tests.helpers import auth, user_token


def test_bootstrap_is_disabled_by_default(client):
    token = user_token(client, "owner@ngo.org")
    r = client.post("/admin/bootstrap", json={"email": "owner@ngo.org", "token": "anything"})
    assert r.status_code == 403
    assert "not enabled" in r.json()["detail"]


def test_bootstrap_rejects_wrong_token(client, monkeypatch):
    monkeypatch.setattr("app.routers.admin_bootstrap.settings.admin_bootstrap_token", "correct-token")
    user_token(client, "owner@ngo.org")
    r = client.post("/admin/bootstrap", json={"email": "owner@ngo.org", "token": "wrong-token"})
    assert r.status_code == 403


def test_bootstrap_404s_for_unknown_email(client, monkeypatch):
    monkeypatch.setattr("app.routers.admin_bootstrap.settings.admin_bootstrap_token", "correct-token")
    r = client.post("/admin/bootstrap", json={"email": "nobody@example.com", "token": "correct-token"})
    assert r.status_code == 404


def test_bootstrap_grants_platform_admin_with_correct_token(client, monkeypatch):
    monkeypatch.setattr("app.routers.admin_bootstrap.settings.admin_bootstrap_token", "correct-token")
    token = user_token(client, "ops@platform.org")

    r = client.post("/admin/bootstrap", json={"email": "ops@platform.org", "token": "correct-token"})
    assert r.status_code == 200, r.text
    assert r.json() == {"granted": True, "email": "ops@platform.org"}

    r = client.get("/auth/me", headers=auth(token))
    assert r.json()["is_platform_admin"] is True
