"""
app/agents/cashflow_agent.py -- Cashflow summary agent.

Computes inflow/outflow balance from customer_sales (revenue)
and purchase_orders (expenses) via PostgreSQL.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from app.services.db_service import get_all_sales, get_all_suppliers


async def cashflow_agent(db: AsyncSession, store_id: str = "store001") -> dict:
    """
    Compute a simple cash balance from:
      inflow  = sum of all customer_sales totals
      outflow = sum of all purchase_order total_amounts

    Returns the same shape as before so master_agent doesn't break.
    """
    from sqlalchemy import select
    from app.models import CustomerSale, PurchaseOrder

    # Inflow: revenue from sales
    from sqlalchemy import func
    from app.core.database import AsyncSessionLocal

    inflow_result = await db.execute(
        select(func.coalesce(func.sum(CustomerSale.total), 0.0))
        .where(CustomerSale.store_id == store_id)
    )
    inflow = float(inflow_result.scalar() or 0.0)

    # Outflow: cost of purchase orders
    outflow_result = await db.execute(
        select(func.coalesce(func.sum(PurchaseOrder.total_amount), 0.0))
        .where(PurchaseOrder.store_id == store_id)
    )
    outflow = float(outflow_result.scalar() or 0.0)

    balance = inflow - outflow

    return {
        "vendorId": store_id,
        "storeId": store_id,
        "inflow": round(inflow, 2),
        "outflow": round(outflow, 2),
        "balance": round(balance, 2),
    }