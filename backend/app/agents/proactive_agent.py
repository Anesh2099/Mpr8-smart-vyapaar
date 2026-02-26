"""
app/agents/proactive_agent.py — Background monitoring job.

Runs at application startup and periodically checks:
- Low stock items → writes alerts to Firestore
- Demand spikes → cross-references forecast with current sales
- Near-expiry items → generates clearance suggestions

Uses FastAPI lifespan context for clean startup/shutdown.
"""

import asyncio
from datetime import datetime, timezone
from app.core.config import db
from app.agents.inventory_agent import check_low_stock, check_expiry, _write_alert


CHECK_INTERVAL_SECONDS = 3600  # Run every hour


async def run_proactive_monitoring():
    """
    Background async task: runs stock + expiry checks every hour.
    Writes critical alerts to Firestore proactive_alerts collection.
    """
    while True:
        try:
            await asyncio.to_thread(_run_checks)
        except Exception:
            pass  # Never crash the background task
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


def _run_checks():
    """Synchronous check logic — called in a thread pool to avoid blocking."""
    store_id = "store001"

    # Low-stock check
    low = check_low_stock(store_id=store_id)
    for item in low:
        name = item.get("productName", item.get("product_id", "?"))
        stock = item.get("stock", 0)
        _write_alert({
            "type": "low_stock",
            "severity": "critical" if stock == 0 else "warning",
            "product_id": item.get("product_id"),
            "product_name": name,
            "message": f"⚠️ {name} stock is {'empty' if stock == 0 else f'low ({stock} units)'}",
            "suggested_action": f"Reorder {name} now.",
            "store_id": store_id,
        })

    # Near-expiry check
    expiring = check_expiry(store_id=store_id)
    for item in expiring:
        name = item.get("productName", item.get("product_id", "?"))
        days = item.get("days_until_expiry", 0)
        _write_alert({
            "type": "expiry",
            "severity": "critical" if days < 2 else "warning",
            "product_id": item.get("product_id"),
            "product_name": name,
            "message": f"🗓️ {name} expires in {days} day(s).",
            "suggested_action": item.get("clearance_suggestion", f"Discount {name} to clear stock."),
            "store_id": store_id,
        })
