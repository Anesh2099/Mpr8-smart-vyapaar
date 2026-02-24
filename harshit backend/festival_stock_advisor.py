import datetime
import os.path
import time
from groq import Groq
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# =========================
# CONFIG
# =========================
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
GROQ_API_KEY = "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"

client = Groq(api_key=GROQ_API_KEY)

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

# =========================
# FETCH LOGIC (Improved)
# =========================

def fetch_festivals(service, days=15):
    now = datetime.datetime.now(datetime.UTC).isoformat()
    future = (datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=days)).isoformat()

    # If 'primary' isn't working, 'en.indian#holiday@group.v.calendar.google.com' is the key
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
    # This prompt is stronger—it forces the AI to recognize Indian festive demand
    prompt = (
        f"Event: {event_name}. "
        "Context: You are a retail expert for Indian Kirana stores. "
        "If this is any part of Holi (Lathmar, Holika Dahan, Dhulandi) or any major festival, "
        "list 5 MUST-STOCK items. Be very specific (e.g., 'Herbal Gulal', 'Mustard Oil'). "
        "If it is a general holiday or personal event, reply ONLY with 'SKIP'."
    )
    
    try:
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
        )
        return completion.choices[0].message.content.strip()
    except:
        return "SKIP"

def main():
    service = get_calendar_service()
    print("🔍 Searching for festivals (Feb 24 - March 11)...")
    
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
        print("No retail festivals found. Tip: Check if 'Holidays in India' is enabled in your Google Calendar settings.")

if __name__ == "__main__":
    main()