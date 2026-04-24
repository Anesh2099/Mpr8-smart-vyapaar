"""
app/agents/pricing_agent.py -- Dynamic pricing with explainable recommendations.

Features:
- Multi-factor pricing: inventory level, demand forecast, seasonal multiplier, competitor prices
- Live Weather Integration (Open-Meteo)
- External Market Signals (Festivals/Events)
- Aggressive Expiry-Driven Discounts
- Explainable output: clear reasoning for every recommendation
"""

from datetime import datetime, timezone
from typing import Optional
import httpx

from sqlalchemy.ext.asyncio import AsyncSession
from app.services.db_service import get_pricing_data
from app.services.llm import llm_chat
from app.agents.forecast_agent import run_festival_advisor

MONTHLY_MULTIPLIERS = {
    1: 0.95, 2: 1.00, 3: 1.10, 4: 1.05, 5: 0.95, 6: 0.90,
    7: 0.90, 8: 1.00, 9: 1.10, 10: 1.20, 11: 1.05, 12: 1.10,
}

async def _get_weather_factor(product_name: str) -> tuple[float, str]:
    """Fetch live weather for Mumbai async and return a price multiplier & reason."""
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=19.0760&longitude=72.8777&current_weather=true"
        async with httpx.AsyncClient(timeout=2.0) as client:
            res = await client.get(url)
            if res.status_code == 200:
                data = res.json()
                temp = data.get("current_weather", {}).get("temperature", 0)
                weathercode = data.get("current_weather", {}).get("weathercode", 0)
                
                is_raining = weathercode in [51, 53, 55, 61, 63, 65, 80, 81, 82, 95, 96, 99]
                is_hot = temp > 32
                
                product_lower = product_name.lower()
                
                if is_raining and any(w in product_lower for w in ["umbrella", "raincoat", "snack", "maggi", "tea", "coffee", "soup"]):
                    return 0.05, f"Rainy weather in Mumbai ({temp}°C) -- high demand category surge"
                if is_hot and any(w in product_lower for w in ["ice cream", "cold drink", "soda", "juice", "water", "cola"]):
                    return 0.05, f"Hot weather in Mumbai ({temp}°C) -- high demand category surge"
    except Exception:
        pass
    return 0.0, ""

