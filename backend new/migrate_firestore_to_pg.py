"""
migrate_firestore_to_pg.py — One-time migration: Firestore → PostgreSQL (Supabase).

Run from the backend/ folder:
    python migrate_firestore_to_pg.py
"""

import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

# ── MUST be set before importing firebase_admin (protobuf 6.x compat) ──────
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

from dotenv import load_dotenv

# Load .env from backend root
load_dotenv(Path(__file__).resolve().parent / ".env")

# ── Firebase ────────────────────────────────────────────────────────────────
import firebase_admin
from firebase_admin import credentials, firestore as fs

_SA_KEY = Path(__file__).resolve().parent / "serviceAccountKey.json"
if not firebase_admin._apps:
    cred = credentials.Certificate(str(_SA_KEY))
    firebase_admin.initialize_app(cred)

db = fs.client()

# ── SQLAlchemy (sync) ───────────────────────────────────────────────────────
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

SYNC_DATABASE_URL = os.environ["SYNC_DATABASE_URL"]
engine = create_engine(SYNC_DATABASE_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine)

# ── ORM models (registers them on Base.metadata) ───────────────────────────
# Ensure backend/ is on sys.path so app.* imports work
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.models import (
    CompetitorPrice,
    CustomerSale,
    DemandForecast,
    Inventory,
    OrderItem,
    ProactiveAlert,
    PurchaseOrder,
    SaleItem,
    Supplier,
)

STORE_ID = "store001"

# ── Helpers ─────────────────────────────────────────────────────────────────

