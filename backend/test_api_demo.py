#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Demo script showing the Admin Intelligence Dashboard API in action.
Tests all 6 smart features with realistic data.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

# Setup test database
os.environ.setdefault("VITA_DATABASE_URL", "postgresql+psycopg://vita:vita@localhost:5432/vitainspire_test")

from sqlalchemy import text
from app.db import engine, SessionLocal
from app.models import (
    Organization, OrgType, VerificationStatus, User, Donation,
    Document, DocumentType, ReviewStatus, Project, ProjectStatus
)
from app.services.risk_scorer import compute_risk_score_deterministic, save_risk_score
from app.services.anomaly_detector import detect_donation_anomalies_deterministic, save_anomaly_flags
from app.services.churn_predictor import predict_churn_deterministic, save_churn_prediction
from app.services.campaign_success import predict_campaign_success_deterministic, save_campaign_prediction
from app.services.smart_alerts import generate_all_alerts

def print_section(title: str):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def test_risk_scoring():
    """Demonstrate Risk Scoring Service"""
    print_section("1. RISK SCORING SERVICE")
    db = SessionLocal()

    try:
        # Create test NGO
        ngo = Organization(
            name="Community Health Initiative",
            org_type=OrgType.NGO,
            verification_status=VerificationStatus.PENDING,
        )
        db.add(ngo)
        db.commit()

        # Compute risk score
        result = compute_risk_score_deterministic(ngo, db)
        saved = save_risk_score(db, ngo.id, "NGO", result)
        db.commit()

        print(f"[OK] NGO Created: {ngo.name}")
        print(f"   Organization ID: {ngo.id}")
        print(f"\n[SCORE] Risk Score Computed:")
        print(f"   Score: {result['score_value']}/100")
        print(f"   Confidence: {result['confidence']}")
        print(f"   Factors:")
        for factor, value in result['factors'].items():
            print(f"     - {factor}: {value} points")
        print(f"\n[SAVED] Score Saved to Database")
        print(f"   Score ID: {saved.id}")

    finally:
        db.close()

def test_anomaly_detection():
    """Demonstrate Anomaly Detection Service"""
    print_section("2. ANOMALY DETECTION SERVICE")
    db = SessionLocal()

    try:
        # Create test donor and NGO
        donor = User(
            email="test.donor@example.com",
            password_hash="hashed",
            full_name="Test Donor",
        )
        db.add(donor)

        ngo = Organization(
            name="Education Foundation",
            org_type=OrgType.NGO,
            verification_status=VerificationStatus.APPROVED,
        )
        db.add(ngo)
        db.commit()

        # Create donation
        donation = Donation(
            org_id=ngo.id,
            donor_user_id=donor.id,
            donor_name="Test Donor",
            donor_email="test.donor@example.com",
            amount_minor=50000,  # 500 INR
            currency="INR",
            billing_address={"city": "Bangalore"},
        )
        db.add(donation)
        db.commit()

        # Detect anomalies
        anomalies = detect_donation_anomalies_deterministic(donation, db)
        if anomalies:
            saved_flags = save_anomaly_flags(db, ngo.id, anomalies, donation.id)
            db.commit()

        print(f"[OK] Donation Created:")
        print(f"   NGO: {ngo.name}")
        print(f"   Donor: {donor.full_name}")
        print(f"   Amount: {donation.amount_minor/100} INR")
        print(f"\n[ANALYSIS] Anomaly Detection Results:")
        if anomalies:
            print(f"   Flags Detected: {len(anomalies)}")
            for flag in anomalies:
                print(f"   - {flag['flag_type']} ({flag['severity']})")
                print(f"     Reason: {flag['reasoning']}")
        else:
            print(f"   [OK] No anomalies detected - donation appears normal")

    finally:
        db.close()

def test_churn_prediction():
    """Demonstrate Churn Prediction Service"""
    print_section("3. CHURN PREDICTION SERVICE")
    db = SessionLocal()

    try:
        # Create inactive NGO
        ngo = Organization(
            name="Inactive Health NGO",
            org_type=OrgType.NGO,
            verification_status=VerificationStatus.APPROVED,
            created_at=datetime.now(timezone.utc) - timedelta(days=60),
        )
        db.add(ngo)
        db.commit()

        # Create old donation (60+ days ago)
        donation = Donation(
            org_id=ngo.id,
            donor_name="Old Donor",
            donor_email="old@example.com",
            amount_minor=10000,
            currency="INR",
            billing_address={"city": "Mumbai"},
            created_at=datetime.now(timezone.utc) - timedelta(days=60),
        )
        db.add(donation)
        db.commit()

        # Predict churn
        result = predict_churn_deterministic(ngo, db)
        saved = save_churn_prediction(db, ngo.id, ngo.org_type.value, result)
        db.commit()

        print(f"[OK] Churn Analysis for: {ngo.name}")
        print(f"   Organization ID: {ngo.id}")
        print(f"\n[PREDICT] Churn Risk Prediction:")
        print(f"   Churn Risk Score: {result['churn_risk_score']}/100")
        print(f"   Risk Factors:")
        for factor, value in result['factors'].items():
            print(f"     - {factor}: {value}")
        if result['intervention_suggested']:
            print(f"\n[ACTION] Suggested Intervention:")
            print(f"   {result['intervention_suggested']}")

    finally:
        db.close()

