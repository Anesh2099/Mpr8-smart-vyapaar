"""
app/agents/proactive_agent.py -- Background monitoring job.

Runs at application startup and periodically checks:
- Low stock items  -> writes alerts to PostgreSQL via upsert_alert
- Near-expiry items -> generates clearance suggestions -> writes alerts

Uses FastAPI lifespan context for clean startup/shutdown.
"""

import asyncio
import logging

from app.core.database import AsyncSessionLocal
from app.agents.inventory_agent import check_low_stock, check_expiry, _write_alert

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 3600  # Run every hour
INITIAL_DELAY_SECONDS = 60     # Wait 60s after startup before first check


async def run_proactive_monitoring() -> None:
    """
    Background async task: runs stock + expiry checks every hour.
    Writes critical alerts to PostgreSQL proactive_alerts table.
    """
    # Wait before first check so startup requests aren't starved of DB connections
    await asyncio.sleep(INITIAL_DELAY_SECONDS)

    while True:
        try:
            await asyncio.wait_for(_run_checks(), timeout=30)
        except asyncio.TimeoutError:
            logger.warning("Proactive check timed out after 30s, skipping cycle")
        except Exception as e:
            logger.warning(f"Proactive check failed: {e}")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


async def _run_checks() -> None:
    """Async check logic — opens its own DB session for the background job."""
    store_id = "store001"

    async with AsyncSessionLocal() as db:
        # Low-stock check
        try:
            low = await check_low_stock(db, store_id=store_id)
        except Exception:
            low = []

        for item in low:
            try:
                name  = item.get("product_name") or item.get("productName") or item.get("product_id", "?")
                stock = float(item.get("stock", 0))
                await _write_alert(db, {
                    "type":             "low_stock",
                    "severity":         "critical" if stock == 0 else "warning",
                    "product_id":       str(item.get("product_id", "")),
                    "product_name":     name,
                    "message":          f"{name} stock is {'empty' if stock == 0 else f'low ({stock} units)'}",
                    "suggested_action": f"Reorder {name} now.",
                    "store_id":         store_id,
                })
            except Exception:
                pass

        # Near-expiry check
        try:
            expiring = await check_expiry(db, store_id=store_id)
        except Exception:
            expiring = []

        for item in expiring:
            try:
                name = item.get("product_name") or item.get("productName") or item.get("product_id", "?")
                days = item.get("days_until_expiry", 0)
                await _write_alert(db, {
                    "type":             "expiry",
                    "severity":         "critical" if days < 2 else "warning",
                    "product_id":       str(item.get("product_id", "")),
                    "product_name":     name,
                    "message":          f"{name} expires in {days} day(s).",
                    "suggested_action": item.get(
                        "clearance_suggestion",
                        f"Discount {name} to clear stock.",
                    ),
                    "store_id":         store_id,
                })
            except Exception:
                pass

