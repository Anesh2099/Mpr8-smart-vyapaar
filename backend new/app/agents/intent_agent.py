"""
app/agents/intent_agent.py — Rich intent classifier and entity extractor.

Classifies user queries into intents AND extracts key entities:
product name, product ID, vendor ID, quantity, budget, and action type.
"""

import json
from app.services.llm import llm_json

INTENT_SYSTEM_PROMPT = """
You are an intent classifier for a hyperlocal retail store AI assistant (KiranaIQ).

Analyze the user query and return a JSON object with these fields:
{
  "intent": "<one of: inventory | forecast | pricing | supplier | cashflow | reorder | alert | general>",
  "productId": "<product document ID if mentioned, else null>",
  "productName": "<product name if mentioned, else null>",
  "vendorId": "<vendor ID if mentioned, else null>",
  "quantity": <number if mentioned, else null>,
  "budget": <number in INR if mentioned, else null>,
  "action": "<specific action: check_stock | low_stock_alert | expiry_check | find_supplier | compare_prices | draft_order | get_forecast | set_price | get_cashflow | general_chat>",
  "confidence": <0.0 to 1.0>
}

Intent definitions:
- inventory: Questions about current stock, quantities, expiry
- forecast: Questions about future demand, what will sell
- pricing: Questions about optimal price, discounts, promotions
- supplier: Finding suppliers, ordering, negotiation
- cashflow: Financial balance, income, expenses
- reorder: Explicit reorder or purchase requests
- alert: User asking about alerts or notifications
- general: Greeting, unclear, or out-of-scope queries

Always return valid JSON only. No explanations.
"""


async def detect_intent(query: str, conversation_history: list[dict] | None = None) -> dict:
    """
    Classify user intent and extract entities from a natural language query.

    Args:
        query: The user's message.
        conversation_history: Previous messages for context (optional).

    Returns:
        dict with intent, productId, productName, vendorId, quantity, budget, action, confidence.
    """
    messages = []

    # Include last 4 history messages for context
    if conversation_history:
        messages.extend(conversation_history[-4:])

    messages.append({"role": "user", "content": query})

    result = await llm_json(
        messages=messages,
        system_prompt=INTENT_SYSTEM_PROMPT,
        temperature=0,
        fallback={
            "intent": "general",
            "productId": None,
            "productName": None,
            "vendorId": None,
            "quantity": None,
            "budget": None,
            "action": "general_chat",
            "confidence": 0.0,
        }
    )
    return result