"""
seed_suppliers.py — Seed the Firestore `suppliers` collection with test data.

Run once from the backend directory:
    python seed_suppliers.py

This creates realistic sample suppliers for testing the Supplier Agent.
"""

import os
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

import firebase_admin
from firebase_admin import credentials, firestore

cred_path = os.path.abspath("serviceAccountKey.json")
if not firebase_admin._apps:
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()

SUPPLIERS = [
    {
        "supplierName": "Ramesh General Traders",
        "contact": "+91-9876543210",
        "products": ["milk", "curd", "butter", "paneer", "ghee"],
        "price_per_unit": 52.0,
        "reliability": 4,
        "leadTimeDays": "1-2",
        "location": "Mumbai",
        "notes": "Fresh dairy daily. Minimum order: 10 units.",
    },
    {
        "supplierName": "Suresh Agro Suppliers",
        "contact": "+91-9123456789",
        "products": ["wheat", "rice", "sugar", "dal", "flour", "atta"],
        "price_per_unit": 45.0,
        "reliability": 5,
        "leadTimeDays": "2-3",
        "location": "Pune",
        "notes": "Direct farm sourcing. Bulk discounts available.",
    },
    {
        "supplierName": "Kewal Oil & Spices",
        "contact": "+91-9988776655",
        "products": ["cooking oil", "sunflower oil", "mustard oil", "spices", "salt"],
        "price_per_unit": 130.0,
        "reliability": 4,
        "leadTimeDays": "2-4",
        "location": "Nashik",
        "notes": "Premium quality oils. No minimum order.",
    },
    {
        "supplierName": "City Beverages Hub",
        "contact": "+91-9898989898",
        "products": ["cold drinks", "juice", "water", "soda", "energy drink"],
        "price_per_unit": 30.0,
        "reliability": 3,
        "leadTimeDays": "1",
        "location": "Mumbai",
        "notes": "Same-day delivery available. High demand products.",
    },
    {
        "supplierName": "Dev Snacks & Namkeen",
        "contact": "+91-9776655443",
        "products": ["biscuits", "chips", "namkeen", "chocolate", "candy"],
        "price_per_unit": 25.0,
        "reliability": 4,
        "leadTimeDays": "2",
        "location": "Thane",
        "notes": "Popular FMCG brands stocked. Weekly restocking.",
    },
    {
        "supplierName": "Global Dairy Fresh",
        "contact": "+91-9001122334",
        "products": ["milk", "buttermilk", "lassi", "cheese", "cream"],
        "price_per_unit": 48.0,
        "reliability": 5,
        "leadTimeDays": "1",
        "location": "Mumbai",
        "notes": "ISO certified dairy. Best for premium customers.",
    },
]

print("Seeding 'suppliers' collection...")
for s in SUPPLIERS:
    doc_ref = db.collection("suppliers").add(s)
    print(f"  ✅ Added: {s['supplierName']}")

print(f"\nDone! {len(SUPPLIERS)} suppliers added to Firestore.")
