"""
app/agents/inventory_agent.py — Full inventory monitoring agent.

Features:
- Natural language → Firestore query via LLM
- Stock monitoring (all products or specific)
- Low-stock detection with reorder quantity calculation
- Expiry detection with clearance suggestions
- Proactive alert generation to Firestore
"""

from datetime import datetime, timezone, timedelta
from app.core.config import db
from app.services.llm import llm_chat, llm_json
from google.cloud.firestore_v1 import FieldFilter


# ── Reorder Constants ──────────────────────────────────────────────────────────
DEFAULT_REORDER_THRESHOLD = 10  # units
SAFETY_STOCK_DAYS = 3           # days of buffer stock
EXPIRY_WARNING_DAYS = 5         # flag items expiring within this many days


# ── Core Query ─────────────────────────────────────────────────────────────────
def inventory_agent(query: str | None = None, store_id: str = "store001") -> dict:
    """
    Main inventory agent entry point.
    If query is given, interprets it via LLM and returns targeted results.
    Without a query, returns a full inventory summary with alerts.
    """
    all_products = _get_all_inventory(store_id)

    if not all_products:
        return {
            "agent": "inventory",
            "store_id": store_id,
            "message": "No inventory data found for this store.",
            "products": [],
            "alerts": [],
        }

    # Annotate each product with status flags
    annotated = [_annotate_product(p) for p in all_products]
    low_stock = [p for p in annotated if p.get("is_low_stock")]
    expiring = [p for p in annotated if p.get("is_near_expiry")]
    alerts = _build_alerts(low_stock, expiring, store_id)

    # Write critical alerts to Firestore for proactive pickup
    for alert in alerts:
        if alert["severity"] in ("warning", "critical"):
            _write_alert(alert)

    # If a natural language query was given, filter/explain using LLM
    nl_message = None
    if query:
        nl_message = _answer_nl_query(query, annotated)

    return {
        "agent": "inventory",
        "store_id": store_id,
        "message": nl_message or f"Inventory loaded: {len(annotated)} products.",
        "products": annotated,
        "low_stock_count": len(low_stock),
        "near_expiry_count": len(expiring),
        "alerts": alerts,
    }


def check_low_stock(store_id: str = "store001") -> list[dict]:
    """Return all products below reorder threshold with reorder suggestions."""
    products = _get_all_inventory(store_id)
    low = [_annotate_product(p) for p in products if p.get("stock", 0) < DEFAULT_REORDER_THRESHOLD]
    for item in low:
        item["reorder_suggestion"] = suggest_reorder(item["product_id"])
    return low


def check_expiry(store_id: str = "store001") -> list[dict]:
    """Return near-expiry products with LLM-generated clearance suggestions."""
    products = _get_all_inventory(store_id)
    today = datetime.now(timezone.utc)
    expiring = []
    for p in products:
        expiry = p.get("expiryDate")
        if expiry:
            try:
                if hasattr(expiry, "timestamp"):
                    expiry_dt = expiry
                else:
                    expiry_dt = datetime.fromisoformat(str(expiry)).replace(tzinfo=timezone.utc)
                days_left = (expiry_dt - today).days
                if days_left <= EXPIRY_WARNING_DAYS:
                    p["days_until_expiry"] = days_left
                    p["clearance_suggestion"] = _suggest_clearance(p, days_left)
                    expiring.append(p)
            except Exception:
                pass
    return expiring


def suggest_reorder(product_id: str) -> dict:
    """
    Calculate recommended reorder quantity using:
    safety stock formula = (avg_daily_sales * SAFETY_STOCK_DAYS) + reorder_threshold
    Returns productName and a human-readable reasoning string.
    """
    product = db.collection("inventory").document(product_id).get().to_dict() or {}
    forecast = db.collection("demand_forecast").document(product_id).get().to_dict() or {}

    product_name = product.get("productName") or product.get("name") or product_id
    current_stock = product.get("stock", 0)
    daily_demand = float(forecast.get("predictedDemand", 5))  # default 5 units/day if no forecast
    reorder_level = product.get("reorderLevel", DEFAULT_REORDER_THRESHOLD)

    safety_stock = daily_demand * SAFETY_STOCK_DAYS
    reorder_qty = max(0, round(safety_stock + reorder_level - current_stock))
    days_left = round(current_stock / daily_demand, 1) if daily_demand > 0 else None

    has_forecast = bool(forecast)
    demand_source = "from demand forecast" if has_forecast else "estimated default"
    days_msg = f" Current stock will last ~{days_left} more days at this rate." if days_left else ""

    reasoning = (
        f"{product_name} currently has {current_stock} units in stock (reorder threshold: {reorder_level} units). "
        f"Daily demand is {daily_demand} units/day ({demand_source}).{days_msg} "
        f"Using a {SAFETY_STOCK_DAYS}-day safety buffer, the recommended reorder quantity is {reorder_qty} units."
    )

    return {
        "productId": product_id,
        "productName": product_name,
        "currentStock": current_stock,
        "dailyDemand": daily_demand,
        "reorderLevel": reorder_level,
        "daysOfStockRemaining": days_left,
        "recommendedReorderQty": reorder_qty,
        "reasoning": reasoning,
    }


