from app.core.config import db
from google.cloud.firestore_v1 import FieldFilter

def cashflow_agent(vendor_id: str) -> dict:
    records = db.collection("cashflow") \
        .where(filter=FieldFilter("vendorId", "==", vendor_id)) \
        .stream()

    records = [r.to_dict() for r in records]
    balance = sum(r.get("inflow", 0) for r in records) - sum(r.get("outflow", 0) for r in records)

    return {
        "vendorId": vendor_id,
        "balance": balance
    }