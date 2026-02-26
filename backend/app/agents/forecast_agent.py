"""
forecast_agent.py — Unified Demand Forecasting Agent

Includes:
  - Module 1: Demand Forecasting (reads/writes demand_forecast Firestore collection)
  - Module 2: Trend & Spike Detection (Google Trends, Amazon, Reddit)
  - Module 3: Festival Stock Advisor (Google Calendar + Groq/Llama)

The primary callable for the FastAPI endpoint is `forecast_agent(product_id)`.
"""

import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
from bs4 import BeautifulSoup
import httpx

# Firebase — shared db instance from app.core.config
from app.core.config import db

# Google Calendar Auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ============================
# CONFIGURATION
# ============================
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
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


def _groq_chat(messages: list, model: str = "llama-3.3-70b-versatile") -> str:
    """Direct httpx call to Groq REST API — no groq/openai SDK required."""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "messages": messages}
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"SKIP (error: {e})"


# ============================
# MODULE 1: DEMAND FORECASTING
# ============================
def forecast_agent(product_id: str) -> dict:
    """
    Primary callable used by FastAPI endpoints.
    Reads the pre-computed forecast from the `demand_forecast` Firestore collection.
    Enriches with product name from inventory and a human-readable restock reason.
    Falls back gracefully if no data exists yet.
    """
    try:
        doc = db.collection("demand_forecast").document(product_id).get()
        forecast_data = doc.to_dict() if doc.exists else {}

        # Always fetch inventory record to get the real product name + stock
        inv_doc = db.collection("inventory").document(product_id).get()
        inv_data = inv_doc.to_dict() if inv_doc.exists else {}

        # Resolve best available name: forecast > inventory > fallback to ID
        product_name = (
            forecast_data.get("productName")
            or inv_data.get("productName")
            or inv_data.get("name")
            or product_id
        )

        predicted_demand = round(float(forecast_data.get("predictedDemand", 0)), 2)
        current_stock = int(inv_data.get("stock", 0))
        reorder_level = int(inv_data.get("reorderLevel", 10))
        days_of_stock = round(current_stock / predicted_demand, 1) if predicted_demand > 0 else None

        # Build a human-readable reason
        if not forecast_data:
            reason = (
                f"{product_name} has not been forecasted yet. "
                f"Current stock is {current_stock} units (reorder at {reorder_level}). "
                f"Run the demand forecast pipeline to generate predictions."
            )
        elif current_stock <= reorder_level:
            urgency = "critically low" if current_stock == 0 else "below reorder threshold"
            days_msg = f" At the predicted demand of {predicted_demand} units/day, stock will last only {days_of_stock} more days." if days_of_stock else ""
            reason = (
                f"{product_name} stock is {urgency} ({current_stock} units left, reorder at {reorder_level}).{days_msg} "
                f"Recommended restock: at least {max(1, round(predicted_demand * 7))} units to cover 7 days."
            )
        elif predicted_demand > current_stock:
            reason = (
                f"{product_name} is forecasted to need {predicted_demand} units/day but only {current_stock} are in stock. "
                f"Restock soon to avoid running out."
            )
        else:
            reason = (
                f"{product_name} has {current_stock} units in stock. "
                f"Predicted demand is {predicted_demand} units/day — approximately {days_of_stock} days of stock remaining. "
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
            "updatedAt": str(forecast_data.get("updatedAt", "Not yet forecasted")),
        }

    except Exception as e:
        return {
            "productId": product_id,
            "productName": product_id,
            "predictedDemand": 0,
            "reason": f"Forecast lookup failed for {product_id}: {e}",
        }



def generate_demand_forecast():
    """
    Reads `customer_sales` from Firestore, computes a weighted 7-day demand
    forecast for each product, and saves results to `demand_forecast` collection.
    Supports both camelCase fields (productId/date) and legacy (productname/timestamp).
    """
    print("\n📊 Starting Demand Forecasting (Layer 1)...")
    docs = db.collection("customer_sales").stream()
    data = [doc.to_dict() for doc in docs]

    if not data:
        print("No sales data found in Firebase.")
        return

    df = pd.DataFrame(data)

    # Normalize date field — support 'date' (seed script) and 'timestamp' (legacy)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    elif "timestamp" in df.columns:
        df["date"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    else:
        print("No date/timestamp field in sales data.")
        return

    df["date"] = df["date"].dt.normalize()

    # Normalize product key — support 'productId' (camelCase) and 'productname' (legacy)
    if "productId" in df.columns:
        df["product_key"] = df["productId"].astype(str)
        name_map = df.groupby("productId")["productName"].first().to_dict() if "productName" in df.columns else {}
    elif "productname" in df.columns:
        df["product_key"] = df["productname"].astype(str)
        name_map = {}
    else:
        print("No product identifier field in sales data.")
        return

    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)

    daily_sales = df.groupby(["product_key", "date"])["quantity"].sum().reset_index()
    last_date = daily_sales["date"].max()
    last_7_days = daily_sales[daily_sales["date"] >= last_date - timedelta(days=7)]

    for product_key in last_7_days["product_key"].unique():
        product_data = last_7_days[last_7_days["product_key"] == product_key].sort_values("date")
        quantities = product_data["quantity"].values
        if len(quantities) == 0:
            continue

        weights = list(range(1, len(quantities) + 1))
        prediction = float(sum(float(q) * w for q, w in zip(quantities, weights)) / sum(weights))

        doc_data = {
            "productId": str(product_key),
            "predictedDemand": round(prediction, 2),
            "updatedAt": datetime.now(timezone.utc),
        }
        if str(product_key) in name_map:
            doc_data["productName"] = str(name_map[str(product_key)])

        db.collection("demand_forecast").document(str(product_key)).set(doc_data)
        print(f"  ✅ {product_key}: predicted demand = {prediction:.1f} units/day")

    print("✅ Next-day demand forecast saved to Firestore")



