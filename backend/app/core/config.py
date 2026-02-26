import os

# MUST be set before importing firebase_admin — forces pure-Python protobuf
# which is compatible with protobuf 6.x on Python 3.11
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

# Load environment variables from backend root .env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

# Absolute path to serviceAccountKey.json at backend root
_SA_KEY_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "serviceAccountKey.json")
)

if not firebase_admin._apps:
    cred = credentials.Certificate(_SA_KEY_PATH)
    firebase_admin.initialize_app(cred)

db = firestore.client()