async def pricing_agent(db: AsyncSession, product_id: str, store_id: str = "store001") -> dict:
    data = await get_pricing_data(db, store_id, product_id)

    # -- Raw data -------------------------------------------------------------
    base_price       = float(data.get("price") or 0)
    wholesale_cost   = float(data.get("wholesale_cost") or base_price * 0.6)
    current_stock    = float(data.get("stock") or 0)
    reorder_level    = float(data.get("reorder_level") or 10)
    product_name     = data.get("product_name") or product_id
    predicted_demand = float(data.get("predicted_demand") or 0)
    competitor_price = float(data.get("competitor_price") or base_price)
    expiry_date      = data.get("expiry_date")

    current_month       = datetime.now(timezone.utc).month
    seasonal_multiplier = MONTHLY_MULTIPLIERS.get(current_month, 1.0)

    reasons = []
    multiplier = 1.0

    # Factor 1: Expiry-Driven Discount
    days_to_expiry = None
    if expiry_date:
        try:
            today = datetime.now(timezone.utc)
            if hasattr(expiry_date, "timestamp"):
                expiry_dt = expiry_date
            else:
                expiry_dt = datetime.fromisoformat(str(expiry_date)).replace(tzinfo=timezone.utc)
            days_to_expiry = (expiry_dt - today).days
        except Exception:
            pass

    if days_to_expiry is not None and days_to_expiry <= 3:
        multiplier -= 0.30
        reasons.append(f"Expiring in {days_to_expiry} days -- aggressive clearance discount")
    else:
        # Standard Factors
        if predicted_demand > 50:
            multiplier += 0.10
            reasons.append(f"High predicted demand ({predicted_demand} units)")
        elif predicted_demand > 20:
            multiplier += 0.05
            reasons.append(f"Moderate demand ({predicted_demand} units)")
        elif predicted_demand < 10 and current_stock > reorder_level * 2:
            multiplier -= 0.10
            reasons.append(f"Low demand ({predicted_demand} units) with overstock")

        if current_stock == 0:
            multiplier += 0.15
            reasons.append("Out of stock -- scarcity premium")
        elif current_stock < reorder_level:
            multiplier += 0.08
            reasons.append(f"Stock low ({current_stock} units < reorder level {reorder_level})")
        elif current_stock > reorder_level * 3:
            multiplier -= 0.08
            reasons.append(f"Overstock ({current_stock} units) -- clearance discount")

        if seasonal_multiplier != 1.0:
            multiplier += (seasonal_multiplier - 1.0)
            reasons.append(f"Seasonal factor for {datetime.now(timezone.utc).strftime('%B')} (x{seasonal_multiplier})")

        if competitor_price > 0:
            if base_price > competitor_price * 1.1:
                multiplier -= 0.05
                reasons.append(f"Competitor price is Rs.{competitor_price} -- discount to stay competitive")
            elif base_price < competitor_price * 0.9:
                multiplier += 0.05
                reasons.append(f"Competitor price is Rs.{competitor_price} -- slight increase possible")

        # Factor 6: Live Weather
        weather_mult, weather_reason = await _get_weather_factor(product_name)
        if weather_mult != 0:
            multiplier += weather_mult
            reasons.append(weather_reason)
            
        # Factor 7: External Market Signals (Festivals/Events)
        try:
            festivals = await run_festival_advisor()
            if festivals:
                festival_name = festivals[0].get("festival", "Upcoming Festival")
                multiplier += 0.05
                reasons.append(f"Upcoming festival detected ({festival_name}) -- festive demand surge")
        except Exception:
            pass

    # -- Calculate prices -----------------------------------------------------
    raw_price         = base_price * multiplier
    min_price         = wholesale_cost * 1.05
    recommended_price = round(max(raw_price, min_price), 2)
    change_pct        = round((recommended_price - base_price) / base_price * 100, 1) if base_price else 0

    promotion = _generate_promotion(product_name, current_stock, predicted_demand, recommended_price)

    reason_str = "; ".join(reasons) if reasons else "No significant pricing factors detected"

    # Build explanation from the already-computed factors (no extra LLM call needed)
    if reasons:
        direction = "increase" if recommended_price > base_price else "decrease" if recommended_price < base_price else "keep"
        if direction == "increase":
            explanation = (
                f"I recommend increasing the price of {product_name} from Rs.{base_price} to "
                f"Rs.{recommended_price} based on: {reason_str}."
            )
        elif direction == "decrease":
            explanation = (
                f"Consider lowering {product_name} from Rs.{base_price} to Rs.{recommended_price}. "
                f"Reason: {reason_str}."
            )
        else:
            explanation = f"Current price of Rs.{base_price} for {product_name} is optimal. {reason_str}."
    else:
        explanation = f"Current price of Rs.{base_price} for {product_name} looks good — no adjustment needed right now."

    data_quality = sum([bool(base_price), bool(predicted_demand), bool(competitor_price), bool(wholesale_cost)])
    confidence = round(data_quality / 4, 2)

    return {
        "agent": "pricing",
        "productId": product_id,
        "productName": product_name,
        "currentPrice": base_price,
        "recommendedPrice": recommended_price,
        "priceChange": f"{'+' if change_pct >= 0 else ''}{change_pct}%",
        "factors": reasons,
        "explanation": explanation,
        "promotionSuggestion": promotion,
        "confidence": confidence,
        "seasonalMultiplier": seasonal_multiplier,
    }

def _generate_promotion(product_name: str, stock: float, demand: float, price: float) -> Optional[str]:
    if stock > 50 and demand < 10:
        return f"💡 Bundle Deal: Buy 3 {product_name} for Rs.{round(price * 2.5, 0)} (save Rs.{round(price * 0.5, 0)})"
    if demand > 50 and stock < 15:
        return f"🔥 Flash Sale Alert: Limited stock of {product_name} at Rs.{price} -- promote urgency!"
    return None