# ============================
# MODULE 2: TREND & SPIKE DETECTION
# ============================
def google_trends():
    try:
        url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=IN"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        root = ET.fromstring(res.content)
        return [item.find('title').text for item in root.findall('.//item') if item.find('title') is not None][:10]
    except Exception as e:
        print("Google Trends RSS fetch failed:", e)
        return []


def amazon_best_sellers():
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


def reddit_trends():
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


def is_retail_relevant(text):
    return any(word in text.lower() for word in retail_keywords)


def is_commercial_product(keyword):
    query = keyword + " buy"
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        return "₹" in soup.text or "Rs." in soup.text
    except Exception:
        return False


def detect_new_trends():
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


def detect_spike(product_doc):
    return product_doc.get("stock", 0) < 5


def get_inventory_items():
    try:
        return [doc.to_dict() | {"id": doc.id} for doc in db.collection("inventory").stream()]
    except Exception:
        return []


def log_decision(product, message, confidence):
    db.collection("decisions").add({
        "productId": product,
        "message": message,
        "confidence": confidence,
        "timestamp": datetime.now(timezone.utc),
        "agent": "Demand Intelligence"
    })


def run_trend_engine():
    print("\n🔍 Starting Trend & Spike Detection (Layers 2 & 3)...")
    inventory = get_inventory_items()
    if inventory:
        for product in inventory:
            if detect_spike(product):
                prod_name = product.get('productName', product['id'])
                log_decision(prod_name, f"Low stock risk for {prod_name}", 0.8)
    else:
        print("No inventory found to check for spikes.")

    trends = detect_new_trends()
    for topic, score in trends:
        log_decision(topic, f"Trending product detected: {topic}", min(score / 100, 1.0))
        print(f"🔥 Valid Trend Logged: {topic} (Score: {score})")
    print("✅ Demand Intelligence cycle complete")


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


def fetch_festivals(service, days=15):
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
            print(f"❌ Error fetching {cal_id}: {e}")
    return all_events


def get_retail_advice(event_name):
    prompt = (
        f"Event: {event_name}. "
        "Context: You are a retail expert for Indian Kirana stores. "
        "If this is any part of Holi (Lathmar, Holika Dahan, Dhulandi) or any major festival, "
        "list 5 MUST-STOCK items. Be very specific (e.g., 'Herbal Gulal', 'Mustard Oil'). "
    "If it is a general holiday or personal event, reply ONLY with 'SKIP'."
    )
    return _groq_chat([{"role": "user", "content": prompt}])


def _llm_festival_fallback() -> list:
    """
    When Google Calendar credentials are unavailable, ask Groq directly
    for upcoming Indian festivals in the next 15 days and kirana stock advice.
    """
    from datetime import datetime, timezone
    today_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    prompt = (
        f"Today is {today_str}. You are an expert retail advisor for Indian Kirana stores. "
        "List ALL Indian festivals, regional holidays, or major events happening in the next 15 days. "
        "For each festival or event, provide a JSON array with this exact format (no extra text, just valid JSON):\n"
        '[{"festival": "Festival Name", "date": "Date string", "advice": "Stock 5 specific items like X, Y, Z for this festival"}]\n'
        "If no major festivals exist in the next 15 days, list 2-3 general seasonal demand trends instead. "
        "Always return at least 2 items. Return ONLY the JSON array."
    )
    raw = _groq_chat([{"role": "user", "content": prompt}])
    try:
        import json
        # Extract JSON array from response
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
    except Exception:
        pass
    # If JSON parsing fails, return a structured fallback
    return [
        {
            "festival": "General Seasonal Demand",
            "date": "Next 15 days",
            "advice": "Stock up on Rice, Dal, Oil, Sugar, and Tea — these are high-demand staples year-round. Monitor Dairy for freshness."
        }
    ]


def run_festival_advisor() -> list:
    """Returns a list of festival-based stock recommendations for the API.
    
    Tries Google Calendar first. Falls back to Groq LLM if credentials
    are unavailable (credentials.json not set up).
    """
    # Fast path: if credentials file doesn't exist, skip Calendar entirely
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
        # If Google Calendar returned no actionable festivals, supplement with LLM
        if not results:
            results = _llm_festival_fallback()
    except Exception as e:
        # Any error (missing creds, network, OAuth) → graceful LLM fallback
        results = _llm_festival_fallback()
    return results


# ============================
# FULL ENGINE (Background / cron use)
# ============================
def run_full_forecast_engine():
    """Runs all three modules sequentially. Call this as a background job."""
    print("🚀 Starting Smart Vyapar Comprehensive Engine...")
    generate_demand_forecast()
    run_trend_engine()
    festivals = run_festival_advisor()
    for f in festivals:
        print(f)
    print("\n✅ All tasks completed successfully.")


if __name__ == "__main__":
    run_full_forecast_engine()