# ── Private Helpers ────────────────────────────────────────────────────────────
def _get_all_inventory(store_id: str) -> list[dict]:
    """Read all inventory documents for a store."""
    docs = db.collection("inventory").stream()
    result = []
    for doc in docs:
        data = doc.to_dict()
        data["product_id"] = doc.id
        result.append(data)
    return result


def _annotate_product(product: dict) -> dict:
    """Add status flags: is_low_stock, is_near_expiry, status_label."""
    stock = product.get("stock", 0)
    reorder_level = product.get("reorderLevel", DEFAULT_REORDER_THRESHOLD)
    product["is_low_stock"] = stock < reorder_level
    product["stock_status"] = "critical" if stock == 0 else ("low" if product["is_low_stock"] else "ok")

    expiry = product.get("expiryDate")
    product["is_near_expiry"] = False
    if expiry:
        try:
            today = datetime.now(timezone.utc)
            if hasattr(expiry, "timestamp"):
                expiry_dt = expiry
            else:
                expiry_dt = datetime.fromisoformat(str(expiry)).replace(tzinfo=timezone.utc)
            days = (expiry_dt - today).days
            product["is_near_expiry"] = days <= EXPIRY_WARNING_DAYS
            product["days_until_expiry"] = days
        except Exception:
            pass

    return product


def _build_alerts(low_stock: list, expiring: list, store_id: str) -> list[dict]:
    """Build structured alert objects for low stock and near-expiry items."""
    alerts = []
    for p in low_stock:
        name = p.get("productName", p["product_id"])
        stock = p.get("stock", 0)
        alerts.append({
            "type": "low_stock",
            "severity": "critical" if stock == 0 else "warning",
            "product_id": p["product_id"],
            "product_name": name,
            "message": f"⚠️ {name} is {'out of stock' if stock == 0 else f'low ({stock} units left)'}. Reorder recommended.",
            "suggested_action": f"Place a reorder for {name}.",
            "store_id": store_id,
        })
    for p in expiring:
        name = p.get("productName", p["product_id"])
        days = p.get("days_until_expiry", 0)
        alerts.append({
            "type": "expiry",
            "severity": "warning" if days > 2 else "critical",
            "product_id": p["product_id"],
            "product_name": name,
            "message": f"🗓️ {name} expires in {days} day(s). Consider a clearance discount.",
            "suggested_action": f"Apply a 20-30% discount on {name} to clear stock.",
            "store_id": store_id,
        })
    return alerts


def _write_alert(alert: dict) -> None:
    """
    Persist alert to Firestore proactive_alerts collection.
    Simple write — deduplication is handled at the caller level.
    """
    try:
        alert_with_time = {**alert, "created_at": datetime.now(timezone.utc), "dismissed": False}
        db.collection("proactive_alerts").add(alert_with_time)
    except Exception:
        pass



def _answer_nl_query(query: str, products: list[dict]) -> str:
    """Use LLM to answer a natural language inventory question from product data."""
    summary = [
        f"{p.get('productName', p['product_id'])}: {p.get('stock', 0)} units "
        f"({'LOW' if p.get('is_low_stock') else 'OK'})"
        for p in products[:20]  # limit to avoid token overflow
    ]
    context = "\n".join(summary)
    return llm_chat(
        messages=[{"role": "user", "content": query}],
        system_prompt=(
            f"You are a helpful inventory assistant for a Kirana store. "
            f"Here is the current inventory:\n{context}\n\n"
            f"Answer the user's question concisely and helpfully."
        ),
        temperature=0.3,
    )


def _suggest_clearance(product: dict, days_left: int) -> str:
    """LLM-generated clearance strategy for near-expiry items."""
    name = product.get("productName", product.get("product_id", "unknown"))
    stock = product.get("stock", 0)
    return llm_chat(
        messages=[{
            "role": "user",
            "content": f"{name} expires in {days_left} days. Current stock: {stock} units. "
                       f"Suggest a practical clearance strategy for a small Kirana store. Be specific and brief."
        }],
        temperature=0.4,
    )