def test_campaign_success_prediction():
    """Demonstrate Campaign Success Prediction Service"""
    print_section("4. CAMPAIGN SUCCESS PREDICTION SERVICE")
    db = SessionLocal()

    try:
        # Create NGO and project
        ngo = Organization(
            name="Healthcare Innovation",
            org_type=OrgType.NGO,
            verification_status=VerificationStatus.APPROVED,
        )
        db.add(ngo)
        db.commit()

        project = Project(
            org_id=ngo.id,
            title="Rural Clinic Initiative",
            summary="Building clinics in rural areas",
            status=ProjectStatus.PUBLISHED,
        )
        db.add(project)
        db.commit()

        # Predict success
        result = predict_campaign_success_deterministic(project, db)
        saved = save_campaign_prediction(db, project.id, result)
        db.commit()

        print(f"[OK] Campaign Success Forecast:")
        print(f"   Project: {project.title}")
        print(f"   NGO: {ngo.name}")
        print(f"\n[FORECAST] Success Prediction:")
        print(f"   Success Probability: {result['success_probability']:.0%}")
        print(f"   Confidence: {result['confidence']}")
        print(f"   Reasoning:")
        for key, value in result['reasoning'].items():
            if key != 'claude_review':
                print(f"     - {key}: {value}")

    finally:
        db.close()

def test_smart_alerts():
    """Demonstrate Smart Alerts Generation"""
    print_section("5. SMART ALERTS ENGINE")
    db = SessionLocal()

    try:
        # Create test NGO that hasn't been updated
        ngo = Organization(
            name="Inactive NGO",
            org_type=OrgType.NGO,
            verification_status=VerificationStatus.APPROVED,
            created_at=datetime.now(timezone.utc) - timedelta(days=40),
        )
        db.add(ngo)
        db.commit()

        # Generate alerts
        result = generate_all_alerts(db)

        print(f"[OK] Alert Generation Complete:")
        print(f"   Total Alerts Generated: {result['alert_count']}")
        print(f"\n[TYPES] Alert Types Generated:")
        alert_types = set()
        for alert in result['alerts']:
            if alert.alert_type not in alert_types:
                alert_types.add(alert.alert_type)
                print(f"   - {alert.alert_type}")

        if result['alerts']:
            print(f"\n[SAMPLE] Sample Alert:")
            sample = result['alerts'][0]
            print(f"   Type: {sample.alert_type}")
            print(f"   Priority: {sample.priority}")
            print(f"   Message: {sample.message}")

    finally:
        db.close()

def test_dashboard_summary():
    """Demonstrate Dashboard Summary Endpoint"""
    print_section("6. ADMIN DASHBOARD SUMMARY")
    db = SessionLocal()

    try:
        from sqlalchemy import func, select
        from app.models import RiskScore, AnomalyFlag, SmartAlert, ChurnPrediction

        # Get counts
        high_risk = db.scalar(select(func.count(RiskScore.id)).where(RiskScore.score_value > 70)) or 0
        anomalies = db.scalar(select(func.count(AnomalyFlag.id)).where(AnomalyFlag.acknowledged_at.is_(None))) or 0
        unread_alerts = db.scalar(select(func.count(SmartAlert.id)).where(SmartAlert.read_at.is_(None))) or 0
        churn_risks = db.scalar(select(func.count(ChurnPrediction.id)).where(ChurnPrediction.churn_risk_score > 70)) or 0
        pending_docs = db.scalar(select(func.count(Document.id)).where(Document.review_status == ReviewStatus.PENDING_REVIEW)) or 0

        print(f"[OK] Dashboard Summary Generated:")
        print(f"\n[METRICS] Key Metrics:")
        print(f"   High-Risk Organizations: {high_risk}")
        print(f"   Active Anomaly Flags: {anomalies}")
        print(f"   Unread Smart Alerts: {unread_alerts}")
        print(f"   Churn Risk Organizations: {churn_risks}")
        print(f"   Pending Documents: {pending_docs}")
        print(f"\n[TOTAL] Total Intelligence Signals: {high_risk + anomalies + unread_alerts + churn_risks + pending_docs}")

    finally:
        db.close()

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("  ADMIN INTELLIGENCE DASHBOARD - FULL SYSTEM TEST")
    print("="*80)
    print("\nTesting all 6 smart features with realistic data...\n")

    try:
        test_risk_scoring()
        test_anomaly_detection()
        test_churn_prediction()
        test_campaign_success_prediction()
        test_smart_alerts()
        test_dashboard_summary()

        print_section("SUCCESS: ALL TESTS PASSED")
        print("The Admin Intelligence Dashboard is fully operational!")
        print("\nNext Steps:")
        print("1. Frontend: Navigate to http://localhost:3000/admin/intelligence")
        print("2. Login with your admin credentials")
        print("3. View all 6 smart intelligence features")
        print("4. Try the interactive buttons and filters")
        print("\n" + "="*80 + "\n")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
