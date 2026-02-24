from google import genai

# 1. Initialize the Client (The new way)
client = genai.Client(api_key="AIzaSyAr3hqqprcEzGmSXTCZUrwThwhf5PBsx_s")

try:
    # 2. Generate content using a simple string for the model name
    response = client.models.generate_content(
        model="gemini-2.0-flash", 
        contents="Hello! Are you working now?"
    )
    
    print("✅ API KEY SUCCESS!")
    print(f"Response: {response.text}")

except Exception as e:
    print(f"❌ API KEY FAILED\n\n{e}")