"""
forecast_agent.py -- Unified Demand Forecasting Agent

Includes:
  - Module 1: Demand Forecasting (reads customer_sales / demand_forecast via PostgreSQL)
  - Module 2: Trend & Spike Detection (Google Trends, Amazon, Reddit scraping)
  - Module 3: Festival Stock Advisor (Google Calendar + Groq/Llama)

The primary callable for the FastAPI endpoint is `forecast_agent(db, product_id)`.
"""

import os
import time
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Optional
import asyncio

from app.core.cache import RedisCache

import pandas as pd
import requests
from bs4 import BeautifulSoup
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

# PostgreSQL service layer
from app.services.db_service import (
    get_sales_last_n_days,
    get_forecast,
    upsert_forecast,
    get_all_inventory,
)

# Google Calendar Auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# ============================
# CONFIGURATION
# ============================
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
TREND_SCORE_THRESHOLD = 40

retail_keywords = [
    "toy", "drink", "chocolate", "snack", "ramen", "figure",
    "collectible", "chips", "biscuits", "juice", "cola",
    "noodles", "candy", "energy drink", "soda", "oil", "sugar", "salt", "dal"
]

# Absolute paths to Google Calendar auth files (at the backend root)
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_TOKEN_PATH = os.path.join(_BACKEND_DIR, "token.json")
_CREDENTIALS_PATH = os.path.join(_BACKEND_DIR, "credentials.json")


async def _groq_chat(messages: list, model: str = "llama-3.3-70b-versatile") -> str:
    """Async httpx call to Groq REST API — used by async forecast functions."""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "messages": messages}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"SKIP (error: {e})"


def _groq_chat_sync(messages: list, model: str = "llama-3.3-70b-versatile") -> str:
    """Sync httpx call to Groq — used by festival advisor (sync context)."""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "messages": messages}
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"SKIP (error: {e})"


# ============================
# MODULE 1: DEMAND FORECASTING
# ============================

async def forecast_agent(db: AsyncSession, product_id: str) -> dict:
    """
    Primary callable used by FastAPI endpoints.
    Reads the pre-computed forecast from the demand_forecast table.
    Enriches with product name from inventory and a human-readable restock reason.
    Falls back gracefully if no data exists yet.
    """
    try:
        # Fetch all forecasts for the store, find the one for this product
        forecast_rows = await get_forecast(db, store_id="store001")
        forecast_row = next(
            (f for f in forecast_rows if str(f.product_id) == str(product_id)),
            None,
        )

        # Fetch inventory to get product name + current stock
        inv_rows = await get_all_inventory(db, store_id="store001")
        inv_row = next(
            (i for i in inv_rows if str(i.product_id) == str(product_id)),
            None,
        )

        # Resolve best available name
        product_name = (
            (forecast_row.product_name if forecast_row else None)
            or (inv_row.product_name if inv_row else None)
            or product_id
        )

        predicted_demand = round(float(forecast_row.predicted_demand if forecast_row else 0), 2)
        current_stock = int(inv_row.stock if inv_row else 0)
        reorder_level = int(inv_row.reorder_level if inv_row else 10)
        days_of_stock = (
            round(current_stock / predicted_demand, 1) if predicted_demand > 0 else None
        )

        # Build a human-readable reason
        if not forecast_row:
            reason = (
                f"{product_name} has not been forecasted yet. "
                f"Current stock is {current_stock} units (reorder at {reorder_level}). "
                f"Run the demand forecast pipeline to generate predictions."
            )
        elif current_stock <= reorder_level:
            urgency = "critically low" if current_stock == 0 else "below reorder threshold"
            days_msg = (
                f" At the predicted demand of {predicted_demand} units/day, "
                f"stock will last only {days_of_stock} more days."
                if days_of_stock else ""
            )
            reason = (
                f"{product_name} stock is {urgency} ({current_stock} units left, "
                f"reorder at {reorder_level}).{days_msg} "
                f"Recommended restock: at least {max(1, round(predicted_demand * 7))} units to cover 7 days."
            )
        elif predicted_demand > current_stock:
            reason = (
                f"{product_name} is forecasted to need {predicted_demand} units/day "
                f"but only {current_stock} are in stock. Restock soon to avoid running out."
            )
        else:
            reason = (
                f"{product_name} has {current_stock} units in stock. "
                f"Predicted demand is {predicted_demand} units/day -- approximately "
                f"{days_of_stock} days of stock remaining. "
                f"Reorder threshold is {reorder_level} units."
            )

        return {
            "productId": product_id,
            "productName": product_name,
            "predictedDemand": predicted_demand,
            "currentStock": current_stock,
            "reorderLevel": reorder_level,
            "daysOfStockRemaining": days_of_stock,
            "reason": reason,
            "updatedAt": str(forecast_row.updated_at if forecast_row else "Not yet forecasted"),
        }

    except Exception as e:
        return {
            "productId": product_id,
            "productName": product_id,
            "predictedDemand": 0,
            "reason": f"Forecast lookup failed for {product_id}: {e}",
        }


