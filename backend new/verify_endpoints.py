import time
import requests

BASE_URL = "http://127.0.0.1:8000"

def measure_time(func, *args, **kwargs):
    start = time.time()
    res = func(*args, **kwargs)
    end = time.time()
    return res, end - start

print("====================================")
print("TESTING REDIS CACHING & FASTAPI ROUTES")
print("====================================")

# 1. API Health
print("\n[1] Health Check")
res, dt = measure_time(requests.get, f"{BASE_URL}/")
print(f"Health status: {res.status_code} in {dt:.3f}s")
if res.status_code == 200:
    print(res.json())

# 2. Test Festivals endpoint (Heavy computation, caches to Redis for 24 hours)
print("\n[2] Festival Advisor Loading & Caching")
res1, dt1 = measure_time(requests.get, f"{BASE_URL}/agent/festivals")
print(f"First request (Cold Cache): {dt1:.3f}s [Status: {res1.status_code}]")

res2, dt2 = measure_time(requests.get, f"{BASE_URL}/agent/festivals")
print(f"Second request (Warm Cache): {dt2:.3f}s [Status: {res2.status_code}]")
if dt2 < (dt1 / 2) and dt2 < 0.1:
     print(">> CACHE HIT CONFIRMED: Sub-100ms response.")
else:
     print(">> WARNING: No massive speedup. Check if Redis server is running locally.")

# 3. Test Alerts endpoints
print("\n[3] Alerts Caching & Validation")
res1, dt1 = measure_time(requests.get, f"{BASE_URL}/agent/alerts")
print(f"First Alerts request: {dt1:.3f}s")

res2, dt2 = measure_time(requests.get, f"{BASE_URL}/agent/alerts")
print(f"Second Alerts request: {dt2:.3f}s")
# Optional check: Did it hit cache?

# 4. Master Agent Chat test
print("\n[4] PostgreSQL DB Integration (Chat Agent Test)")
payload = {"message": "show pricing for prod_003", "session_id": "test_verification"}
resp, dt = measure_time(requests.post, f"{BASE_URL}/agent/master/chat", json=payload)
print(f"Master Agent response in {dt:.3f}s")
print(f"Chat status: {resp.status_code}")
if resp.status_code == 200:
    print("Response preview:", str(resp.json())[:200])

print("\n====================================")
print("TESTING COMPLETE")
print("====================================")
