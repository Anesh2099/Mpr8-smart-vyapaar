"""
seed_inventory.py — Populates Firestore with realistic kirana store inventory.

Run from the backend/ directory:
    python seed_inventory.py

This seeds 25+ realistic products with varied states:
  - Many healthy / well-stocked items
  - Several LOW STOCK items (stock < reorderLevel) → triggers low_stock alerts
  - Several NEAR-EXPIRY items (expiryDate within 5 days) → triggers expiry alerts
  - Different categories, suppliers, and prices for variety

After seeding, it immediately triggers the proactive monitor checks so
alerts are written to the proactive_alerts collection right away.
"""

import sys
import os
from datetime import datetime, timedelta, timezone

# Make sure app imports work from backend/
sys.path.insert(0, os.path.dirname(__file__))

from app.core.config import db
from app.agents.inventory_agent import check_low_stock, check_expiry, _write_alert


TODAY = datetime.now(timezone.utc)

def dt(days_from_now: int) -> str:
    """Return an ISO-format date string N days from today (UTC)."""
    return (TODAY + timedelta(days=days_from_now)).isoformat()


# ── Product Definitions ────────────────────────────────────────────────────────
# Format: (product_id, productName, sku, category, stock, reorderLevel, price, supplier, forecast, expiryDate_days_from_now)
# expiryDate_days_from_now = None means no expiry (dry goods etc.)
# Negative value = already expired (we skip those to keep it realistic)

PRODUCTS = [
    # ── GRAINS & PULSES (healthy stock mostly)
    ("prod_001", "Basmati Rice 5kg",     "RICE-BAS-5",  "Grains",   45, 20, 320,  "Agro Direct",      "High demand",  None),
    ("prod_002", "Toor Dal 1kg",          "DAL-TOOR-1",  "Pulses",    6,  15, 92,   "Pulses Hub",       "Moderate",     None),   # LOW STOCK
    ("prod_003", "Chana Dal 1kg",         "DAL-CHAN-1",  "Pulses",   28,  10, 85,   "Pulses Hub",       "Moderate",     None),
    ("prod_004", "Maida 1kg",             "MAIDA-1KG",   "Grains",    3,  12, 45,   "Flour Mills",      "Low",          None),   # LOW STOCK
    ("prod_005", "Besan 500g",            "BSN-500G",    "Grains",   35,  15, 38,   "Flour Mills",      "Moderate",     None),
    ("prod_006", "Sooji (Rava) 500g",     "SOJI-500G",   "Grains",   12,  15, 32,   "Flour Mills",      "Low",          None),   # LOW STOCK

    # ── DAIRY & PERISHABLES (near-expiry triggers)
    ("prod_007", "Full Cream Milk 1L",   "MILK-FC-1L",  "Dairy",     8,  20, 62,   "Dairy Direct",     "High demand",  2),     # LOW STOCK + NEAR EXPIRY
    ("prod_008", "Curd 500g",             "CURD-500G",   "Dairy",    15,  10, 45,   "Dairy Direct",     "Moderate",     3),     # NEAR EXPIRY
    ("prod_009", "Paneer 200g",           "PNEER-200G",  "Dairy",     4,  10, 120,  "Dairy Direct",     "High demand",  1),     # CRITICAL LOW + NEAR EXPIRY
    ("prod_010", "Butter 100g",           "BUTR-100G",   "Dairy",    22,  10, 55,   "Dairy Direct",     "Moderate",     None),
    ("prod_011", "Cheese Slices 200g",    "CHSE-200G",   "Dairy",     7,  10, 95,   "Premium Foods",    "Moderate",     4),     # LOW STOCK + NEAR EXPIRY

    # ── OILS & FATS
    ("prod_012", "Sunflower Oil 1L",      "OIL-SFL-1L",  "Oils",     30,  15, 165,  "Oil India",        "High demand",  None),
    ("prod_013", "Groundnut Oil 1L",      "OIL-GNT-1L",  "Oils",      5,  12, 155,  "Oil India",        "Moderate",     None),   # LOW STOCK
    ("prod_014", "Desi Ghee 500g",        "GHEE-500G",   "Oils",     18,  10, 385,  "Amul Distributors","Moderate",     None),
    ("prod_015", "Coconut Oil 500ml",     "OIL-CCN-500", "Oils",     40,  10, 130,  "South Agro",       "Low",          None),

    # ── SPICES & CONDIMENTS
    ("prod_016", "Turmeric Powder 200g",  "TURMR-200G",  "Spices",   55,  15, 38,   "Spice World",      "Moderate",     None),
    ("prod_017", "Red Chilli Powder 200g","CHILL-200G",  "Spices",   42,  15, 48,   "Spice World",      "Moderate",     None),
    ("prod_018", "Garam Masala 100g",     "GRMSL-100G",  "Spices",    9,  15, 65,   "Spice World",      "High demand",  None),   # LOW STOCK
    ("prod_019", "Cumin Seeds 100g",      "CUMNS-100G",  "Spices",   33,  10, 42,   "Spice World",      "Low",          None),
    ("prod_020", "Mustard Seeds 200g",    "MUSTR-200G",  "Spices",   25,  10, 35,   "Spice World",      "Low",          None),

    # ── SNACKS & PACKAGED
    ("prod_021", "Maggi Noodles 70g",     "MGGI-70G",    "Packaged",  2,  25, 14,   "HUL Distributors", "High demand",  180),   # CRITICAL LOW STOCK
    ("prod_022", "Biscuits Parle-G 200g", "PRLG-200G",   "Packaged", 60,  20, 10,   "Parle Distributors","High demand",  None),
    ("prod_023", "Poha 500g",             "POHA-500G",   "Grains",   14,  15, 38,   "Agro Direct",      "Moderate",     None),

    # ── BEVERAGES
    ("prod_024", "Tea Dust 250g",         "TEA-250G",    "Beverages", 8,  15, 95,   "Tata Consumer",    "High demand",  None),   # LOW STOCK
    ("prod_025", "Coffee Powder 100g",    "COFF-100G",   "Beverages",20,  10, 130,  "Bru Distributors", "Low",          None),
    ("prod_026", "Sugar 1kg",             "SUGR-1KG",    "Sweeteners",50, 25, 44,   "Sugar Mills",      "High demand",  None),
    ("prod_027", "Jaggery 500g",          "JAGG-500G",   "Sweeteners",11,  15, 55,   "Agro Direct",      "Moderate",     None),   # LOW STOCK

    # ── CLEANING & HYGIENE (different agent category for variety)
    ("prod_028", "Surf Excel 500g",       "SURF-500G",   "Household", 18, 10, 88,   "HUL Distributors", "Low",          None),
    ("prod_029", "Dettol Soap 100g",      "DDTL-100G",   "Hygiene",  30,  15, 45,   "Reckitt",          "Moderate",     None),
    ("prod_030", "Toothpaste 100ml",      "TPST-100ML",  "Hygiene",   3,  10, 62,   "Colgate",          "Moderate",     None),   # LOW STOCK
]