async def generate_demand_forecast(db: AsyncSession, store_id: str = "store001") -> None:
    """
    Reads customer_sales from PostgreSQL (last 7 days via date index),
    computes a weighted 7-day moving average for each product,
    and saves results to the demand_forecast table via upsert_forecast().

    Supports both camelCase fields (productId / date) and snake_case (product_id / sale_date).
    """
    print("\nStarting Demand Forecasting (Layer 1)...")

    # --- Fetch last 7 days of sales with their items (uses idx_sales_date) ---
    sales = await get_sales_last_n_days(db, store_id, n=7)

    if not sales:
        print("No sales data found in the last 7 days.")
        return

    # Flatten sales + sale_items into a list of per-item dicts
    rows = []
    for sale in sales:
        sale_date = sale.sale_date
        for item in sale.items:
            rows.append({
                "product_id": str(item.product_id),
                "product_name": str(item.product_name),
                "quantity": float(item.quantity),
                "date": sale_date,
            })

    if not rows:
        print("Sales exist but no line items found.")
        return

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce").dt.normalize()
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)

    # Build a name map: product_id -> most recent product_name
    name_map = df.groupby("product_id")["product_name"].first().to_dict()

    daily_sales = (
        df.groupby(["product_id", "date"])["quantity"].sum().reset_index()
    )
    last_date = daily_sales["date"].max()
    last_7_days = daily_sales[daily_sales["date"] >= last_date - timedelta(days=7)]

    for product_id in last_7_days["product_id"].unique():
        product_data = (
            last_7_days[last_7_days["product_id"] == product_id]
            .sort_values("date")
        )
        quantities = product_data["quantity"].values
        if len(quantities) == 0:
            continue

        # Weighted moving average: more recent days get higher weight
        weights = list(range(1, len(quantities) + 1))
        prediction = float(
            sum(float(q) * w for q, w in zip(quantities, weights)) / sum(weights)
        )

        product_name = name_map.get(product_id, product_id)
        await upsert_forecast(
            db=db,
            store_id=store_id,
            product_id=str(product_id),
            product_name=str(product_name),
            predicted_demand=round(prediction, 2),
        )
        print(f"  OK {product_id}: predicted demand = {prediction:.1f} units/day")

    print("Demand forecast saved to PostgreSQL.")


# ============================
# MODULE 2: TREND & SPIKE DETECTION
# ============================

def google_trends() -> list:
    try:
        url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=IN"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        root = ET.fromstring(res.content)
        return [
            item.find('title').text
            for item in root.findall('.//item')
            if item.find('title') is not None
        ][:10]
    except Exception as e:
        print("Google Trends RSS fetch failed:", e)
        return []


def amazon_best_sellers() -> list:
    items = []
    headers = {"User-Agent": "Mozilla/5.0"}
    url = "https://www.amazon.in/gp/bestsellers/grocery"
    try:
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        for item in soup.select("._cDEzb_p13n-sc-css-line-clamp-3_g3dy1"):
            items.append(item.text.strip())
    except Exception:
        print("Amazon fetch failed")
    return items[:20]


def reddit_trends() -> list:
    topics = []
    subreddits = ["india", "indiaspeaks", "food", "snacks", "gaming", "technology"]
    headers = {"User-Agent": "Mozilla/5.0"}
    for sub in subreddits:
        try:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit=15"
            res = requests.get(url, headers=headers, timeout=5)
            data = res.json()
            for post in data.get("data", {}).get("children", []):
                topics.append(post["data"]["title"])
        except Exception:
            continue
    return topics


def is_retail_relevant(text: str) -> bool:
    return any(word in text.lower() for word in retail_keywords)


def is_commercial_product(keyword: str) -> bool:
    query = keyword + " buy"
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        return "\u20b9" in soup.text or "Rs." in soup.text
    except Exception:
        return False


def detect_new_trends() -> list:
    daily_google = google_trends()
    daily_amazon = amazon_best_sellers()
    daily_reddit = reddit_trends()
    candidates = list(set(daily_google + daily_amazon + daily_reddit))
    print(f"TOTAL TREND CANDIDATES: {len(candidates)}")

    valid = []
    for topic in candidates:
        if not is_retail_relevant(topic) or not is_commercial_product(topic):
            continue
        score = 0
        if topic in daily_google:
            score += 50
        if topic in daily_amazon:
            score += 30
        reddit_count = sum(topic.lower() in t.lower() for t in daily_reddit)
        score += reddit_count * 10
        if score >= TREND_SCORE_THRESHOLD:
            valid.append((topic, score))
    return valid


def detect_spike(product: dict) -> bool:
    return float(product.get("stock", 0)) < 5


