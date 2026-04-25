"""
app/agents/cashflow_agent.py -- Financial tracking and forecasting agent.

Simplified to avoid cascading DB calls that cause timeouts.
Computes inflow/outflow from sales and purchase orders, then estimates
procurement cost using inventory data directly (no agent chaining).
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.models import CustomerSale, PurchaseOrder, Inventory


async def cashflow_agent(db: AsyncSession, store_id: str = "store001") -> dict:
    """
    Computes cash balance from PostgreSQL revenue/expenses and projects
    post-procurement liquidity using low-stock items from the inventory table.
    """
    # ── 1. Calculate Current Cash Balance ─────────────────────────────────────
    # Inflow: revenue from sales
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

    # ── 2. Procurement Cost Estimate (simplified — no agent chaining) ─────────
    # Directly query low-stock items from inventory to avoid cascading calls
    result = await db.execute(
        select(Inventory).where(
            and_(
                Inventory.store_id == store_id,
                Inventory.stock < Inventory.reorder_level,
            )
        )
    )
    low_stock_rows = result.scalars().all()

    estimated_procurement_cost = 0.0
    pending_reorders = []

    for item in low_stock_rows:
        deficit = max(0, float(item.reorder_level) - float(item.stock))
        # Use wholesale_cost if available, otherwise estimate at 60% of retail price
        unit_cost = float(item.wholesale_cost) if item.wholesale_cost else float(item.price or 0) * 0.6
        cost = deficit * unit_cost

        estimated_procurement_cost += cost
        pending_reorders.append({
            "product_id": item.product_id,
            "product_name": item.product_name,
            "current_stock": float(item.stock),
            "reorder_level": float(item.reorder_level),
            "quantity": deficit,
            "estimated_cost": round(cost, 2),
            "supplier": item.supplier or "Unknown",
        })

    post_procurement_balance = balance - estimated_procurement_cost

    return {
        "vendorId": store_id,
        "storeId": store_id,
        "inflow": round(inflow, 2),
        "outflow": round(outflow, 2),
        "balance": round(balance, 2),
        "estimatedProcurementCost": round(estimated_procurement_cost, 2),
        "postProcurementBalance": round(post_procurement_balance, 2),
        "pendingReorders": pending_reorders,
        "lowStockCount": len(pending_reorders),
    }