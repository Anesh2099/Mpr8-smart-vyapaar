"""
app/agents/inventory_agent.py -- Full inventory monitoring agent.

Features:
- Natural language -> PostgreSQL query via LLM
- Stock monitoring (all products or specific)
- Low-stock detection with reorder quantity calculation
- Expiry detection with clearance suggestions
- Proactive alert generation to PostgreSQL via db_service
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm import llm_chat
from app.services.db_service import (
    get_all_inventory,
    get_low_stock_items,
    get_expiring_items,
    get_inventory_item,
    upsert_inventory_item,
    get_forecast,
    upsert_alert,
)


# -- Reorder Constants --------------------------------------------------------
DEFAULT_REORDER_THRESHOLD = 10  # units
SAFETY_STOCK_DAYS = 3           # days of buffer stock
EXPIRY_WARNING_DAYS = 5         # flag items expiring within this many days


# -- ORM row -> plain dict helper ---------------------------------------------
def _row_to_dict(row) -> dict:
    """Convert a SQLAlchemy ORM row to a plain dict for LLM / return payloads."""
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


# -- Core Entry Point ---------------------------------------------------------

async def inventory_agent(
    db: AsyncSession,
    query: Optional[str] = None,
    store_id: str = "store001",
) -> dict:
    """
    Main inventory agent entry point.
    If query is given, interprets it via LLM and returns targeted results.
    Without a query, returns a full inventory summary with alerts.
    """
    all_rows = await get_all_inventory(db, store_id)

    if not all_rows:
        return {
            "agent": "inventory",
            "store_id": store_id,
            "message": "No inventory data found for this store.",
            "products": [],
            "alerts": [],
        }

    all_products = [_row_to_dict(r) for r in all_rows]

    # Annotate each product with status flags
    annotated = [_annotate_product(p) for p in all_products]
    low_stock = [p for p in annotated if p.get("is_low_stock")]
    expiring = [p for p in annotated if p.get("is_near_expiry")]
    alerts = _build_alerts(low_stock, expiring, store_id)

    # Persist critical alerts to PostgreSQL for proactive pickup
    for alert in alerts:
        if alert["severity"] in ("warning", "critical"):
            await _write_alert(db, alert)

    # If a natural language query was given, filter/explain using LLM
    nl_message = None
    if query:
        nl_message = await _answer_nl_query(query, annotated)

    return {
        "agent": "inventory",
        "store_id": store_id,
        "message": nl_message or f"Inventory loaded: {len(annotated)} products.",
        "products": annotated,
        "low_stock_count": len(low_stock),
        "near_expiry_count": len(expiring),
        "alerts": alerts,
    }


async def check_low_stock(db: AsyncSession, store_id: str = "store001") -> list[dict]:
    """Return all products below reorder threshold with reorder suggestions."""
    rows = await get_low_stock_items(db, store_id)
    low = [_annotate_product(_row_to_dict(r)) for r in rows]
    for item in low:
        item["reorder_suggestion"] = await suggest_reorder(
            db, item["product_id"], store_id
        )
    return low


async def check_expiry(db: AsyncSession, store_id: str = "store001") -> list[dict]:
    """Return near-expiry products with LLM-generated clearance suggestions."""
    rows = await get_expiring_items(db, store_id, days=EXPIRY_WARNING_DAYS)
    expiring = []
    today = datetime.now(timezone.utc)
    tasks = []
    products = []
    for row in rows:
        p = _row_to_dict(row)
        expiry = p.get("expiry_date")
        if expiry:
            try:
                if hasattr(expiry, "tzinfo") and expiry.tzinfo is None:
                    expiry_dt = expiry.replace(tzinfo=timezone.utc)
                else:
                    expiry_dt = expiry
                days_left = (expiry_dt - today).days
                p["days_until_expiry"] = days_left
                products.append(p)
                tasks.append(_suggest_clearance(p, days_left))
            except Exception:
                pass
    if tasks:
        suggestions = await asyncio.gather(*tasks)
        for p, suggestion in zip(products, suggestions):
            p["clearance_suggestion"] = suggestion
            expiring.append(p)
    return expiring


async def suggest_reorder(
    db: AsyncSession,
    product_id: str,
    store_id: str = "store001",
) -> dict:
    """
    Calculate recommended reorder quantity using:
    safety stock formula = (avg_daily_sales * SAFETY_STOCK_DAYS) + reorder_threshold
    Returns product_name and a human-readable reasoning string.
    """
    product_row = await get_inventory_item(db, store_id, product_id)
    product = _row_to_dict(product_row) if product_row else {}

    # Fetch demand forecast (first matching row for this store+product)
    forecast_rows = await get_forecast(db, store_id)
    forecast = next(
        (f for f in forecast_rows if f.product_id == product_id), None
    )

    product_name = product.get("product_name") or product_id
    current_stock = float(product.get("stock", 0))
    daily_demand = float(
        forecast.predicted_demand if forecast else 5  # default 5 units/day
    )
    reorder_level = float(product.get("reorder_level", DEFAULT_REORDER_THRESHOLD))

    safety_stock = daily_demand * SAFETY_STOCK_DAYS
    reorder_qty = max(0, round(safety_stock + reorder_level - current_stock))
    days_left = round(current_stock / daily_demand, 1) if daily_demand > 0 else None

    demand_source = "from demand forecast" if forecast else "estimated default"
    days_msg = (
        f" Current stock will last ~{days_left} more days at this rate."
        if days_left is not None
        else ""
    )

    reasoning = (
        f"{product_name} currently has {current_stock} units in stock "
        f"(reorder threshold: {reorder_level} units). "
        f"Daily demand is {daily_demand} units/day ({demand_source}).{days_msg} "
        f"Using a {SAFETY_STOCK_DAYS}-day safety buffer, "
        f"the recommended reorder quantity is {reorder_qty} units."
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


# -- Private Helpers ----------------------------------------------------------

def _annotate_product(product: dict) -> dict:
    """Add status flags: is_low_stock, is_near_expiry, stock_status."""
    stock = float(product.get("stock", 0))
    reorder_level = float(
        product.get("reorder_level") or product.get("reorderLevel") or DEFAULT_REORDER_THRESHOLD
    )
    product["is_low_stock"] = stock < reorder_level
    product["stock_status"] = (
        "critical" if stock == 0 else ("low" if product["is_low_stock"] else "ok")
    )

    expiry = product.get("expiry_date") or product.get("expiryDate")
    product["is_near_expiry"] = False
    if expiry:
        try:
            today = datetime.now(timezone.utc)
            if hasattr(expiry, "tzinfo") and expiry.tzinfo is None:
                expiry_dt = expiry.replace(tzinfo=timezone.utc)
            elif hasattr(expiry, "tzinfo"):
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
        name = p.get("product_name") or p.get("productName") or p["product_id"]
        stock = float(p.get("stock", 0))
        alerts.append({
            "type": "low_stock",
            "severity": "critical" if stock == 0 else "warning",
            "product_id": str(p["product_id"]),
            "product_name": name,
            "message": (
                f"{name} is {'out of stock' if stock == 0 else f'low ({stock} units left)'}."
                f" Reorder recommended."
            ),
            "suggested_action": f"Place a reorder for {name}.",
            "store_id": store_id,
        })
    for p in expiring:
        name = p.get("product_name") or p.get("productName") or p["product_id"]
        days = p.get("days_until_expiry", 0)
        alerts.append({
            "type": "expiry",
            "severity": "warning" if days > 2 else "critical",
            "product_id": str(p["product_id"]),
            "product_name": name,
            "message": (
                f"{name} expires in {days} day(s). Consider a clearance discount."
            ),
            "suggested_action": f"Apply a 20-30% discount on {name} to clear stock.",
            "store_id": store_id,
        })
    return alerts


async def _write_alert(db: AsyncSession, alert: dict) -> None:
    """Persist alert to PostgreSQL proactive_alerts via db_service (deduplicating upsert)."""
    try:
        await upsert_alert(
            db=db,
            store_id=alert["store_id"],
            alert_type=alert["type"],
            product_id=alert.get("product_id"),
            product_name=alert.get("product_name"),
            message=alert["message"],
            severity=alert.get("severity"),
            suggested_action=alert.get("suggested_action"),
        )
    except Exception:
        pass


async def _answer_nl_query(query: str, products: list[dict]) -> str:
    """Use LLM to answer a natural language inventory question from product data."""
    summary = [
        f"{p.get('product_name') or p.get('productName') or p['product_id']}: "
        f"{p.get('stock', 0)} units "
        f"({'LOW' if p.get('is_low_stock') else 'OK'})"
        for p in products[:20]  # limit to avoid token overflow
    ]
    context = "\n".join(summary)
    return await llm_chat(
        messages=[{"role": "user", "content": query}],
        system_prompt=(
            f"You are a helpful inventory assistant for a Kirana store. "
            f"Here is the current inventory:\n{context}\n\n"
            f"Answer the user's question concisely and helpfully."
        ),
        temperature=0.3,
    )


async def _suggest_clearance(product: dict, days_left: int) -> str:
    """LLM-generated clearance strategy for near-expiry items."""
    name = product.get("product_name") or product.get("productName") or product.get("product_id", "unknown")
    stock = product.get("stock", 0)
    return await llm_chat(
        messages=[{
            "role": "user",
            "content": (
                f"{name} expires in {days_left} days. Current stock: {stock} units. "
                f"Suggest a practical clearance strategy for a small Kirana store. Be specific and brief."
            ),
        }],
        temperature=0.4,
    )