async def run_trend_engine(db: AsyncSession, store_id: str = "store001") -> None:
    """Trend & spike detection using live inventory from PostgreSQL."""
    print("\nStarting Trend & Spike Detection (Layers 2 & 3)...")

    inv_rows = await get_all_inventory(db, store_id)
    if inv_rows:
        for row in inv_rows:
            product = {c.name: getattr(row, c.name) for c in row.__table__.columns}
            if detect_spike(product):
                prod_name = product.get("product_name", product.get("product_id", "unknown"))
                print(f"  Low stock spike: {prod_name} ({product.get('stock')} units)")
    else:
        print("No inventory found to check for spikes.")

    trends = detect_new_trends()
    for topic, score in trends:
        print(f"  Valid Trend: {topic} (Score: {score})")
    print("Demand Intelligence cycle complete.")


# ============================
# MODULE 3: FESTIVAL STOCK ADVISOR
# ============================

def get_calendar_service():
    creds = None
    if os.path.exists(_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(_TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(_CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(_TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)


def fetch_festivals(service, days: int = 15) -> list:
    now = datetime.now(timezone.utc).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    calendar_ids = ['primary', 'en.indian#holiday@group.v.calendar.google.com']
    all_events = []
    for cal_id in calendar_ids:
        try:
            result = service.events().list(
                calendarId=cal_id, timeMin=now, timeMax=future,
                singleEvents=True, orderBy='startTime'
            ).execute()
            all_events.extend(result.get('items', []))
        except Exception as e:
            print(f"Error fetching {cal_id}: {e}")
    return all_events


def get_retail_advice(event_name: str) -> str:
    prompt = (
        f"Event: {event_name}. "
        "Context: You are a retail expert for Indian Kirana stores. "
        "If this is any part of Holi (Lathmar, Holika Dahan, Dhulandi) or any major festival, "
        "list 5 MUST-STOCK items. Be very specific (e.g., 'Herbal Gulal', 'Mustard Oil'). "
        "If it is a general holiday or personal event, reply ONLY with 'SKIP'."
    )
    return _groq_chat_sync([{"role": "user", "content": prompt}])


def _llm_festival_fallback() -> list:
    """
    When Google Calendar credentials are unavailable, ask Groq directly
    for upcoming Indian festivals in the next 15 days and kirana stock advice.
    """
    today_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    prompt = (
        f"Today is {today_str}. You are an expert retail advisor for Indian Kirana stores. "
        "List ALL Indian festivals, regional holidays, or major events happening in the next 15 days. "
        "For each festival or event, provide a JSON array with this exact format (no extra text, just valid JSON):\n"
        '[{"festival": "Festival Name", "date": "Date string", "advice": "Stock 5 specific items like X, Y, Z for this festival"}]\n'
        "If no major festivals exist in the next 15 days, list 2-3 general seasonal demand trends instead. "
        "Always return at least 2 items. Return ONLY the JSON array."
    )
    raw = _groq_chat_sync([{"role": "user", "content": prompt}])
    try:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
    except Exception:
        pass
    return [
        {
            "festival": "General Seasonal Demand",
            "date": "Next 15 days",
            "advice": (
                "Stock up on Rice, Dal, Oil, Sugar, and Tea -- "
                "these are high-demand staples year-round. Monitor Dairy for freshness."
            ),
        }
    ]


async def run_festival_advisor() -> list:
    """Returns a list of festival-based stock recommendations for the API.

    Tries Google Calendar first. Falls back to Groq LLM if credentials
    are unavailable (credentials.json not set up).
    """
    cached = await RedisCache.get("festivals")
    if cached:
        return json.loads(cached)

    def _sync_advisor():
        if not os.path.exists(_CREDENTIALS_PATH) and not os.path.exists(_TOKEN_PATH):
            return _llm_festival_fallback()

        results = []
        try:
            service = get_calendar_service()
            events = fetch_festivals(service, days=15)
            seen = set()
            for event in events:
                name = event.get('summary', '')
                if not name or name in seen:
                    continue
                advice = get_retail_advice(name)
                if "SKIP" not in advice.upper():
                    results.append({"festival": name, "advice": advice})
                    seen.add(name)
                time.sleep(0.3)
            if not results:
                results = _llm_festival_fallback()
        except Exception:
            results = _llm_festival_fallback()
        return results

    results = await asyncio.to_thread(_sync_advisor)
    await RedisCache.set("festivals", json.dumps(results), ex=86400)
    return results


# ============================
# FULL ENGINE (Background / cron use)
# ============================

async def run_full_forecast_engine(db: AsyncSession, store_id: str = "store001") -> None:
    """Runs all three modules sequentially. Call this as a background job."""
    print("Starting Smart Vyapar Comprehensive Engine...")
    await generate_demand_forecast(db, store_id)
    await run_trend_engine(db, store_id)
    festivals = await run_festival_advisor()
    for f in festivals:
        print(f)
    print("\nAll tasks completed successfully.")