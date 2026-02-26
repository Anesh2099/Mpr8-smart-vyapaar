"""
app/agents/master_agent.py — Full Orchestrator + Conversational Interface.

Features:
- Maintains conversation context via Firestore chat history
- Rich intent detection with entity extraction
- Multi-agent routing and chaining (inventory → forecast → supplier chain)
- Error handling with human-friendly messages
- Proactive alerts injected into every response
- Structured response: message + agent_trace + action_cards + alerts
- Human-in-the-loop: generates drafts, never auto-executes
"""

from app.agents.intent_agent import detect_intent
from app.agents.inventory_agent import inventory_agent, check_low_stock
from app.agents.forecast_agent import forecast_agent
from app.agents.pricing_agent import pricing_agent
from app.agents.cashflow_agent import cashflow_agent
from app.agents.supplier_agent import supplier_agent
from app.services.conversation_store import (
    get_history, append_message, format_history_for_llm
)
from app.services.llm import llm_chat
from app.core.config import db


def assistant_agent(
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
    history = get_history(session_id)
    history_for_llm = format_history_for_llm(history)

    # 2. Detect intent with conversation context
    agent_trace.append("intent_classifier")
    intent_data = detect_intent(query, conversation_history=history_for_llm)
    intent = intent_data.get("intent", "general")
    product_id = intent_data.get("productId") or _resolve_product_id(intent_data.get("productName"))
    product_name = intent_data.get("productName")
    vendor_id = intent_data.get("vendorId") or "vendor001"
    quantity = intent_data.get("quantity")
    budget = intent_data.get("budget")

    # 3. Store user message in history
    append_message(session_id, "user", query)

    # 4. Route to agent(s)
    response_data = {}
    action_cards = []
    message = ""

    try:
        if intent in ("inventory", "reorder"):
            agent_trace.append("inventory_agent")
            result = inventory_agent(query=query, store_id=store_id)
            response_data = result

            # Chain: if low stock found, also run forecast + supplier for top item
            if result.get("low_stock_count", 0) > 0 and product_id:
                agent_trace.append("forecast_agent")
                fc = forecast_agent(product_id)
                agent_trace.append("supplier_agent")
                sup = supplier_agent(
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
            pid = product_id
            if not pid:
                # No specific product — summarise low stock items instead
                agent_trace.append("inventory_agent")
                inv_result = inventory_agent(query=query, store_id=store_id)
                response_data = inv_result
                message = inv_result.get("message", "I need a specific product name to run a forecast. Which product would you like me to forecast demand for?")
            else:
                result = forecast_agent(pid)
                response_data = result
                message = _explain_forecast(result)

        elif intent == "pricing":
            agent_trace.append("pricing_agent")
            pid = product_id or "product001"
            result = pricing_agent(pid, store_id=store_id)
            response_data = result
            message = result.get("explanation", f"Recommended price for {pid}: ₹{result.get('recommendedPrice', 'N/A')}")
            if result.get("promotionSuggestion"):
                action_cards.append({
                    "type": "promotion",
                    "title": "Promotion Suggestion",
                    "data": {"suggestion": result["promotionSuggestion"]}
                })

        elif intent == "cashflow":
            agent_trace.append("cashflow_agent")
            result = cashflow_agent(vendor_id)
            response_data = result
            balance = result.get("balance", 0)
            message = f"Your current cash balance is ₹{balance:,.0f}. {'Finances look healthy.' if balance > 5000 else '⚠️ Low balance — consider delaying non-urgent reorders.'}"

        elif intent == "supplier":
            agent_trace.append("supplier_agent")
            result = supplier_agent(
                product_id=product_id,
                product_name=product_name,
                quantity=quantity,
                budget=budget,
                query=query,
            )
            response_data = result
            action_cards.extend(result.get("action_cards", []))
            message = result.get("message", "Supplier search complete.")

        elif intent == "alert":
            # Return pending proactive alerts
            alerts = _get_pending_alerts(store_id)
            response_data = {"alerts": alerts}
            message = f"You have {len(alerts)} pending alert(s)." if alerts else "No pending alerts. All clear! ✅"

        else:
            # General conversation — LLM handles it directly
            agent_trace.append("general_llm")
            message = _general_chat(query, history_for_llm)
            response_data = {}

    except Exception as e:
        message = f"I encountered an issue processing your request. Please try again or rephrase your question."
        response_data = {"error_detail": str(e)}

    # 5. Fetch proactive alerts to include in every response
    proactive = _get_pending_alerts(store_id, limit=3)

    # 6. Store assistant reply in history
    append_message(session_id, "assistant", message)

    return {
        "message": message,
        "agent": intent,
        "agent_trace": agent_trace,
        "action_cards": action_cards,
        "alerts": proactive,
        "session_id": session_id,
        "raw_data": response_data,
        "intent_metadata": intent_data,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────
def _resolve_product_id(product_name: str | None) -> str | None:
    """Try to find a Firestore product_id by product name."""
    if not product_name:
        return None
    try:
        docs = db.collection("inventory").where("productName", "==", product_name).limit(1).get()
        if docs:
            return docs[0].id
    except Exception:
        pass
    return None


def _explain_forecast(result: dict) -> str:
    """Generate a conversational explanation of the forecast result using the enriched reason field."""
    # Use the pre-built human-readable reason if available
    if result.get("reason"):
        name = result.get("productName", "This product")
        reason = result["reason"]
        demand = result.get("predictedDemand", 0)
        reorder_qty = result.get("recommendedReorderQty")
        days_left = result.get("daysOfStockRemaining")

        # Build a rich conversational response
        lines = [reason]
        if demand and demand > 0:
            lines.append(f"📊 Predicted demand: {demand} units/day.")
        if days_left:
            urgency = "⚠️" if days_left < 3 else "ℹ️"
            lines.append(f"{urgency} Estimated stock duration: {days_left} days.")
        if reorder_qty:
            lines.append(f"✅ Suggested reorder: {reorder_qty} units.")
        return " ".join(lines)

    # Fallback if no data
    name = result.get("productName") or result.get("productId", "this product")
    return (
        f"No forecast data found for '{name}' yet. "
        f"Run the forecast pipeline first using the Run Forecast button on the Insights page."
    )


def _general_chat(query: str, history: list[dict]) -> str:
    """Handle general queries with a conversational LLM response."""
    return llm_chat(
        messages=history[-6:] + [{"role": "user", "content": query}],
        system_prompt=(
            "You are KiranaIQ, an AI assistant for a hyperlocal Indian retail store. "
            "Help the store owner with questions about inventory, sales, suppliers, pricing, and business strategy. "
            "Be concise, practical, and friendly. Use simple language."
        ),
        temperature=0.4,
    )


def _get_pending_alerts(store_id: str, limit: int = 5) -> list[dict]:
    """Fetch non-dismissed alerts from Firestore."""
    try:
        docs = (
            db.collection("proactive_alerts")
            .where("store_id", "==", store_id)
            .where("dismissed", "==", False)
            .limit(limit)
            .get()
        )
        alerts = []
        for doc in docs:
            a = doc.to_dict()
            a["alert_id"] = doc.id
            alerts.append(a)
        return alerts
    except Exception:
        return []