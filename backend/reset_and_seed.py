#!/usr/bin/env python3
import os
import sys

# Set working directory and Python path
os.chdir(r'D:\Vitainspire\backend')
sys.path.insert(0, r'D:\Vitainspire\backend')

print("🔄 Resetting database...")

from sqlalchemy import text
from app.db import engine
from alembic import command
from alembic.config import Config

# Drop everything
try:
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    print("✓ Dropped schema")
except Exception as e:
    print(f"✓ Schema cleared (or didn't exist): {e}")

# Re-migrate
try:
    command.upgrade(Config(r'D:\Vitainspire\backend\alembic.ini'), "head")
    print("✓ Migrations complete")
except Exception as e:
    print(f"✗ Migration error: {e}")

print("\n" + "="*60)
print("🌱 Seeding test data...")
print("="*60)

from datetime import date, timedelta
from sqlalchemy.orm import sessionmaker
from app.models import (
    User, Organization, Membership, Opportunity, Shortlist, Role, OrgType, VerificationStatus
)
from app.security import hash_password

Session = sessionmaker(bind=engine)
db = Session()

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

print(f"✓ Created CSR: {csr_org.name}")
print(f"  Email: admin@impactfund.com | Password: TestPassword123!")

# Create NGOs
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
    print(f"✓ Created NGO: {ngo_name}")
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

print(f"\n✓ Created Opportunity: {opp.title}")

# Create Shortlist
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

print(f"✓ Created Shortlist (NGO1 & NGO2 invited, NGO3 excluded)")

db.close()

print("\n" + "="*60)
print("✅ READY TO TEST!")
print("="*60)
print("\n1. Clear browser cache: F12 → Application → Clear site data")
print("2. Go to: http://localhost:3000")
print("3. Login: admin@impactfund.com / TestPassword123!")
print("4. Visit: /csr/opportunities")
print("\nThen test the full flow!")
