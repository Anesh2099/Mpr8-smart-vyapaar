"""
app/agents/pricing_agent.py -- Dynamic pricing with explainable recommendations.

Features:
- Multi-factor pricing: inventory level, demand forecast, seasonal multiplier,
  competitor prices, wholesale cost
- Promotion suggestions for overstock or near-expiry items
- Explainable output: clear reasoning for every recommendation
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.db_service import get_pricing_data
from app.services.llm import llm_chat


# -- Seasonal Multipliers -----------------------------------------------------
# Month -> demand multiplier for Indian retail
MONTHLY_MULTIPLIERS = {
    1: 0.95,  # Jan -- post-holiday slowdown
    2: 1.00,  # Feb
    3: 1.10,  # Mar -- Holi
    4: 1.05,  # Apr -- New Year festivals
    5: 0.95,  # May -- summer slowdown
    6: 0.90,  # Jun
    7: 0.90,  # Jul
    8: 1.00,  # Aug -- Independence Day
    9: 1.10,  # Sep -- Navratri / Dussehra
    10: 1.20, # Oct -- Diwali
    11: 1.05, # Nov -- post-Diwali
    12: 1.10, # Dec -- Christmas / New Year
}


async def pricing_agent(
    db: AsyncSession,
    product_id: str,
    store_id: str = "store001",
) -> dict:
    """
    Recommend an optimal price for a product using multi-factor analysis.

    Uses get_pricing_data() -- a single joined query across inventory,
    demand_forecast, and competitor_prices.

    Returns:
        dict with recommended_price, reasoning, promotion_suggestion, confidence
    """
    data = await get_pricing_data(db, store_id, product_id)

    # -- Raw data -------------------------------------------------------------
    base_price       = float(data.get("price") or 0)
    wholesale_cost   = float(data.get("wholesale_cost") or base_price * 0.6)
    current_stock    = float(data.get("stock") or 0)
    reorder_level    = float(data.get("reorder_level") or 10)
    product_name     = data.get("product_name") or product_id
    predicted_demand = float(data.get("predicted_demand") or 0)
    competitor_price = float(data.get("competitor_price") or base_price)

    current_month     = datetime.now().month
    seasonal_multiplier = MONTHLY_MULTIPLIERS.get(current_month, 1.0)

    # -- Pricing Factors ------------------------------------------------------
    reasons = []
    multiplier = 1.0

    # Factor 1: Demand signal
    if predicted_demand > 50:
        multiplier += 0.10
        reasons.append(f"High predicted demand ({predicted_demand} units)")
    elif predicted_demand > 20:
        multiplier += 0.05
        reasons.append(f"Moderate demand ({predicted_demand} units)")
    elif predicted_demand < 10 and current_stock > reorder_level * 2:
        multiplier -= 0.10
        reasons.append(f"Low demand ({predicted_demand} units) with overstock")

    # Factor 2: Stock level
    if current_stock == 0:
        multiplier += 0.15
        reasons.append("Out of stock -- scarcity premium")
    elif current_stock < reorder_level:
        multiplier += 0.08
        reasons.append(f"Stock low ({current_stock} units < reorder level {reorder_level})")
    elif current_stock > reorder_level * 3:
        multiplier -= 0.08
        reasons.append(f"Overstock ({current_stock} units) -- clearance discount")

    # Factor 3: Seasonal
    if seasonal_multiplier != 1.0:
        multiplier += (seasonal_multiplier - 1.0)
        reasons.append(
            f"Seasonal factor for {datetime.now().strftime('%B')} (x{seasonal_multiplier})"
        )

    # Factor 4: Competitor benchmark
    if competitor_price > 0:
        if base_price > competitor_price * 1.1:
            multiplier -= 0.05
            reasons.append(f"Competitor price is Rs.{competitor_price} -- discount to stay competitive")
        elif base_price < competitor_price * 0.9:
            multiplier += 0.05
            reasons.append(f"Competitor price is Rs.{competitor_price} -- slight increase possible")

    # -- Calculate prices -----------------------------------------------------
    raw_price         = base_price * multiplier
    min_price         = wholesale_cost * 1.05  # minimum 5% margin
    recommended_price = round(max(raw_price, min_price), 2)
    change_pct        = (
        round((recommended_price - base_price) / base_price * 100, 1)
        if base_price else 0
    )

    # -- Promotion suggestion -------------------------------------------------
    promotion = _generate_promotion(product_name, current_stock, predicted_demand, recommended_price)

    # -- LLM explanation ------------------------------------------------------
    reason_str = "; ".join(reasons) if reasons else "No significant pricing factors detected"
    explanation = await llm_chat(
        messages=[{
            "role": "user",
            "content": (
                f"Product: {product_name}\n"
                f"Current price: Rs.{base_price}\nRecommended price: Rs.{recommended_price}\n"
                f"Reasons: {reason_str}\n\n"
                f"Write a 1-2 sentence explanation for a Kirana store owner on why they should "
                f"change the price. Be simple, clear, and actionable."
            )
        }],
        temperature=0.3,
    )

    # -- Confidence score -----------------------------------------------------
    data_quality = sum([
        bool(base_price),
        bool(predicted_demand),
        bool(competitor_price),
        bool(wholesale_cost),
    ])
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


def _generate_promotion(
    product_name: str,
    stock: float,
    demand: float,
    price: float,
) -> Optional[str]:
    """Generate a promotion suggestion when overstock or near expiry."""
    if stock > 50 and demand < 10:
        return (
            f"Bundle Deal: Buy 3 {product_name} for "
            f"Rs.{round(price * 2.5, 0)} (save Rs.{round(price * 0.5, 0)})"
        )
    if demand > 50 and stock < 15:
        return (
            f"Flash Sale Alert: Limited stock of {product_name} "
            f"at Rs.{price} -- promote urgency!"
        )
    return None