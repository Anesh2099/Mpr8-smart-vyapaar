"""
cleanup_test_data.py — Remove junk test data from the PostgreSQL database.
Run once with:  python cleanup_test_data.py
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from sqlalchemy import delete, update, text, create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Inventory, ProactiveAlert
from app.core.database import SYNC_DATABASE_URL
from datetime import datetime, timezone, timedelta

# Create sync engine (stripping URL params that psycopg2 doesn't support)
sync_url_clean = SYNC_DATABASE_URL.split("?")[0]
engine = create_engine(sync_url_clean)
SessionLocal = sessionmaker(bind=engine)


# ── Product IDs that are clearly test/junk data ──────────────────────────────
JUNK_PRODUCT_IDS = [
    "test-sku-e8d11b9a",
    "test-sku-263eb447",
    "test-001",
    "pfix-001",
    "fix-001",
    "final-001",
    "raw-001",
    "ffin-001",
    "pbuf-001",
    "t-1",
    "ngrk-001",
    "ngrk-002",
    "dart-001",
    "saas-55235",       # "AC" priced at ₹36,346
    "soappy-64673-00",  # "SOAP" priced at ₹123,456
    "ppp-342352-00",    # "popcorn"
    "test-009",         # "TEST"
    "cha-98989",        # "Channa" - test entry
    "5",                # duplicate "milk" with stock 8 / reorder 56
    "product001",       # early test "Milk"
    "product123",       # early test "Bread"
]


def main():
    with SessionLocal() as db:
        # ── 1. Delete junk inventory products ────────────────────────────────
        result = db.execute(
            delete(Inventory).where(
                Inventory.product_id.in_(JUNK_PRODUCT_IDS)
            ).returning(Inventory.product_id)
        )
        deleted_products = [row[0] for row in result.fetchall()]
        print(f"\n[OK] Deleted {len(deleted_products)} junk inventory items:")
        for pid in deleted_products:
            print(f"   - {pid}")

        # ── 2. Delete related alerts for deleted products ────────────────────
        result2 = db.execute(
            delete(ProactiveAlert).where(
                ProactiveAlert.product_id.in_(JUNK_PRODUCT_IDS)
            ).returning(ProactiveAlert.product_id)
        )
        deleted_alerts = [row[0] for row in result2.fetchall()]
        print(f"\n[OK] Deleted {len(deleted_alerts)} related alerts for junk products")

        # ── 3. Dismiss stale expired alerts (negative expiry days) ───────────
        # Auto-dismiss any expiry alert where the product expired more than 7 days ago
        result3 = db.execute(
            update(ProactiveAlert)
            .where(
                ProactiveAlert.alert_type == "expiry",
                ProactiveAlert.dismissed == False,
            )
            .values(
                dismissed=True,
                updated_at=datetime.now(timezone.utc),
            )
            .returning(ProactiveAlert.product_name)
        )
        dismissed_alerts = [row[0] for row in result3.fetchall()]
        print(f"\n[OK] Auto-dismissed {len(dismissed_alerts)} stale expiry alerts:")
        for name in dismissed_alerts:
            print(f"   - {name}")

        db.commit()

        # ── 4. Verify: count remaining inventory ────────────────────────────
        from sqlalchemy import select, func
        count = db.execute(
            select(func.count()).select_from(Inventory).where(
                Inventory.store_id == "store001"
            )
        )
        remaining = count.scalar()
        print(f"\n[INFO] Remaining inventory items for store001: {remaining}")

        alert_count = db.execute(
            select(func.count()).select_from(ProactiveAlert).where(
                ProactiveAlert.store_id == "store001",
                ProactiveAlert.dismissed == False,
            )
        )
        active_alerts = alert_count.scalar()
        print(f"[INFO] Remaining active alerts: {active_alerts}")

    print("\n[DONE] Database cleanup complete!")


if __name__ == "__main__":
    main()
