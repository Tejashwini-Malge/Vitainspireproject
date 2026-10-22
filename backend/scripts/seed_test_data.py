#!/usr/bin/env python3
"""Seed test data for complete end-to-end testing."""

import sys
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(__file__).rsplit('/', 1)[0] + '/../')

from app.db import engine, get_db
from app.models import (
    User, Organization, Membership, Opportunity, Shortlist, Role, OrgType, VerificationStatus
)
from app.security import hash_password

Session = sessionmaker(bind=engine)
db = Session()

def seed():
    # Clear existing test data
    db.query(Shortlist).delete()
    db.query(Opportunity).delete()
    db.query(Membership).delete()
    db.query(User).delete()
    db.query(Organization).delete()
    db.commit()

    print("✓ Cleared old test data")

    # Create CSR Organization (already verified)
    csr_org = Organization(
        name="Impact Fund CSR",
        org_type=OrgType.CSR,
        verification_status=VerificationStatus.APPROVED,
        verified_at=date.today(),
        verification_reason="Seeded test data - pre-approved"
    )
    db.add(csr_org)
    db.flush()

    # Create CSR User
    csr_user = User(
        email="admin@impactfund.com",
        password_hash=hash_password("TestPassword123!"),
        full_name="CSR Admin"
    )
    db.add(csr_user)
    db.flush()
    db.add(Membership(org_id=csr_org.id, user_id=csr_user.id, role=Role.ADMIN))
    db.commit()

    print(f"✓ Created CSR: {csr_org.name} ({csr_org.id})")
    print(f"  Email: admin@impactfund.com | Password: TestPassword123!")

    # Create NGO Organizations
    ngo_names = ["Health for All", "Water Initiative", "Education First"]
    ngo_users = []

    for i, ngo_name in enumerate(ngo_names):
        ngo_org = Organization(
            name=ngo_name,
            org_type=OrgType.NGO,
            verification_status=VerificationStatus.APPROVED,
            verified_at=date.today()
        )
        db.add(ngo_org)
        db.flush()

        ngo_user = User(
            email=f"ngo{i+1}@test.com",
            password_hash=hash_password("TestPassword123!"),
            full_name=f"NGO Admin {i+1}"
        )
        db.add(ngo_user)
        db.flush()
        db.add(Membership(org_id=ngo_org.id, user_id=ngo_user.id, role=Role.ADMIN))
        db.commit()

        ngo_users.append((ngo_org, ngo_user))
        print(f"✓ Created NGO: {ngo_name} ({ngo_org.id})")
        print(f"  Email: ngo{i+1}@test.com | Password: TestPassword123!")

    # Create Opportunity
    opp = Opportunity(
        org_id=csr_org.id,
        title="Healthcare Innovation Fund",
        description="Fund innovative mobile health solutions to reach rural communities",
        sectors=["health", "technology"],
        geographies=["Karnataka", "Tamil Nadu"],
        budget_min=1000000,
        budget_max=5000000,
        deadline=date.today() + timedelta(days=90),
        requirements_text="NGOs must have healthcare focus and proven track record",
        status="PUBLISHED"
    )
    db.add(opp)
    db.flush()
    db.commit()

    print(f"\n✓ Created Opportunity: {opp.title} ({opp.id})")
    print(f"  Budget: ₹10L - ₹50L | Deadline: {opp.deadline}")

    # Create Shortlist (invite first 2 NGOs)
    shortlist = Shortlist(
        shortlist_id=opp.id,
        opportunity_id=opp.id,
        revision_num=1,
        ngo_ids=[ngo_users[0][0].id, ngo_users[1][0].id],
        is_current=True,
        selected_by_user_id=csr_user.id
    )
    db.add(shortlist)
    db.commit()

    print(f"\n✓ Created Shortlist with NGOs:")
    print(f"  - {ngo_users[0][0].name}")
    print(f"  - {ngo_users[1][0].name}")
    print(f"  (Note: {ngo_users[2][0].name} NOT invited)")

    print("\n" + "="*60)
    print("SEED DATA COMPLETE - Ready to test!")
    print("="*60)
    print("\nTEST FLOW:")
    print("1. Login as CSR: admin@impactfund.com / TestPassword123!")
    print("   → Go to /csr/opportunities → View opportunity")
    print("   → Go to /csr/proposals → No proposals yet")
    print("\n2. Login as NGO (shortlisted): ngo1@test.com / TestPassword123!")
    print("   → Go to /ngo/proposals/create → Submit proposal")
    print("   → Go to /ngo/proposals → View submitted proposal")
    print("\n3. Login as NGO (NOT shortlisted): ngo3@test.com / TestPassword123!")
    print("   → Go to /ngo/proposals/create → Try to submit")
    print("   → Should get 403 Forbidden (not shortlisted)")
    print("\n4. Login as CSR: admin@impactfund.com / TestPassword123!")
    print("   → Go to /csr/proposals → View NGO proposal")
    print("   → Click Approve → Creates financial commitment")
    print("   → Or Request Changes → Send feedback to NGO")

if __name__ == '__main__':
    seed()
