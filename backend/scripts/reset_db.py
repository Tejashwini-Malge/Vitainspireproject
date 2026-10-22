#!/usr/bin/env python3
"""Complete database reset - drop schema and re-migrate."""

import sys
from sqlalchemy import text

sys.path.insert(0, str(__file__).rsplit('/', 1)[0] + '/../')

from app.db import engine
from alembic import command
from alembic.config import Config
from pathlib import Path

def reset():
    print("🔄 Resetting database...")

    # Drop everything
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    print("✓ Dropped schema")

    # Re-migrate
    backend_dir = Path(__file__).resolve().parent.parent
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")
    print("✓ Migrations complete")

    print("\n✅ Database reset complete!")
    print("Now run: python scripts/seed_test_data.py")

if __name__ == '__main__':
    reset()