def seed_products():
    """Write all products to Firestore inventory collection."""
    print(f"\n{'='*55}")
    print(f"  Seeding {len(PRODUCTS)} products to Firestore...")
    print(f"{'='*55}")

    batch = db.batch()
    count = 0

    for p in PRODUCTS:
        pid, name, sku, cat, stock, reorder, price, supplier, forecast, expiry_days = p
        doc_ref = db.collection("inventory").document(pid)

        data = {
            "productName":  name,
            "sku":          sku,
            "category":     cat,
            "stock":        stock,
            "reorderLevel": reorder,
            "price":        price,
            "supplier":     supplier,
            "forecast":     forecast,
            "store_id":     "store001",
            "updatedAt":    TODAY.isoformat(),
        }

        if expiry_days is not None:
            data["expiryDate"] = dt(expiry_days)

        batch.set(doc_ref, data, merge=True)
        count += 1

        status = ""
        if stock < reorder:
            status = " ⚠ LOW STOCK"
        if expiry_days is not None and expiry_days <= 5:
            status += f" 🗓 EXPIRES in {expiry_days}d"

        print(f"  [{count:02d}] {name:<30} stock={stock:>3}/{reorder:<3}{status}")

    batch.commit()
    print(f"\n✅ All {count} products written to Firestore.\n")


def trigger_alerts():
    """Run the proactive checks manually to generate alerts right now."""
    print("{'='*55}")
    print("  Running proactive alert checks...")
    print("{'='*55}\n")

    store_id = "store001"

    # Low-stock check
    print("📦 Checking low stock...")
    low = check_low_stock(store_id=store_id)
    print(f"   Found {len(low)} low-stock items:")
    for item in low:
        name = item.get("productName", item.get("product_id", "?"))
        stock = item.get("stock", 0)
        reorder = item.get("reorderLevel", 0)
        sev = "🔴 CRITICAL" if stock == 0 else "🟡 WARNING"
        print(f"   {sev} — {name} (stock={stock}, reorder@{reorder})")
        _write_alert({
            "type": "low_stock",
            "severity": "critical" if stock == 0 else "warning",
            "product_id": item.get("product_id"),
            "product_name": name,
            "message": f"⚠️ {name} stock is {'empty' if stock == 0 else f'low ({stock} units)'}",
            "suggested_action": f"Reorder {name} immediately.",
            "store_id": store_id,
            "dismissed": False,
        })

    print()

    # Near-expiry check
    print("🗓️  Checking near-expiry items...")
    expiring = check_expiry(store_id=store_id)
    print(f"   Found {len(expiring)} near-expiry items:")
    for item in expiring:
        name = item.get("productName", item.get("product_id", "?"))
        days = item.get("days_until_expiry", 0)
        sev = "🔴 CRITICAL" if days < 2 else "🟡 WARNING"
        suggestion = item.get("clearance_suggestion", f"Discount {name} to clear stock.")
        print(f"   {sev} — {name} (expires in {days} day(s))")
        print(f"          → {suggestion}")
        _write_alert({
            "type": "expiry",
            "severity": "critical" if days < 2 else "warning",
            "product_id": item.get("product_id"),
            "product_name": name,
            "message": f"🗓️ {name} expires in {days} day(s)!",
            "suggested_action": suggestion,
            "store_id": store_id,
            "dismissed": False,
        })

    print()
    print("='*55}")
    print(f"✅ Done! Wrote {len(low)} low-stock alerts + {len(expiring)} expiry alerts to proactive_alerts.")
    print(f"   Open your app and check Insights / Dashboard / Agents to see them!")
    print("='*55}\n")


if __name__ == "__main__":
    seed_products()
    trigger_alerts()
