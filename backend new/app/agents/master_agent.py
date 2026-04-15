"""
app/agents/master_agent.py -- Full Orchestrator + Conversational Interface.

Features:
- Maintains conversation context via in-memory/Redis conversation store
- Rich intent detection with entity extraction
- Multi-agent routing and chaining (inventory -> forecast -> supplier chain)
- Error handling with human-friendly messages
- Proactive alerts injected into every response from PostgreSQL
- Structured response: message + agent_trace + action_cards + alerts
- Human-in-the-loop: generates drafts, never auto-executes
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agents.intent_agent import detect_intent
from app.agents.inventory_agent import inventory_agent, check_low_stock
from app.agents.forecast_agent import forecast_agent
from app.agents.pricing_agent import pricing_agent
from app.agents.cashflow_agent import cashflow_agent
from app.agents.supplier_agent import supplier_agent
from app.services.conversation_store import (
    get_history, append_message, format_history_for_llm
)
from app.services.db_service import get_active_alerts, get_all_inventory
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
                # No specific product -- summarise low stock items instead
                agent_trace.append("inventory_agent")
                inv_result    = await inventory_agent(db, query=query, store_id=store_id)
                response_data = inv_result
                message       = inv_result.get(
                    "message",
                    "I need a specific product name to run a forecast. Which product would you like me to forecast demand for?",
                )
            else:
                result        = await forecast_agent(db, product_id)
                response_data = result
                message       = _explain_forecast(result)

        elif intent == "pricing":
            agent_trace.append("pricing_agent")
            pid           = product_id or "product001"
            result        = await pricing_agent(db, pid, store_id=store_id)
            response_data = result
            message       = result.get(
                "explanation",
                f"Recommended price for {pid}: Rs.{result.get('recommendedPrice', 'N/A')}",
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
            result        = await supplier_agent(
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
            message       = result.get("message", "Supplier search complete.")

        elif intent == "alert":
            # Return pending proactive alerts from PostgreSQL
            alerts        = await _get_pending_alerts(db, store_id)
            response_data = {"alerts": alerts}
            message       = (
                f"You have {len(alerts)} pending alert(s)."
                if alerts
                else "No pending alerts. All clear!"
            )

        else:
            # General conversation -- LLM handles it directly
            agent_trace.append("general_llm")
            message       = await _general_chat(query, history_for_llm)
            response_data = {}

    except Exception as e:
        message       = "I encountered an issue processing your request. Please try again or rephrase your question."
        response_data = {"error_detail": str(e)}

    # 5. Fetch proactive alerts to include in every response
    proactive = await _get_pending_alerts(db, store_id, limit=3)

    # 6. Store assistant reply in history
    append_message(session_id, "assistant", message)

    return {
        "message":          message,
        "agent":            intent,
        "agent_trace":      agent_trace,
        "action_cards":     action_cards,
        "alerts":           proactive,
        "session_id":       session_id,
        "raw_data":         response_data,
        "intent_metadata":  intent_data,
    }


# -- Helpers ------------------------------------------------------------------

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
        from sqlalchemy import and_
        result = await db.execute(
            select(Inventory.product_id)
            .where(
                and_(
                    Inventory.store_id == store_id,
                    Inventory.product_name == product_name,
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
            urgency = "[!]" if days_left < 3 else "[i]"
            lines.append(f"{urgency} Estimated stock duration: {days_left} days.")
        return " ".join(lines)

    name = result.get("productName") or result.get("productId", "this product")
    return (
        f"No forecast data found for '{name}' yet. "
        f"Run the forecast pipeline first using the Run Forecast button on the Insights page."
    )


async def _general_chat(query: str, history: list[dict]) -> str:
    """Handle general queries with a conversational LLM response."""
    return await llm_chat(
        messages=history[-6:] + [{"role": "user", "content": query}],
        system_prompt=(
            "You are KiranaIQ, an AI assistant for a hyperlocal Indian retail store. "
            "Help the store owner with questions about inventory, sales, suppliers, pricing, and business strategy. "
            "Be concise, practical, and friendly. Use simple language."
        ),
        temperature=0.4,
    )