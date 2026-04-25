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
from app.agents.forecast_agent import forecast_agent, generate_demand_forecast
from app.agents.pricing_agent import pricing_agent
from app.agents.cashflow_agent import cashflow_agent
from app.agents.supplier_agent import supplier_agent
from app.services.conversation_store import (
    get_history, append_message, format_history_for_llm
)
from app.services.db_service import get_active_alerts, get_all_inventory, get_low_stock_items, get_all_suppliers
from app.services.llm import llm_chat
import httpx


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

    # --- Pre-classify: keyword-first overrides for conversational shortcuts ---
    # These catch phrases like "run it", "run the pipeline", "run forecast" BEFORE
    # the LLM classifier runs, so they always work in context.
    q_lower = query.lower().strip()
    _RUN_PIPELINE_KWS = ["run it", "run pipeline", "run the pipeline", "trigger forecast",
                         "run forecast", "start forecast", "generate forecast", "run the forecast"]
    _force_run_pipeline = any(kw in q_lower for kw in _RUN_PIPELINE_KWS)

    # 2. Detect intent with conversation context
    event_start_time = datetime.utcnow()
    agent_trace.append("intent_classifier")
    intent_data  = await detect_intent(query, conversation_history=history_for_llm)
    intent       = "run_pipeline" if _force_run_pipeline else intent_data.get("intent", "general")
    product_name = intent_data.get("productName")

    # Context carry-forward: if user says "run it" with no product, check last message for product
    if not product_name and _force_run_pipeline:
        for msg in reversed(history):
            # Look through recent assistant messages for a product name we mentioned
            if msg.get("role") == "assistant" and msg.get("content"):
                import re
                # Match product names from previous forecast responses
                m = re.search(r'\*\*([^*]+)\*\*|for ([\w\s]+?) (has not|stock|demand|is forecast)', msg["content"])
                if m:
                    product_name = (m.group(1) or m.group(2) or "").strip()
                    break

    product_id   = intent_data.get("productId") or await _resolve_product_id(
        db, store_id, product_name
    )
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

        elif intent == "run_pipeline":
            # ── Run demand forecast pipeline, then immediately query the result ──
            agent_trace.append("forecast_pipeline")
            await generate_demand_forecast(db, store_id)

            if product_id:
                # Immediately query the freshly-written forecast
                agent_trace.append("forecast_agent")
                result = await forecast_agent(db, product_id)
                pname  = result.get("productName") or product_name or product_id
                demand = result.get("predictedDemand", 0)
                stock  = result.get("currentStock", 0)
                reorder = result.get("reorderLevel", 0)

                if demand and demand > 0:
                    days_left = result.get("daysOfStockRemaining")
                    urgency = "⚠️ **Restock urgently!**" if stock <= reorder else "✅ Stock looks okay."
                    message = (
                        f"✅ Forecast pipeline ran successfully. Here's the demand outlook for **{pname}**:\n\n"
                        f"📊 Predicted demand: **{demand} units/day**\n"
                        f"📦 Current stock: {stock} units (reorder at {reorder})\n"
                        + (f"⏳ Estimated stock duration: **{days_left} days**\n" if days_left else "")
                        + f"\n{urgency}"
                    )
                else:
                    # Pipeline ran but product still has no sales data — give inventory-based estimate
                    inv_rows = await get_all_inventory(db, store_id)
                    inv_row  = next((r for r in inv_rows if str(r.product_id) == str(product_id)), None)
                    pname    = (inv_row.product_name if inv_row else None) or product_name or product_id
                    stock    = int(inv_row.stock if inv_row else 0)
                    reorder  = int(inv_row.reorder_level if inv_row else 10)
                    message = (
                        f"✅ Forecast pipeline ran, but **{pname}** has no recent sales to compute a data-driven prediction.\n\n"
                        f"📦 Current stock: **{stock} units** (reorder at {reorder})\n"
                        f"💡 Based on inventory: stock is {'critically low' if stock <= reorder else 'sufficient'}. "
                        f"To get a real forecast, record some sales for this product first."
                    )
                response_data = result
            else:
                message = (
                    "✅ I've successfully run the demand forecast pipeline for all your products. "
                    "Predictions have been updated based on recent sales data.\n\n"
                    "You can now ask: **\"What's the demand for [product name]?\"** to see specific forecasts."
                )
                response_data = {"status": "success", "pipeline": "forecast"}

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
                result = await forecast_agent(db, product_id)
                demand = result.get("predictedDemand", 0)

                if not demand or demand == 0:
                    # ── Auto-pipeline: product not forecasted → run pipeline and re-query ──
                    agent_trace.append("forecast_pipeline_auto")
                    pname  = result.get("productName") or product_name or product_id
                    await generate_demand_forecast(db, store_id)
                    result = await forecast_agent(db, product_id)
                    demand = result.get("predictedDemand", 0)

                    if demand and demand > 0:
                        stock   = result.get("currentStock", 0)
                        reorder = result.get("reorderLevel", 0)
                        days_left = result.get("daysOfStockRemaining")
                        urgency = "⚠️ **Restock urgently!**" if stock <= reorder else "✅ Stock looks okay."
                        message = (
                            f"I ran the forecast pipeline automatically for you. Here's the demand outlook for **{pname}**:\n\n"
                            f"📊 Predicted demand: **{demand} units/day**\n"
                            f"📦 Current stock: {stock} units (reorder at {reorder})\n"
                            + (f"⏳ Estimated stock duration: **{days_left} days**\n" if days_left else "")
                            + f"\n{urgency}"
                        )
                    else:
                        # Still no forecast (no sales data for this product at all)
                        inv_rows = await get_all_inventory(db, store_id)
                        inv_row  = next((r for r in inv_rows if str(r.product_id) == str(product_id)), None)
                        pname    = (inv_row.product_name if inv_row else None) or product_name or product_id
                        stock    = int(inv_row.stock if inv_row else 0)
                        reorder  = int(inv_row.reorder_level if inv_row else 10)
                        message = (
                            f"**{pname}** has no recent sales data to generate a forecast from.\n\n"
                            f"📦 Current stock: **{stock} units** (reorder threshold: {reorder})\n"
                            f"📌 Status: {'🔴 Stock is critically low — restock soon!' if stock <= reorder else '🟢 Stock level is sufficient.'}"
                            f"\n\n💡 Once you record some sales for this product, I can compute a real demand forecast."
                        )
                else:
                    message = _explain_forecast(result)
                response_data = result

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
            result = await cashflow_agent(db, store_id=store_id)
            response_data = result
            balance = result.get("balance", 0)
            
            is_conversational = any(kw in query.lower() for kw in ["why", "explain", "how", "what", "detail"])
            
            if is_conversational:
                agent_trace.append("general_llm")
                cashflow_context = f"Current cash balance is Rs.{balance:,.0f}. Daily revenue is {result.get('revenue', 0)} and daily expenses are {result.get('expenses', 0)}. Let the user know the balance is negative because expenses exceeded revenues or initial balance was low."
                history_with_context = history_for_llm + [{"role": "system", "content": cashflow_context}]
                message = await _general_chat(query, history_with_context, db, store_id)
            else:
                message = (
                    f"Your current cash balance is Rs.{balance:,.0f}. "
                    f"{'Finances look healthy.' if balance > 5000 else 'Low balance -- consider delaying non-urgent reorders.'}"
                )

        elif intent == "supplier":
            # If the user is asking a general analytical question without specifying a product, let the LLM handle it
            is_general_query = (intent_data.get("action") == "general_chat" or "best" in query.lower() or "who" in query.lower() or "what" in query.lower())
            
            if is_general_query and not product_name and not product_id:
                agent_trace.append("general_llm")
                message = await _general_chat(query, history_for_llm, db, store_id)
                response_data = {}
            else:
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
            alerts = await _get_pending_alerts(db, store_id)
            
            is_conversational = any(kw in query.lower() for kw in ["tell me", "what", "why", "how", "explain", "detail"]) or product_name
            
            if is_conversational:
                agent_trace.append("general_llm")
                alert_context = "Current Pending Alerts:\n" + "\n".join([f"- {a.get('message', 'Alert')}" for a in alerts]) if alerts else "No pending alerts."
                history_with_context = history_for_llm + [{"role": "system", "content": alert_context}]
                message = await _general_chat(query, history_with_context, db, store_id)
                response_data = {"alerts": alerts}
            else:
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
        import traceback
        err_detail = str(e)
        # Friendly message but also preserve error detail for debugging
        message       = f"I hit an unexpected issue while processing your request. Details: {err_detail[:200]}"
        response_data = {"error_detail": err_detail}

    # Dynamically inject action cards for general chat if the LLM suggests tasks or ordering
    if not action_cards:
        lower_msg = message.lower()
        if "order more" in lower_msg or "type 'order" in lower_msg or "restock" in lower_msg:
            # Try to infer product name from intent
            prod = product_name or "this product"
            action_cards.append({
                "type": "draft_order",
                "title": f"Draft Order for {prod}",
                "data": {"product": prod, "quantity": 50}
            })
        if "daily tasks" in lower_msg or "add to your list" in lower_msg or "daily operational tasks" in lower_msg:
            import re
            tasks = re.findall(r'^\d+\.\s+\*\*(.*?)\*\*(.*?)$', message, re.MULTILINE)
            if not tasks:
                tasks = re.findall(r'^\d+\.\s+(.*?)$', message, re.MULTILINE)
            
            for t in tasks:
                task_str = f"{t[0]}{t[1]}" if isinstance(t, tuple) else t
                # Clean up bold markers
                task_str = task_str.replace("**", "").replace(":", " - ").strip()
                action_cards.append({
                    "type": "add_task",
                    "title": f"Add Task: {task_str[:25]}...",
                    "data": {"task_text": task_str}
                })

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

        supplier_rows = await get_all_suppliers(db, store_id)
        if supplier_rows:
            best_suppliers = sorted(supplier_rows, key=lambda x: float(x.reliability or 0), reverse=True)[:3]
            if best_suppliers:
                supplier_info = [f"{s.supplier_name} (Rating: {s.reliability}, Products: {', '.join((s.products or [])[:2])})" for s in best_suppliers]
                context_parts.append(f"Top Suppliers: {'; '.join(supplier_info)}.")
    except Exception:
        pass

    store_context = " ".join(context_parts) if context_parts else ""

    return await llm_chat(
        messages=history[-8:] + [{"role": "user", "content": query}],
        system_prompt=(
            "You are Agent Saarthi, an omnipotent AI assistant for a hyperlocal Indian retail store (KiranaIQ / Smart Vyapar). "
            "You have FULL ACCESS to all store data and can actually execute actions — not just suggest them.\n\n"
            "CAPABILITIES YOU CAN EXECUTE RIGHT NOW:\n"
            "- Check inventory: 'Show my inventory' / 'What\'s low on stock?'\n"
            "- Demand forecast: 'Forecast demand for Maggi' (auto-runs pipeline if needed)\n"
            "- Run forecast pipeline: 'Run forecast' / 'Run it' (runs & returns results)\n"
            "- Find suppliers: 'Find supplier for Groundnut Oil'\n"
            "- Draft orders: 'Order 50 units of Milk from Global Dairy'\n"
            "- Pricing advice: 'What should I price Parle-G?'\n"
            "- Cash flow: 'Show my cash flow' / 'Why is cash flow negative?'\n"
            "- Alerts: 'Show my alerts' / 'Tell me about the low stock alerts'\n"
            "- Sales analysis: 'What sold most today?' / 'Analyze top products'\n"
            "- Add tasks: 'Suggest daily tasks' (adds directly to dashboard)\n\n"
            "IMPORTANT: When a user says 'run it', 'run the pipeline', or similar — they mean run the demand forecast pipeline. "
            "Always respond helpfully and tell the user what you\'re doing or what you did.\n\n"
            f"Current store info: {store_context}\n\n"
            "Be concise, practical, and friendly. Use simple language with emojis where helpful. "
            "Always provide actionable advice. Never tell the user to 'ask me to do X' — just do it."
        ),
        temperature=0.4,
    )