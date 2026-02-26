"""
app/agents/supplier_agent.py — Full supplier discovery, comparison & ordering agent.

Features:
- Supplier discovery from Firestore `suppliers` collection
- Natural language command parsing (product, quantity, budget)
- Price comparison and ranking
- LLM-generated negotiation draft messages
- LLM-generated order confirmation drafts
- Supplier interaction logging to Firestore
"""

from datetime import datetime, timezone
from app.core.config import db
from app.services.llm import llm_chat, llm_json


# ── Main Entry Point ───────────────────────────────────────────────────────────
def supplier_agent(
    product_id: str | None = None,
    product_name: str | None = None,
    quantity: int | None = None,
    budget: float | None = None,
    query: str | None = None,
) -> dict:
    """
    Main supplier agent. Can be called directly with structured args
    or with a raw NL query that gets parsed first.
    """
    # Parse NL query if given
    if query and not product_name:
        parsed = _parse_supplier_command(query)
        product_name = parsed.get("product_name") or product_name
        quantity = parsed.get("quantity") or quantity
        budget = parsed.get("budget") or budget

    # Resolve product_name from inventory if only product_id given
    if product_id and not product_name:
        inv = db.collection("inventory").document(product_id).get().to_dict() or {}
        product_name = inv.get("productName", product_id)
        if not quantity:
            # Suggest from demand forecast
            fc = db.collection("demand_forecast").document(product_id).get().to_dict() or {}
            quantity = fc.get("predictedDemand", 10)
        if not budget:
            price = inv.get("price", 0)
            budget = price * (quantity or 10) * 1.2  # 20% margin on cost

    if not product_name:
        return {"agent": "supplier", "error": "Could not determine product to find suppliers for."}

    # Discover and rank suppliers
    suppliers = discover_suppliers(product_name)
    if not suppliers:
        return {
            "agent": "supplier",
            "product": product_name,
            "message": f"No suppliers found for '{product_name}'. You may need to add suppliers to the database.",
            "suppliers": [],
            "action_cards": [],
        }

    ranked = compare_prices(suppliers, budget)
    best = ranked[0] if ranked else None

    action_cards = []
    if best:
        within_budget = budget is None or best.get("price_per_unit", 0) * (quantity or 1) <= budget
        if within_budget:
            draft = draft_interest_message(best, product_name, quantity)
            action_type = "draft_interest"
        else:
            draft = draft_negotiation_message(best, product_name, quantity, budget)
            action_type = "draft_negotiation"

        order_summary = draft_order_confirmation(best, product_name, quantity)

        action_cards = [
            {
                "type": action_type,
                "title": f"Message for {best.get('supplierName', 'Supplier')}",
                "data": {"message_draft": draft, "supplier": best}
            },
            {
                "type": "draft_order",
                "title": "Draft Purchase Order",
                "data": order_summary
            }
        ]

        # Log the interaction
        log_supplier_interaction(
            supplier_id=best.get("supplier_id", ""),
            product_name=product_name,
            quantity=quantity,
            budget=budget,
            action=action_type,
            draft=draft,
        )

    return {
        "agent": "supplier",
        "product": product_name,
        "quantity_needed": quantity,
        "budget": budget,
        "message": f"Found {len(ranked)} supplier(s) for {product_name}. Best option: {best.get('supplierName') if best else 'N/A'}.",
        "ranked_suppliers": ranked,
        "action_cards": action_cards,
    }


# ── Discovery & Comparison ─────────────────────────────────────────────────────
def discover_suppliers(product_name: str) -> list[dict]:
    """Fetch suppliers from Firestore that carry a given product."""
    try:
        # Search by product tags or name (partial match via array-contains or exact field)
        docs = db.collection("suppliers").stream()
        result = []
        product_lower = product_name.lower()
        for doc in docs:
            data = doc.to_dict()
            data["supplier_id"] = doc.id
            # Match by products list or name
            products = [str(p).lower() for p in data.get("products", [])]
            if any(product_lower in p or p in product_lower for p in products):
                result.append(data)
        return result
    except Exception:
        return []


def compare_prices(suppliers: list[dict], budget: float | None = None) -> list[dict]:
    """Rank suppliers by price (cheapest first). Annotate budget status."""
    for s in suppliers:
        price = s.get("price_per_unit", s.get("pricePerUnit", 0))
        s["price_per_unit"] = price
        s["within_budget"] = True if budget is None else price <= budget
        s["reliability_score"] = s.get("reliability", 3)  # 1-5 stars
    return sorted(suppliers, key=lambda s: (not s["within_budget"], s["price_per_unit"]))


# ── Draft Generation ───────────────────────────────────────────────────────────
def draft_interest_message(supplier: dict, product: str, quantity: int | None) -> str:
    name = supplier.get("supplierName", "Supplier")
    qty_str = f"{quantity} units of " if quantity else ""
    return llm_chat(
        messages=[{
            "role": "user",
            "content": (
                f"Write a short, professional WhatsApp message to a supplier named '{name}' "
                f"expressing interest in purchasing {qty_str}{product}. "
                f"Mention the price of ₹{supplier.get('price_per_unit', '?')}/unit. "
                f"Keep it under 60 words, friendly but professional."
            )
        }],
        temperature=0.5,
    )


def draft_negotiation_message(
    supplier: dict, product: str, quantity: int | None, budget: float | None
) -> str:
    name = supplier.get("supplierName", "Supplier")
    qty_str = f"{quantity} units of " if quantity else ""
    budget_str = f"₹{budget}" if budget else "our budget"
    return llm_chat(
        messages=[{
            "role": "user",
            "content": (
                f"Write a short negotiation WhatsApp message to supplier '{name}'. "
                f"We want to buy {qty_str}{product}. "
                f"Their price is ₹{supplier.get('price_per_unit', '?')}/unit but our budget is {budget_str}. "
                f"Request a discount politely. Under 70 words."
            )
        }],
        temperature=0.5,
    )


def draft_order_confirmation(supplier: dict, product: str, quantity: int | None) -> dict:
    qty = quantity or 1
    price = supplier.get("price_per_unit", 0)
    total = qty * price
    return {
        "supplier": supplier.get("supplierName", "Unknown"),
        "product": product,
        "quantity": qty,
        "price_per_unit": price,
        "total_cost": total,
        "contact": supplier.get("contact", "N/A"),
        "estimated_delivery": supplier.get("leadTimeDays", "3-5") ,
        "order_status": "draft",
    }


# ── Interaction Logging ────────────────────────────────────────────────────────
def log_supplier_interaction(
    supplier_id: str,
    product_name: str,
    quantity: int | None,
    budget: float | None,
    action: str,
    draft: str,
) -> None:
    try:
        db.collection("supplier_interactions").add({
            "supplier_id": supplier_id,
            "product_name": product_name,
            "quantity": quantity,
            "budget": budget,
            "action": action,
            "draft_message": draft,
            "timestamp": datetime.now(timezone.utc),
        })
    except Exception:
        pass


# ── NL Command Parser ──────────────────────────────────────────────────────────
def _parse_supplier_command(query: str) -> dict:
    """Extract product, quantity, budget from a natural language command."""
    return llm_json(
        messages=[{"role": "user", "content": query}],
        system_prompt=(
            "Extract supplier-related information from the user message. "
            "Return JSON: {\"product_name\": str|null, \"quantity\": int|null, \"budget\": float|null}"
        ),
        temperature=0,
        fallback={"product_name": None, "quantity": None, "budget": None},
    )