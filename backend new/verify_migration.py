"""
verify_migration.py -- Quick sanity-check: row counts + sample rows from Supabase.
Run from backend/: python verify_migration.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parent))

SYNC_DATABASE_URL = os.environ["SYNC_DATABASE_URL"]
engine = create_engine(SYNC_DATABASE_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine)

TABLES = [
    "inventory",
    "customer_sales",
    "sale_items",
    "suppliers",
    "purchase_orders",
    "order_items",
    "demand_forecast",
    "proactive_alerts",
    "competitor_prices",
]

def main():
    session = Session()
    try:
        print("=" * 50)
        print("  Supabase Migration Verification")
        print("=" * 50)

        # ---------- Row counts ----------
        print("\n  Row Counts")
        print("  " + "-" * 36)
        for table in TABLES:
            result = session.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            print(f"  {table:<22} {count:>6} rows")

        # ---------- Sample: inventory ----------
        print("\n  Sample row -- inventory")
        print("  " + "-" * 36)
        row = session.execute(
            text("SELECT product_name, stock, reorder_level, price FROM inventory LIMIT 1")
        ).fetchone()
        if row:
            print(f"  product_name : {row.product_name}")
            print(f"  stock        : {row.stock}")
            print(f"  reorder_level: {row.reorder_level}")
            print(f"  price        : {row.price}")
        else:
            print("  (no rows)")

        # ---------- Sample: customer_sales ----------
        print("\n  Sample row -- customer_sales")
        print("  " + "-" * 36)
        row = session.execute(
            text("SELECT customer, total, payment_method, sale_date FROM customer_sales LIMIT 1")
        ).fetchone()
        if row:
            print(f"  customer      : {row.customer}")
            print(f"  total         : {row.total}")
            print(f"  payment_method: {row.payment_method}")
            print(f"  sale_date     : {row.sale_date}")
        else:
            print("  (no rows)")

        print("\n" + "=" * 50)
        print("  Verification complete.")
        print("=" * 50)

    finally:
        session.close()

if __name__ == "__main__":
    main()
