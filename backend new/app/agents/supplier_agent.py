"""
app/agents/supplier_agent.py -- Full supplier discovery, comparison & ordering agent.

Features:
- Supplier discovery from PostgreSQL suppliers table via db_service
- Natural language command parsing (product, quantity, budget)
- Price comparison and ranking
- LLM-generated negotiation draft messages
- LLM-generated order confirmation drafts
- Firestore interaction logging removed; decisions are printed/returned only
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.db_service import (
    get_all_suppliers,
    search_suppliers_by_product,
    get_inventory_item,
    get_forecast,
)
from app.services.llm import llm_chat, llm_json


# -- Main Entry Point ---------------------------------------------------------

async def supplier_agent(
    db: AsyncSession,
    store_id: str = "store001",
    product_id: Optional[str] = None,
    product_name: Optional[str] = None,
    quantity: Optional[int] = None,
    budget: Optional[float] = None,
    query: Optional[str] = None,
) -> dict:
    """
    Main supplier agent. Can be called directly with structured args
    or with a raw NL query that gets parsed first.
    """
    # Parse NL query if given
    if query and not product_name:
        parsed = _parse_supplier_command(query)
        product_name = parsed.get("product_name") or product_name
        quantity      = parsed.get("quantity") or quantity
        budget        = parsed.get("budget") or budget

    # Resolve product_name from inventory if only product_id given
    if product_id and not product_name:
        inv_row = await get_inventory_item(db, store_id, product_id)
        if inv_row:
            product_name = inv_row.product_name
            if not quantity:
                # Suggest from demand forecast
                forecast_rows = await get_forecast(db, store_id)
                fc = next(
                    (f for f in forecast_rows if str(f.product_id) == str(product_id)),
                    None,
                )
                quantity = int(fc.predicted_demand) if fc else 10
            if not budget:
                price = float(inv_row.price or 0)
                budget = price * (quantity or 10) * 1.2  # 20% margin on cost

    if not product_name:
        return {"agent": "supplier", "error": "Could not determine product to find suppliers for."}

    # Discover and rank suppliers
    suppliers = await discover_suppliers(db, store_id, product_name)
    if not suppliers:
        return {
            "agent": "supplier",
            "product": product_name,
            "message": (
                f"No suppliers found for '{product_name}'. "
                f"You may need to add suppliers to the database."
            ),
            "suppliers": [],
            "action_cards": [],
        }

    ranked = compare_prices(suppliers, budget)
    best = ranked[0] if ranked else None

    action_cards = []
    if best:
        within_budget = budget is None or best.get("price_per_unit", 0) * (quantity or 1) <= budget
        if within_budget:
            draft = await draft_interest_message(best, product_name, quantity)
            action_type = "draft_interest"
        else:
            draft = await draft_negotiation_message(best, product_name, quantity, budget)
            action_type = "draft_negotiation"

        order_summary = draft_order_confirmation(best, product_name, quantity)

        action_cards = [
            {
                "type": action_type,
                "title": f"Message for {best.get('supplier_name', 'Supplier')}",
                "data": {"message_draft": draft, "supplier": best},
            },
            {
                "type": "draft_order",
                "title": "Draft Purchase Order",
                "data": order_summary,
            },
        ]

    return {
        "agent": "supplier",
        "product": product_name,
        "quantity_needed": quantity,
        "budget": budget,
        "message": (
            f"Found {len(ranked)} supplier(s) for {product_name}. "
            f"Best option: {best.get('supplier_name') if best else 'N/A'}."
        ),
        "ranked_suppliers": ranked,
        "action_cards": action_cards,
    }


# -- Discovery & Comparison ---------------------------------------------------

async def discover_suppliers(
    db: AsyncSession,
    store_id: str,
    product_name: str,
) -> list[dict]:
    """Fetch suppliers that carry a given product (PostgreSQL GIN index search)."""
    try:
        rows = await search_suppliers_by_product(db, store_id, product_name)

        # Fallback: if GIN search returns nothing, do a client-side substring match
        if not rows:
            all_rows = await get_all_suppliers(db, store_id)
            product_lower = product_name.lower()
            rows = [
                r for r in all_rows
                if any(
                    product_lower in str(p).lower() or str(p).lower() in product_lower
                    for p in (r.products or [])
                )
            ]

        result = []
        for row in rows:
            result.append({
                "supplier_id": str(row.id),
                "supplier_name": row.supplier_name,
                "products": row.products or [],
                "price_per_unit": float(row.price_per_unit or 0),
                "reliability": float(row.reliability or 3),
                "contact": row.contact,
                "lead_time_days": row.lead_time_days,
            })
        return result
    except Exception:
        return []


def compare_prices(
    suppliers: list[dict],
    budget: Optional[float] = None,
) -> list[dict]:
    """Rank suppliers by price (cheapest first). Annotate budget status."""
    for s in suppliers:
        price = s.get("price_per_unit", 0)
        s["price_per_unit"]    = price
        s["within_budget"]     = True if budget is None else price <= budget
        s["reliability_score"] = s.get("reliability", 3)  # 1-5 stars
    return sorted(suppliers, key=lambda s: (not s["within_budget"], s["price_per_unit"]))


# -- Draft Generation ---------------------------------------------------------

async def draft_interest_message(
    supplier: dict,
    product: str,
    quantity: Optional[int],
) -> str:
    name    = supplier.get("supplier_name", "Supplier")
    qty_str = f"{quantity} units of " if quantity else ""
    return await llm_chat(
        messages=[{
            "role": "user",
            "content": (
                f"Write a short, professional WhatsApp message to a supplier named '{name}' "
                f"expressing interest in purchasing {qty_str}{product}. "
                f"Mention the price of Rs.{supplier.get('price_per_unit', '?')}/unit. "
                f"Keep it under 60 words, friendly but professional."
            ),
        }],
        temperature=0.5,
    )


async def draft_negotiation_message(
    supplier: dict,
    product: str,
    quantity: Optional[int],
    budget: Optional[float],
) -> str:
    name       = supplier.get("supplier_name", "Supplier")
    qty_str    = f"{quantity} units of " if quantity else ""
    budget_str = f"Rs.{budget}" if budget else "our budget"
    return await llm_chat(
        messages=[{
            "role": "user",
            "content": (
                f"Write a short negotiation WhatsApp message to supplier '{name}'. "
                f"We want to buy {qty_str}{product}. "
                f"Their price is Rs.{supplier.get('price_per_unit', '?')}/unit "
                f"but our budget is {budget_str}. "
                f"Request a discount politely. Under 70 words."
            ),
        }],
        temperature=0.5,
    )


def draft_order_confirmation(
    supplier: dict,
    product: str,
    quantity: Optional[int],
) -> dict:
    qty   = quantity or 1
    price = supplier.get("price_per_unit", 0)
    total = qty * price
    return {
        "supplier":           supplier.get("supplier_name", "Unknown"),
        "product":            product,
        "quantity":           qty,
        "price_per_unit":     price,
        "total_cost":         total,
        "contact":            supplier.get("contact", "N/A"),
        "estimated_delivery": supplier.get("lead_time_days", "3-5"),
        "order_status":       "draft",
    }


# -- NL Command Parser --------------------------------------------------------

async def _parse_supplier_command(query: str) -> dict:
    """Extract product, quantity, budget from a natural language command."""
    return await llm_json(
        messages=[{"role": "user", "content": query}],
        system_prompt=(
            "Extract supplier-related information from the user message. "
            'Return JSON: {"product_name": str|null, "quantity": int|null, "budget": float|null}'
        ),
        temperature=0,
        fallback={"product_name": None, "quantity": None, "budget": None},
    )