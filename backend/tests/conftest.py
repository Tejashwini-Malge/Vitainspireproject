import os
import tempfile

# Set before any app module reads settings. Tests never run against a database that is not named *_test.
os.environ.setdefault("VITA_DATABASE_URL", "postgresql+psycopg://vita:vita@localhost:5432/vitainspire_test")
os.environ.setdefault("VITA_STORAGE_DIR", tempfile.mkdtemp(prefix="vita-test-storage-"))

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import engine, SessionLocal  # noqa: E402
from app.main import create_app  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]

# Mutable tables are cleared between tests. The audit log is append-only and is never truncated by tests;
# tests therefore filter audit rows by the resource they created.
MUTABLE_TABLES = (
    "users, sessions, memberships, organizations, ngo_profiles, documents, document_review_decisions, "
    "pan_verifications, pan_verification_decisions, "
    "projects, donations, opportunities, eligibility_rules, eligibility_results, fit_scores, shortlists, "
    "proposals, approval_requests, commitments, finance_ledger, matching_jobs"
)


@pytest.fixture(scope="session", autouse=True)
def schema():
    url = str(engine.url)
    assert url.endswith("/vitainspire_test"), f"Tests must run against vitainspire_test, got {url}"
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    # The real migrations build the schema, so tests exercise exactly what production will run.
    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")
    yield


@pytest.fixture(autouse=True)
def clean_tables():
    with engine.begin() as conn:
        # All mutable tables, in order of dependencies (independent first)
        conn.execute(text(
            "TRUNCATE users, sessions, memberships, organizations, ngo_profiles, documents, "
            "document_review_decisions, pan_verifications, pan_verification_decisions, "
            "projects, donations, eligibility_rules, "
            "opportunities, eligibility_results, fit_scores, shortlists, proposals, "
            "approval_requests, commitments, finance_ledger, matching_jobs, "
            "risk_scores, anomaly_flags, smart_alerts, churn_predictions, campaign_predictions, "
            "campaigns, donation_types, campaign_donations, campaign_milestones, campaign_reviews, "
            "payments, recurring_donations, tax_receipts, email_queue, sent_emails "
            "RESTART IDENTITY CASCADE"
        ))
    yield


@pytest.fixture(autouse=True)
def fake_geocoder(monkeypatch):
    """Profile saves call out to Nominatim to geocode each geography entry. Tests never hit the
    real service: this gives every query the same fixed point, which is enough for every test
    that doesn't care about geocoding specifically. A test that does (distance/radius behaviour)
    overrides this with its own monkeypatch on app.routers.profiles.geocode / app.routers.feed.geocode.
    """
    from app.services.geocoding import GeoPoint

    async def _fake(query: str):
        query = query.strip()
        if not query:
            return None
        return GeoPoint(query=query, lat=20.0, lon=78.0, display_name=query)

    monkeypatch.setattr("app.routers.profiles.geocode", _fake)
    monkeypatch.setattr("app.routers.feed.geocode", _fake)


@pytest.fixture()
def client():
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture()
def storage_dir():
    return Path(os.environ["VITA_STORAGE_DIR"])


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.close()
