import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

# Data Processing
import pandas as pd

# Web Scraping & Trends
import requests
from bs4 import BeautifulSoup

# Firebase
import firebase_admin
from firebase_admin import credentials, firestore

# Google Calendar Auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Groq LLM
from groq import Groq


# =========================
# CONFIGURATION
# =========================
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
GROQ_API_KEY = "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"

CHECK_INTERVAL_MINUTES = 60
TREND_SCORE_THRESHOLD = 40  # Lowered slightly since we use a new scoring method

retail_keywords = [
    "toy", "drink", "chocolate", "snack", "ramen", "figure",
    "collectible", "chips", "biscuits", "juice", "cola",
    "noodles", "candy", "energy drink", "soda", "oil", "sugar", "salt", "dal"
]


# =========================
# INITIALIZATION
# =========================
# 1. Firebase
if not firebase_admin._apps:
    # Ensure 'serviceAccountKey.json' is in your directory
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()
print("✅ Firebase Connected")

# 2. Groq
groq_client = Groq(api_key=GROQ_API_KEY)


# =========================
# MODULE 1: DEMAND FORECASTING (LAYER 1)
# =========================
def generate_demand_forecast():
    print("\n📊 Starting Demand Forecasting (Layer 1)...")
    docs = db.collection("customer_sales").stream()
    data = [doc.to_dict() for doc in docs]
    
    if not data:
        print("No sales data found in Firebase.")
        return

    df = pd.DataFrame(data)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["date"] = df["timestamp"].dt.date
    
    # Calculate daily sales
    daily_sales = df.groupby(["productname", "date"])["quantity"].sum().reset_index()
    daily_sales["date"] = pd.to_datetime(daily_sales["date"])
    
    # Filter for the last 7 days
    last_date = daily_sales["date"].max()
    last_7_days = daily_sales[daily_sales["date"] >= last_date - timedelta(days=7)]
    
    predictions = {}
    for product in last_7_days["productname"].unique():
        product_data = last_7_days[last_7_days["productname"] == product].sort_values("date")
        quantities = product_data["quantity"].values
        
        if len(quantities) == 0:
            continue
            
        # Weighted average -> recent days matter more
        weights = range(1, len(quantities) + 1)
        prediction = sum(q * w for q, w in zip(quantities, weights)) / sum(weights)
        predictions[product] = round(prediction, 2)
        
    pred_df = pd.DataFrame(list(predictions.items()), columns=["productname", "predictedDemand"])
    
    # Save to Firestore
    for _, row in pred_df.iterrows():
        db.collection("demand_forecast").document(row["productname"]).set({
            "productname": row["productname"],
            "predictedDemand": float(row["predictedDemand"]),
            "updatedAt": datetime.now(timezone.utc)
        })
    print("✅ Next-day demand forecast saved to Firestore")


# =========================
# MODULE 2: TREND & SPIKE DETECTION (LAYER 2 & 3)
# =========================
def google_trends():
    """Bypass broken pytrends by using Google Trends Official RSS"""
    try:
        url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=IN"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        root = ET.fromstring(res.content)
        
        trends = []
        for item in root.findall('.//item'):
            title = item.find('title').text
            if title:
                trends.append(title)
        return trends[:10]
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
    except:
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
        except:
            continue
    return topics

def is_retail_relevant(text):
    text = text.lower()
    return any(word in text for word in retail_keywords)

def is_commercial_product(keyword):
    query = keyword + " buy"
    url = f"https://www.google.com/search?q={query.replace(' ','+')}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        if "₹" in soup.text or "Rs." in soup.text:
            return True
    except:
        return False
    return False

