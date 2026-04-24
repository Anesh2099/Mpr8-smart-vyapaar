"""
app/agents/master_agent.py -- Full Orchestrator + Conversational Interface.

Features:
- Maintains conversation context via in-memory conversation store
- Rich intent detection with entity extraction
- Multi-agent routing and chaining (inventory -> forecast -> supplier chain)
- Error handling with human-friendly messages
- Proactive alerts available via dedicated /agent/alerts endpoint
- Structured response: message + agent_trace + action_cards + alerts
- Human-in-the-loop: generates drafts, never auto-executes
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models import AIResponseLog
from app.agents.intent_agent import detect_intent
from app.agents.inventory_agent import inventory_agent
from app.agents.forecast_agent import forecast_agent
from app.agents.pricing_agent import pricing_agent
from app.agents.cashflow_agent import cashflow_agent
from app.agents.supplier_agent import supplier_agent
from app.services.conversation_store import (
    get_history, append_message, format_history_for_llm
)
from app.services.db_service import get_active_alerts, get_all_inventory, get_low_stock_items
from app.services.llm import llm_chat


async def assistant_agent(
    db: AsyncSession,
    query: str,
    session_id: str = "default",
    store_id: str = "store001",
) -> dict:
    """
    Main orchestrator entry point. Accepts a natural language query,
    routes it to the correct agent(s), and returns a structured response.
    """
    agent_trace = []

    # 1. Load conversation history for context
    history         = get_history(session_id)
    history_for_llm = format_history_for_llm(history)

    # 2. Detect intent with conversation context
    event_start_time = datetime.utcnow()
    agent_trace.append("intent_classifier")
    intent_data  = await detect_intent(query, conversation_history=history_for_llm)
    intent       = intent_data.get("intent", "general")
    product_id   = intent_data.get("productId") or await _resolve_product_id(
        db, store_id, intent_data.get("productName")
    )
    product_name = intent_data.get("productName")
    vendor_id    = intent_data.get("vendorId") or "vendor001"
    quantity     = intent_data.get("quantity")
    budget       = intent_data.get("budget")

    # 3. Store user message in history
    append_message(session_id, "user", query)

    # 4. Route to agent(s)
    response_data = {}
    action_cards  = []
    message       = ""

    try:
        if intent in ("inventory", "reorder"):
            agent_trace.append("inventory_agent")
            result       = await inventory_agent(db, query=query, store_id=store_id)
            response_data = result

            # Chain: if low stock found, also run forecast + supplier for top item
            if result.get("low_stock_count", 0) > 0 and product_id:
                agent_trace.append("forecast_agent")
                fc = await forecast_agent(db, product_id)
                agent_trace.append("supplier_agent")
                sup = await supplier_agent(
                    db,
                    store_id=store_id,
                    product_id=product_id,
                    product_name=product_name,
                    quantity=quantity,
                    budget=budget,
                )
                response_data["forecast"] = fc
                response_data["supplier"] = sup
                action_cards.extend(sup.get("action_cards", []))

            message = result.get("message", "Here is your inventory status.")

        elif intent == "forecast":
            agent_trace.append("forecast_agent")
            if not product_id:
                # No specific product — give a summary of all forecasts + inventory
                agent_trace.append("inventory_agent")
                inv_result = await inventory_agent(db, query=query, store_id=store_id)

                # Build a helpful summary using live data
                products = inv_result.get("products", [])
                low_stock = [p for p in products if p.get("is_low_stock")]
                total = len(products)

                summary_lines = [f"Here's an overview of your store's demand outlook across {total} products:"]

                if low_stock:
                    summary_lines.append(f"\n⚠️ **{len(low_stock)} items are below reorder level:**")
                    for p in low_stock[:5]:
                        name = p.get("product_name", p.get("product_id", "?"))
                        stock = p.get("stock", 0)
                        summary_lines.append(f"  • {name}: {stock} units remaining")
                    if len(low_stock) > 5:
                        summary_lines.append(f"  ...and {len(low_stock) - 5} more")

                summary_lines.append(
                    "\nTo get a detailed forecast for a specific product, ask me: "
                    "\"Forecast demand for [product name]\""
                )

                message = "\n".join(summary_lines)
                response_data = inv_result

            else:
                result        = await forecast_agent(db, product_id)
                response_data = result
                message       = _explain_forecast(result)

        elif intent == "pricing":
            agent_trace.append("pricing_agent")
            if not product_id:
                # No specific product — give a helpful overview
                inv_rows = await get_all_inventory(db, store_id)
                total = len(inv_rows) if inv_rows else 0
                message = (
                    f"I can give you AI-powered pricing recommendations for any of your {total} products. "
                    f"Just ask: \"What should I price [product name]?\" or visit the Pricing page for a full overview."
                )
                response_data = {"total_products": total}
            else:
                result        = await pricing_agent(db, product_id, store_id=store_id)
                response_data = result
                message       = result.get(
                    "explanation",
                    f"Recommended price for {product_name or product_id}: Rs.{result.get('recommendedPrice', 'N/A')}",
                )
                if result.get("promotionSuggestion"):
                    action_cards.append({
                        "type":  "promotion",
                        "title": "Promotion Suggestion",
                        "data":  {"suggestion": result["promotionSuggestion"]},
                    })

        elif intent == "cashflow":
            agent_trace.append("cashflow_agent")
            result        = await cashflow_agent(db, store_id=store_id)
            response_data = result
            balance       = result.get("balance", 0)
            message       = (
                f"Your current cash balance is Rs.{balance:,.0f}. "
                f"{'Finances look healthy.' if balance > 5000 else 'Low balance -- consider delaying non-urgent reorders.'}"
            )

        elif intent == "supplier":
            agent_trace.append("supplier_agent")

            # If user didn't mention a product, ask them or auto-suggest
            if not product_name and not product_id:
                # Try to find the most urgently needed product from low stock
                try:
                    low_rows = await get_low_stock_items(db, store_id)
                except Exception:
                    low_rows = []

                if low_rows:
                    # Auto-suggest the lowest-stock item
                    top = low_rows[0]
                    auto_product = getattr(top, 'product_name', '') or ''
                    auto_pid = getattr(top, 'product_id', '') or ''
                    if auto_product:
                        product_name = auto_product
                        product_id = auto_pid
                        message_prefix = (
                            f"Since you didn't specify a product, I'm searching suppliers for "
                            f"your most urgent item: **{auto_product}** (low stock).\n\n"
                        )
                    else:
                        message = (
                            "Which product do you need suppliers for? "
                            "Tell me something like: \"Find supplier for rice\" or \"Order 50 units of milk\""
                        )
                        response_data = {"hint": "specify_product"}
                        append_message(session_id, "assistant", message)
                        return _build_response(message, intent, agent_trace, action_cards, response_data, intent_data, session_id)
                else:
                    message = (
                        "Which product do you need suppliers for? "
                        "All your inventory looks healthy right now. "
                        "Try: \"Find supplier for [product name]\""
                    )
                    response_data = {"hint": "specify_product"}
                    append_message(session_id, "assistant", message)
                    return _build_response(message, intent, agent_trace, action_cards, response_data, intent_data, session_id)
            else:
                message_prefix = ""

            result = await supplier_agent(
                db,
                store_id=store_id,
                product_id=product_id,
                product_name=product_name,
                quantity=quantity,
                budget=budget,
                query=query,
            )
            response_data = result
            action_cards.extend(result.get("action_cards", []))

            # Build a rich message
            ranked = result.get("ranked_suppliers", [])
            if ranked:
                lines = [f"{message_prefix}Found {len(ranked)} supplier(s) for **{product_name or result.get('product', '?')}**:\n"]
                for i, s in enumerate(ranked[:3], 1):
                    name = s.get("supplier_name", "Unknown")
                    price = s.get("price_per_unit", 0)
                    reliability = s.get("reliability_score", 0)
                    stars = "⭐" * int(reliability)
                    lines.append(f"{i}. **{name}** — Rs.{price}/unit {stars}")
                if result.get("quantity_needed"):
                    lines.append(f"\nQuantity needed: {result['quantity_needed']} units")
                if result.get("budget"):
                    lines.append(f"Budget: Rs.{result['budget']}")
                message = "\n".join(lines)
            else:
                message = result.get("message", f"No suppliers found for {product_name or 'this product'}.")

        elif intent == "alert":
            # Return pending proactive alerts from PostgreSQL
            alerts        = await _get_pending_alerts(db, store_id)
            response_data = {"alerts": alerts}
            if alerts:
                lines = [f"You have **{len(alerts)} pending alert(s)**:\n"]
                for a in alerts[:5]:
                    severity = a.get("severity", "info")
                    icon = "🔴" if severity == "critical" else "🟡" if severity == "warning" else "ℹ️"
                    lines.append(f"{icon} {a.get('message', 'Alert')}")
                message = "\n".join(lines)
            else:
                message = "✅ No pending alerts. Your store is running smoothly!"

        else:
            # General conversation -- LLM handles it directly with full context
            agent_trace.append("general_llm")
            message       = await _general_chat(query, history_for_llm, db, store_id)
            response_data = {}

        if intent in ("pricing", "forecast"):
            try:
                await log_ai_response_time(db, competitor_zone="LocalMart", event_type=intent, event_time=event_start_time)
            except Exception:
                pass

    except Exception as e:
        message       = "I encountered an issue processing your request. Please try again or rephrase your question."
        response_data = {"error_detail": str(e)}

    # 5. Store assistant reply in history
    append_message(session_id, "assistant", message)

    return _build_response(message, intent, agent_trace, action_cards, response_data, intent_data, session_id)


def _build_response(message, intent, agent_trace, action_cards, response_data, intent_data, session_id):
    """Construct the standard response dict."""
    return {
        "message":          message,
        "agent":            intent,
        "agent_trace":      agent_trace,
        "action_cards":     action_cards,
        "alerts":           [],
        "session_id":       session_id,
        "raw_data":         response_data,
        "intent_metadata":  intent_data,
    }


# -- Helpers ------------------------------------------------------------------

async def log_ai_response_time(db: AsyncSession, competitor_zone: str, event_type: str, event_time: datetime):
    rec_time = datetime.utcnow()
    diff_minutes = (rec_time - event_time).total_seconds() / 60.0
    log_entry = AIResponseLog(
        competitor_zone=competitor_zone,
        market_event_type=event_type,
        market_event_timestamp=event_time,
        recommendation_timestamp=rec_time,
        response_time_minutes=diff_minutes
    )
    db.add(log_entry)
    await db.commit()

async def _resolve_product_id(
    db: AsyncSession,
    store_id: str,
    product_name: str | None,
) -> str | None:
    """Try to find a product_id by product name in the inventory table."""
    if not product_name:
        return None
    try:
        from app.models import Inventory
        from sqlalchemy import and_, func
        # Case-insensitive match
        result = await db.execute(
            select(Inventory.product_id)
            .where(
                and_(
                    Inventory.store_id == store_id,
                    func.lower(Inventory.product_name) == product_name.lower(),
                )
            )
            .limit(1)
        )
        row = result.fetchone()
        if row:
            return str(row[0])

        # Fallback: partial match
        result = await db.execute(
            select(Inventory.product_id)
            .where(
                and_(
                    Inventory.store_id == store_id,
                    func.lower(Inventory.product_name).contains(product_name.lower()),
                )
            )
            .limit(1)
        )
        row = result.fetchone()
        return str(row[0]) if row else None
    except Exception:
        return None


async def _get_pending_alerts(
    db: AsyncSession,
    store_id: str,
    limit: int = 5,
) -> list[dict]:
    """Fetch non-dismissed alerts from PostgreSQL."""
    try:
        rows = await get_active_alerts(db, store_id)
        alerts = []
        for row in rows[:limit]:
            alerts.append({
                "alert_id":       str(row.id),
                "alert_type":     row.alert_type,
                "severity":       row.severity,
                "product_id":     str(row.product_id) if row.product_id else None,
                "product_name":   row.product_name,
                "message":        row.message,
                "suggested_action": row.suggested_action,
                "dismissed":      row.dismissed,
                "created_at":     str(row.created_at),
                "store_id":       row.store_id,
            })
        return alerts
    except Exception:
        return []


def _explain_forecast(result: dict) -> str:
    """Generate a conversational explanation of the forecast result."""
    if result.get("reason"):
        reason    = result["reason"]
        demand    = result.get("predictedDemand", 0)
        days_left = result.get("daysOfStockRemaining")

        lines = [reason]
        if demand and demand > 0:
            lines.append(f"Predicted demand: {demand} units/day.")
        if days_left:
            urgency = "⚠️" if days_left < 3 else "ℹ️"
            lines.append(f"{urgency} Estimated stock duration: {days_left} days.")
        return " ".join(lines)

    name = result.get("productName") or result.get("productId", "this product")
    return (
        f"No forecast data found for '{name}' yet. "
        f"Run the forecast pipeline first using the Run Forecast button on the Insights page."
    )


async def _general_chat(query: str, history: list[dict], db: AsyncSession, store_id: str) -> str:
    """Handle general queries with a conversational LLM response, enriched with store context."""
    # Build a brief store context snapshot for the LLM
    context_parts = []
    try:
        inv_rows = await get_all_inventory(db, store_id)
        if inv_rows:
            total_products = len(inv_rows)
            low_stock = [r for r in inv_rows if r.stock < r.reorder_level]
            context_parts.append(
                f"Store has {total_products} products, {len(low_stock)} are low on stock."
            )
            if low_stock[:3]:
                names = [r.product_name for r in low_stock[:3]]
                context_parts.append(f"Low stock items: {', '.join(names)}.")
    except Exception:
        pass

    store_context = " ".join(context_parts) if context_parts else ""

    return await llm_chat(
        messages=history[-8:] + [{"role": "user", "content": query}],
        system_prompt=(
            "You are KiranaIQ, an AI assistant for a hyperlocal Indian retail store called Smart Vyapar. "
            "You help the store owner with inventory management, sales analysis, supplier discovery, "
            "pricing optimization, demand forecasting, and business strategy.\n\n"
            "IMPORTANT CAPABILITIES you can tell the user about:\n"
            "- Check inventory status: 'Show my inventory' or 'What's low on stock?'\n"
            "- Find suppliers: 'Find supplier for [product]' or 'Order 50 units of milk'\n"
            "- Demand forecast: 'Forecast demand for [product]' or 'Show forecasts'\n"
            "- Pricing help: 'What should I price [product]?' or visit Pricing page\n"
            "- Cash flow: 'Show my cash flow'\n"
            "- Alerts: 'Show my alerts'\n\n"
            f"Current store info: {store_context}\n\n"
            "Be concise, practical, and friendly. Use simple language. "
            "Always provide actionable advice. If the user asks something vague, "
            "suggest specific actions they can take."
        ),
        temperature=0.4,
    )