def _parse_dt(value) -> datetime | None:
    """Coerce Firestore timestamps / ISO strings / None to a datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if hasattr(value, "ToDatetime"):          # google.protobuf Timestamp
        return value.ToDatetime()
    if hasattr(value, "_seconds"):            # firestore DatetimeWithNanoseconds
        return datetime.utcfromtimestamp(value._seconds)
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _new_id() -> uuid.UUID:
    return uuid.uuid4()


# ── Migration functions ──────────────────────────────────────────────────────

def migrate_inventory(session: Session) -> int:
    print("Migrating inventory...", end=" ", flush=True)
    docs = db.collection("inventory").stream()
    count = 0
    for doc in docs:
        d = doc.to_dict()
        try:
            row = Inventory(
                id=_new_id(),
                store_id=STORE_ID,
                product_id=doc.id,
                product_name=d.get("productName") or d.get("product_name") or "",
                sku=d.get("sku"),
                stock=float(d.get("stock", 0)),
                reorder_level=float(d.get("reorderLevel") or d.get("reorder_level") or 10),
                price=float(d["price"]) if d.get("price") is not None else None,
                wholesale_cost=float(d["wholesaleCost"]) if d.get("wholesaleCost") is not None else None,
                supplier=d.get("supplier"),
                expiry_date=_parse_dt(d.get("expiryDate") or d.get("expiry_date")),
                category=d.get("category"),
                created_at=_parse_dt(d.get("created_at")) or datetime.utcnow(),
                updated_at=_parse_dt(d.get("updated_at")) or datetime.utcnow(),
            )
            if not row.product_name:
                print(f"\n  [!] inventory/{doc.id}: missing product_name, skipping")
                continue
            session.add(row)
            count += 1
        except Exception as e:
            print(f"\n  [!] inventory/{doc.id}: {e}, skipping")
    print(f"done ({count} rows)")
    return count


def migrate_sales(session: Session) -> int:
    print("Migrating customer_sales + sale_items...", end=" ", flush=True)
    docs = db.collection("customer_sales").stream()
    count = 0
    for doc in docs:
        d = doc.to_dict()
        try:
            sale_date = _parse_dt(d.get("date") or d.get("sale_date"))
            if sale_date is None:
                print(f"\n  [!] customer_sales/{doc.id}: missing sale_date, skipping")
                continue
            total = d.get("total")
            if total is None:
                print(f"\n  [!] customer_sales/{doc.id}: missing total, skipping")
                continue

            sale_id = _new_id()
            sale = CustomerSale(
                id=sale_id,
                store_id=STORE_ID,
                customer=d.get("customer"),
                total=float(total),
                payment_method=d.get("paymentMethod") or d.get("payment_method"),
                sale_date=sale_date,
                created_at=_parse_dt(d.get("created_at")) or datetime.utcnow(),
            )
            session.add(sale)
            count += 1

            for item in d.get("items", []):
                try:
                    si = SaleItem(
                        id=_new_id(),
                        sale_id=sale_id,
                        product_id=str(item.get("productId") or item.get("product_id") or ""),
                        product_name=str(item.get("productName") or item.get("product_name") or ""),
                        quantity=float(item.get("quantity", 0)),
                        price=float(item.get("price", 0)),
                    )
                    session.add(si)
                except Exception as ie:
                    print(f"\n  [!] sale_items for sale {doc.id}: {ie}, skipping item")
        except Exception as e:
            print(f"\n  [!] customer_sales/{doc.id}: {e}, skipping")
    print(f"done ({count} rows)")
    return count


def migrate_suppliers(session: Session) -> int:
    print("Migrating suppliers...", end=" ", flush=True)
    docs = db.collection("suppliers").stream()
    count = 0
    for doc in docs:
        d = doc.to_dict()
        try:
            name = d.get("supplierName") or d.get("supplier_name")
            if not name:
                print(f"\n  [!] suppliers/{doc.id}: missing supplier_name, skipping")
                continue
            row = Supplier(
                id=_new_id(),
                store_id=STORE_ID,
                supplier_name=name,
                products=d.get("products") or [],
                price_per_unit=float(d["price_per_unit"]) if d.get("price_per_unit") is not None else None,
                reliability=float(d["reliability"]) if d.get("reliability") is not None else None,
                contact=d.get("contact"),
                lead_time_days=int(d["leadTimeDays"]) if d.get("leadTimeDays") is not None else None,
                created_at=_parse_dt(d.get("created_at")) or datetime.utcnow(),
            )
            session.add(row)
            count += 1
        except Exception as e:
            print(f"\n  [!] suppliers/{doc.id}: {e}, skipping")
    print(f"done ({count} rows)")
    return count


def migrate_purchase_orders(session: Session) -> int:
    print("Migrating purchase_orders + order_items...", end=" ", flush=True)
    docs = db.collection("purchase_orders").stream()
    count = 0
    for doc in docs:
        d = doc.to_dict()
        try:
            supplier = d.get("supplier")
            if not supplier:
                print(f"\n  [!] purchase_orders/{doc.id}: missing supplier, skipping")
                continue

            order_id = _new_id()
            order = PurchaseOrder(
                id=order_id,
                store_id=STORE_ID,
                supplier=supplier,
                status=d.get("status", "pending"),
                total_amount=float(d["amount"]) if d.get("amount") is not None else None,
                order_date=_parse_dt(d.get("date") or d.get("order_date")) or datetime.utcnow(),
                created_at=_parse_dt(d.get("created_at")) or datetime.utcnow(),
            )
            session.add(order)
            count += 1

            for item in d.get("items", []):
                try:
                    oi = OrderItem(
                        id=_new_id(),
                        order_id=order_id,
                        product_name=str(item.get("productName") or item.get("product_name") or ""),
                        quantity=float(item.get("quantity", 0)),
                        unit_price=float(item["unitPrice"]) if item.get("unitPrice") is not None else None,
                    )
                    session.add(oi)
                except Exception as ie:
                    print(f"\n  [!] order_items for order {doc.id}: {ie}, skipping item")
        except Exception as e:
            print(f"\n  [!] purchase_orders/{doc.id}: {e}, skipping")
    print(f"done ({count} rows)")
    return count


def migrate_demand_forecast(session: Session) -> int:
    print("Migrating demand_forecast...", end=" ", flush=True)
    docs = db.collection("demand_forecast").stream()
    count = 0
    for doc in docs:
        d = doc.to_dict()
        try:
            product_id = d.get("productId") or d.get("product_id")
            predicted = d.get("predictedDemand") or d.get("predicted_demand")
            if product_id is None or predicted is None:
                print(f"\n  [!] demand_forecast/{doc.id}: missing product_id or predicted_demand, skipping")
                continue
            row = DemandForecast(
                id=_new_id(),
                store_id=STORE_ID,
                product_id=str(product_id),
                product_name=d.get("productName") or d.get("product_name"),
                predicted_demand=float(predicted),
                updated_at=_parse_dt(d.get("updated_at")) or datetime.utcnow(),
            )
            session.add(row)
            count += 1
        except Exception as e:
            print(f"\n  [!] demand_forecast/{doc.id}: {e}, skipping")
    print(f"done ({count} rows)")
    return count


def migrate_competitor_prices(session: Session) -> int:
    print("Migrating competitor_prices...", end=" ", flush=True)
    docs = db.collection("competitor_prices").stream()
    count = 0
    for doc in docs:
        d = doc.to_dict()
        try:
            product_id = d.get("productId") or d.get("product_id")
            price = d.get("competitorPrice") or d.get("competitor_price")
            if product_id is None or price is None:
                print(f"\n  [!] competitor_prices/{doc.id}: missing product_id or competitor_price, skipping")
                continue
            row = CompetitorPrice(
                id=_new_id(),
                store_id=STORE_ID,
                product_id=str(product_id),
                product_name=d.get("productName") or d.get("product_name"),
                competitor_price=float(price),
                updated_at=_parse_dt(d.get("updated_at")) or datetime.utcnow(),
            )
            session.add(row)
            count += 1
        except Exception as e:
            print(f"\n  [!] competitor_prices/{doc.id}: {e}, skipping")
    print(f"done ({count} rows)")
    return count


def migrate_proactive_alerts(session: Session) -> int:
    print("Migrating proactive_alerts...", end=" ", flush=True)
    docs = db.collection("proactive_alerts").stream()
    count = 0
    for doc in docs:
        d = doc.to_dict()
        try:
            alert_type = d.get("alert_type")
            message = d.get("message")
            if not alert_type or not message:
                print(f"\n  [!] proactive_alerts/{doc.id}: missing alert_type or message, skipping")
                continue
            row = ProactiveAlert(
                id=_new_id(),
                store_id=STORE_ID,
                alert_type=alert_type,
                severity=d.get("severity"),
                product_id=d.get("product_id"),
                product_name=d.get("product_name"),
                message=message,
                suggested_action=d.get("suggested_action"),
                dismissed=bool(d.get("dismissed", False)),
                created_at=_parse_dt(d.get("created_at")) or datetime.utcnow(),
                updated_at=_parse_dt(d.get("updated_at")) or datetime.utcnow(),
            )
            session.add(row)
            count += 1
        except Exception as e:
            print(f"\n  [!] proactive_alerts/{doc.id}: {e}, skipping")
    print(f"done ({count} rows)")
    return count


# -- Main ---------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  KiranaIQ -- Firestore -> PostgreSQL Migration")
    print("=" * 60)

    session = Session()
    counts: dict[str, int] = {}

    try:
        counts["inventory"]        = migrate_inventory(session)
        counts["customer_sales"]   = migrate_sales(session)
        counts["suppliers"]        = migrate_suppliers(session)
        counts["purchase_orders"]  = migrate_purchase_orders(session)
        counts["demand_forecast"]  = migrate_demand_forecast(session)
        counts["competitor_prices"]= migrate_competitor_prices(session)
        counts["proactive_alerts"] = migrate_proactive_alerts(session)

        session.commit()
        print()
        print("=" * 60)
        print("  Migration Summary")
        print("=" * 60)
        total = 0
        for table, n in counts.items():
            print(f"  {table:<22} {n:>5} rows")
            total += n
        print(f"  {'TOTAL':<22} {total:>5} rows")
        print("=" * 60)
        print("[OK] Migration complete.")

    except Exception as exc:
        session.rollback()
        print(f"\n[FAILED] Migration FAILED -- rolled back.\nError: {exc}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