def detect_new_trends():
    # Gather data once to save network calls
    daily_google = google_trends()
    daily_amazon = amazon_best_sellers()
    daily_reddit = reddit_trends()
    
    candidates = list(set(daily_google + daily_amazon + daily_reddit))
    print(f"TOTAL TREND CANDIDATES: {len(candidates)}")
    
    valid = []
    for topic in candidates:
        if not is_retail_relevant(topic) or not is_commercial_product(topic):
            continue
            
        # Calculate score dynamically without pytrends
        score = 0
        if topic in daily_google:
            score += 50
        if topic in daily_amazon:
            score += 30
            
        # Add 10 points for every time it is mentioned in hot Reddit posts
        reddit_count = sum(topic.lower() in t.lower() for t in daily_reddit)
        score += reddit_count * 10
        
        if score >= TREND_SCORE_THRESHOLD:
            valid.append((topic, score))
            
    return valid

def detect_spike(product_doc):
    stock = product_doc.get("stock", 0)
    threshold = 5
    return stock < threshold

def get_inventory():
    try:
        docs = db.collection("inventory").stream()
        return [doc.to_dict() | {"id": doc.id} for doc in docs]
    except Exception:
        return []

def log_decision(product, message, confidence):
    db.collection("decisions").add({
        "productId": product,
        "message": message,
        "confidence": confidence,
        "timestamp": firestore.SERVER_TIMESTAMP,
        "agent": "Demand Intelligence"
    })

def run_trend_engine():
    print("\n🔍 Starting Trend & Spike Detection (Layers 2 & 3)...")
    inventory = get_inventory()
    
    # Layer 2: Spike detection
    if inventory:
        for product in inventory:
            if detect_spike(product):
                prod_name = product.get('productName', product['id'])
                msg = f"Low stock risk for {prod_name}"
                log_decision(prod_name, msg, 0.8)
    else:
        print("No inventory found to check for spikes.")

    # Layer 3: Trend detection
    trends = detect_new_trends()
    for topic, score in trends:
        msg = f"Trending product detected: {topic}"
        log_decision(topic, msg, min(score / 100, 1.0)) # Cap confidence at 1.0
        print(f"🔥 Valid Trend Logged: {topic} (Score: {score})")
        
    print("✅ Demand Intelligence cycle complete")


# =========================
# MODULE 3: FESTIVAL STOCK ADVISOR
# =========================
def get_calendar_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)

def fetch_festivals(service, days=15):
    now = datetime.now(timezone.utc).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

    calendar_ids = ['primary', 'en.indian#holiday@group.v.calendar.google.com']
    all_events = []

    for cal_id in calendar_ids:
        try:
            events_result = service.events().list(
                calendarId=cal_id,
                timeMin=now,
                timeMax=future,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            items = events_result.get('items', [])
            all_events.extend(items)
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
    try:
        completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
        )
        return completion.choices[0].message.content.strip()
    except:
        return "SKIP"

def run_festival_advisor():
    print("\n🎉 Starting Festival Stock Advisor...")
    try:
        service = get_calendar_service()
        events = fetch_festivals(service, days=15)
        
        found = False
        seen = set()

        for event in events:
            name = event.get('summary', '')
            if not name or name in seen: continue
            
            advice = get_retail_advice(name)
            if "SKIP" not in advice.upper():
                print(f"\n✨ {name.upper()}")
                print(advice)
                print("-" * 40)
                seen.add(name)
                found = True
            time.sleep(0.5)

        if not found:
            print("No retail festivals found in the upcoming 15 days.")
    except Exception as e:
        print(f"Festival Advisor encountered an error (did you set up credentials.json?): {e}")


# =========================
# MAIN EXECUTION
# =========================
def main():
    print("🚀 Starting Smart Vyapar Comprehensive Engine...")
    
    # 1. Generate Demand Forecast (Layer 1)
    generate_demand_forecast()
    
    # 2. Execute Trend & Spike Checks (Layer 2 & 3)
    run_trend_engine()
    
    # Optional: Display Top Amazon Sellers
    items = amazon_best_sellers()[:10]
    print("\n🛒 TOP SELLING AMAZON PRODUCTS RIGHT NOW:")
    for item in items:
        print(" •", item)
        
    # 3. Calendar Festival LLM Processing
    run_festival_advisor()
    
    print("\n✅ All tasks completed successfully.")

if __name__ == "__main__":
    main()