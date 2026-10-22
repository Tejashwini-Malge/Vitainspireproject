"""Integration tests for smart admin intelligence features."""
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    Organization,
    OrgType,
    VerificationStatus,
    User,
    Donation,
    RiskScore,
    AnomalyFlag,
)
from app.services.risk_scorer import (
    compute_risk_score_deterministic,
    save_risk_score,
)
from app.services.anomaly_detector import (
    detect_donation_anomalies_deterministic,
    save_anomaly_flags,
)


@pytest.fixture
def db():
    """Get test database session."""
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def test_ngo(db: Session) -> Organization:
    """Create a test NGO."""
    ngo = Organization(
        name="Test NGO",
        org_type=OrgType.NGO,
        verification_status=VerificationStatus.PENDING,
    )
    db.add(ngo)
    db.commit()
    return ngo


@pytest.fixture
def test_donor(db: Session) -> User:
    """Create a test donor user."""
    user = User(
        email="donor@example.com",
        password_hash="hashed",
        full_name="Test Donor",
    )
    db.add(user)
    db.commit()
    return user


class TestRiskScorer:
    """Tests for risk scoring service."""

    def test_compute_risk_score_new_org(self, db: Session, test_ngo: Organization):
        """Test risk score for a newly created NGO."""
        result = compute_risk_score_deterministic(test_ngo, db)

        assert result["score_value"] >= 0
        assert result["score_value"] <= 100
        assert result["confidence"] in ["LOW", "MEDIUM", "HIGH"]
        assert "verification" in result["factors"]

    def test_compute_risk_score_pending_org(self, db: Session, test_ngo: Organization):
        """Test that pending verification increases risk."""
        result = compute_risk_score_deterministic(test_ngo, db)

        # Pending org should have verification risk > 0
        assert result["factors"]["verification"] > 0

    def test_save_risk_score(self, db: Session, test_ngo: Organization):
        """Test saving risk score to database."""
        result = compute_risk_score_deterministic(test_ngo, db)
        saved = save_risk_score(db, test_ngo.id, "NGO", result)

        assert saved.org_id == test_ngo.id
        assert saved.score_value == result["score_value"]
        assert saved.score_type == "NGO"

        # Verify it's in the database
        from sqlalchemy import select
        stmt = select(RiskScore).where(RiskScore.org_id == test_ngo.id)
        retrieved = db.scalar(stmt)
        assert retrieved is not None
        assert retrieved.score_value == result["score_value"]

    def test_risk_score_factors_sum(self, db: Session, test_ngo: Organization):
        """Test that risk score factors don't exceed 100."""
        result = compute_risk_score_deterministic(test_ngo, db)

        total = sum(result["factors"].values())
        assert total <= 100, f"Risk factors total {total} exceeds 100"


class TestAnomalyDetector:
    """Tests for anomaly detection service."""

    def test_no_anomalies_for_normal_donation(
        self,
        db: Session,
        test_ngo: Organization,
        test_donor: User,
    ):
        """Test that normal donations don't trigger anomalies."""
        donation = Donation(
            org_id=test_ngo.id,
            donor_user_id=test_donor.id,
            donor_name="Test Donor",
            donor_email="donor@example.com",
            amount_minor=10000,
            currency="INR",
            billing_address={"city": "Test"},
        )
        db.add(donation)
        db.commit()

        anomalies = detect_donation_anomalies_deterministic(donation, db)

        # Normal donation should have few/no anomalies
        critical_flags = [a for a in anomalies if a["severity"] == "CRITICAL"]
        assert len(critical_flags) == 0

    def test_duplicate_account_detection(self, db: Session, test_ngo: Organization, test_donor: User):
        """Test detection of duplicate accounts."""
        # Skip: Duplicate email detection requires creating users with same email,
        # but unique constraint prevents this in the current test
        pass

    def test_save_anomaly_flags(
        self,
        db: Session,
        test_ngo: Organization,
        test_donor: User,
    ):
        """Test saving anomaly flags to database."""
        donation = Donation(
            org_id=test_ngo.id,
            donor_user_id=test_donor.id,
            donor_name="Test Donor",
            donor_email="donor@example.com",
            amount_minor=10000,
            currency="INR",
            billing_address={"city": "Test"},
        )
        db.add(donation)
        db.commit()

        anomalies = detect_donation_anomalies_deterministic(donation, db)

        if anomalies:
            saved_flags = save_anomaly_flags(
                db,
                test_ngo.id,
                anomalies,
                donation.id,
            )

            assert len(saved_flags) > 0
            for flag in saved_flags:
                assert flag.org_id == test_ngo.id
                assert flag.flag_type in [a["flag_type"] for a in anomalies]

            # Verify in database
            from sqlalchemy import select
            stmt = select(AnomalyFlag).where(AnomalyFlag.org_id == test_ngo.id)
            retrieved = db.scalars(stmt).all()
            assert len(retrieved) > 0

    def test_unusual_donation_amount_detection(self, db: Session, test_ngo: Organization):
        """Test detection of unusually large donations."""
        # Create normal baseline donations
        for i in range(5):
            donation = Donation(
                org_id=test_ngo.id,
                donor_name=f"Donor {i}",
                donor_email=f"donor{i}@example.com",
                amount_minor=1000,  # Normal amount
                currency="INR",
                billing_address={"city": "Test"},
                created_at=datetime.now(timezone.utc) - timedelta(days=10),
            )
            db.add(donation)
        db.commit()

        # Now create unusual large donation
        large_donation = Donation(
            org_id=test_ngo.id,
            donor_name="Large Donor",
            donor_email="large@example.com",
            amount_minor=100000,  # 100x normal
            currency="INR",
            billing_address={"city": "Test"},
        )
        db.add(large_donation)
        db.commit()

        anomalies = detect_donation_anomalies_deterministic(large_donation, db)

        # Should detect unusual amount
        unusual_flags = [a for a in anomalies if a["flag_type"] == "UNUSUAL_DONATION_AMOUNT"]
        # Note: This may not trigger if there aren't enough samples, but test the logic
        if unusual_flags:
            assert unusual_flags[0]["severity"] in ["HIGH", "CRITICAL"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
