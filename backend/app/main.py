"""
app/main.py — FastAPI application with all AI agent endpoints.

Endpoint design following the spec:
  POST /agent/master/chat          ← main conversational interface
  POST /agent/inventory/run        ← NL inventory query
  GET  /agent/inventory/status     ← full inventory summary + alerts
  GET  /agent/inventory/low-stock  ← low stock items only
  GET  /agent/inventory/expiry     ← near-expiry items
  GET  /agent/supplier/{product_id}← supplier recommendations for a product
  POST /agent/supplier/run         ← NL supplier command
  GET  /agent/forecast/{product_id}← demand forecast for a product
  POST /agent/forecast/run         ← trigger full forecast pipeline
  GET  /agent/pricing/{product_id} ← pricing recommendation
  GET  /agent/cashflow/{vendor_id} ← cash flow balance
  GET  /agent/festivals            ← festival stock advisor
  GET  /agent/alerts               ← proactive alerts queue
  DELETE /agent/alerts/{alert_id}  ← dismiss an alert
  GET  /agent/chat/{session_id}    ← conversation history
  DELETE /agent/chat/{session_id}  ← clear chat history
  POST /agent/forecast/seed-data   ← run demand forecast computation
  GET  /                           ← health check
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from app.agents.master_agent import assistant_agent
from app.agents.inventory_agent import inventory_agent, check_low_stock, check_expiry, suggest_reorder
from app.agents.supplier_agent import supplier_agent
from app.agents.pricing_agent import pricing_agent
from app.agents.cashflow_agent import cashflow_agent
from app.agents.forecast_agent import forecast_agent, run_festival_advisor, generate_demand_forecast
from app.agents.proactive_agent import run_proactive_monitoring
from app.services.conversation_store import get_history, clear_history
from app.core.config import db
from app.schemas.models import ChatRequest, InventoryRunRequest, SupplierRunRequest, PricingRunRequest, ForecastRunRequest, InventoryItem

# ── Lifespan: start background monitoring on startup ──────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(run_proactive_monitoring())
    yield
    task.cancel()


app = FastAPI(
    title="KiranaIQ — Hyperlocal Vendor Intelligence API",
    description="AI-powered backend for Kirana store management: inventory, forecasting, pricing, supplier, and assistant agents.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Additional endpoints for Frontend Integration ──────────────────────────────
@app.get("/agent/supplier/list", tags=["Supplier"])
def get_supplier_list(store_id: str = "store001"):
    try:
        docs = db.collection("suppliers").limit(100).get()
        suppliers = [{"id": d.id, **d.to_dict()} for d in docs]
        return {"suppliers": suppliers}
    except Exception as e:
        return {"suppliers": [], "error": str(e)}

@app.get("/agent/supplier/orders", tags=["Supplier"])
def get_purchase_orders(store_id: str = "store001"):
    try:
        docs = db.collection("purchase_orders").limit(100).get()
        orders = [{"id": d.id, **d.to_dict()} for d in docs]
        orders = [o for o in orders if o.get("store_id") == store_id]
        
        # Sort manually to avoid filtering out records matching missing fields in DB index
        def get_sort_key(x):
            t = x.get('timestamp')
            if t:
                return t.isoformat() if hasattr(t, 'isoformat') else str(t)
            return x.get('date') or ''
        
        orders.sort(key=get_sort_key, reverse=True)
        return {"orders": orders}
    except Exception as e:
        return {"orders": [], "error": str(e)}

@app.post("/agent/supplier/orders/add", tags=["Supplier"])
def add_purchase_order(orderData: dict):
    try:
        if "store_id" not in orderData:
            orderData["store_id"] = "store001"
        from google.cloud import firestore
        orderData["timestamp"] = firestore.SERVER_TIMESTAMP
        db.collection("purchase_orders").add(orderData)
        return {"status": "success"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/agent/supplier/orders/{order_id}", tags=["Supplier"])
def delete_purchase_order(order_id: str):
    try:
        db.collection("purchase_orders").document(order_id).delete()
        return {"status": "deleted"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agent/sales/list", tags=["Sales"])
def get_sales_list(store_id: str = "store001"):
    try:
        from google.cloud import firestore
        docs = db.collection("customer_sales").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(100).get()
        sales = [{"id": d.id, **d.to_dict()} for d in docs]
        sales = [s for s in sales if s.get("store_id") == store_id or s.get("store_id") is None]
        return {"sales": sales}
    except Exception as e:
        return {"sales": [], "error": str(e)}

@app.post("/agent/sales/add", tags=["Sales"])
def add_sale(saleData: dict):
    try:
        from google.cloud import firestore
        saleData["timestamp"] = firestore.SERVER_TIMESTAMP
        db.collection("customer_sales").add(saleData)
        return {"status": "success"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/agent/sales/{sale_id}", tags=["Sales"])
def delete_sale(sale_id: str):
    try:
        db.collection("customer_sales").document(sale_id).delete()
        return {"status": "deleted"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))


# ── Assistant / Master Agent ───────────────────────────────────────────────────
@app.post("/agent/master/chat", tags=["Assistant"])
def chat(req: ChatRequest):
    """
    Main conversational interface. Accepts natural language queries,
    routes to correct agent(s), returns structured response with
    message, action_cards, alerts, and agent_trace.
    """
    return assistant_agent(
        query=req.query,
        session_id=req.session_id,
        store_id=req.store_id,
    )


# Keep backward-compatible endpoint
@app.post("/assistant", tags=["Assistant"])
def chat_legacy(req: ChatRequest):
    """Backward-compatible alias for /agent/master/chat."""
    return assistant_agent(query=req.query, session_id=req.session_id, store_id=req.store_id)


# ── Chat History ──────────────────────────────────────────────────────────────
@app.get("/agent/chat/{session_id}", tags=["Assistant"])
def get_chat_history(session_id: str):
    """Return conversation history for a session."""
    return {"session_id": session_id, "history": get_history(session_id)}


@app.delete("/agent/chat/{session_id}", tags=["Assistant"])
def delete_chat_history(session_id: str):
    """Clear conversation history for a session."""
    clear_history(session_id)
    return {"session_id": session_id, "status": "cleared"}


# ── Inventory Agent ───────────────────────────────────────────────────────────
@app.get("/agent/inventory/status", tags=["Inventory"])
def inventory_status(store_id: str = "store001"):
    """Full inventory summary with stock levels, alerts, and product list."""
    return inventory_agent(store_id=store_id)


@app.post("/agent/inventory/run", tags=["Inventory"])
def inventory_run(req: InventoryRunRequest):
    """Natural language inventory query — e.g. 'How much milk do I have?'"""
    return inventory_agent(query=req.query, store_id=req.store_id)


@app.get("/agent/inventory/low-stock", tags=["Inventory"])
def inventory_low_stock(store_id: str = "store001"):
    """Return all products below reorder threshold with reorder recommendations."""
    return {"low_stock_items": check_low_stock(store_id=store_id)}


@app.get("/agent/inventory/expiry", tags=["Inventory"])
def inventory_expiry(store_id: str = "store001"):
    """Return near-expiry items with clearance suggestions."""
    return {"expiring_items": check_expiry(store_id=store_id)}


@app.get("/agent/inventory/reorder/{product_id}", tags=["Inventory"])
def inventory_reorder(product_id: str):
    """Calculate recommended reorder quantity for a product."""
    return suggest_reorder(product_id)


@app.post("/agent/inventory/add", tags=["Inventory"])
def add_inventory_item(item: InventoryItem):
    """Add a new product to the inventory collection."""
    try:
        data = item.dict()
        data["product_id"] = data["sku"].lower().replace(" ", "-")
        # Ensure consistent naming
        data["name"] = data["productName"] 
        db.collection("inventory").document(data["product_id"]).set(data)
        return {"status": "success", "product_id": data["product_id"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/agent/inventory/edit/{product_id}", tags=["Inventory"])
def edit_inventory_item(product_id: str, item: InventoryItem):
    """Update an existing product in the inventory collection."""
    try:
        data = item.dict()
        data["name"] = data["productName"] 
        db.collection("inventory").document(product_id).set(data, merge=True)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/agent/inventory/delete/{product_id}", tags=["Inventory"])
def delete_inventory_item(product_id: str):
    """Delete a product from the inventory collection."""
    try:
        db.collection("inventory").document(product_id).delete()
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Legacy endpoint
@app.get("/inventory", tags=["Inventory"])
def inventory_legacy(store_id: str = "store001"):
    return inventory_agent(store_id=store_id)


# ── Supplier Agent ────────────────────────────────────────────────────────────
@app.get("/agent/supplier/{product_id}", tags=["Supplier"])
def supplier_by_product(product_id: str, quantity: Optional[int] = None, budget: Optional[float] = None):
    """Find and rank suppliers for a specific product."""
    return supplier_agent(product_id=product_id, quantity=quantity, budget=budget)


@app.post("/agent/supplier/run", tags=["Supplier"])
def supplier_run(req: SupplierRunRequest):
    """Natural language supplier command — e.g. 'Find me 20 units of sugar under ₹500'"""
    return supplier_agent(
        product_id=req.product_id,
        query=req.query,
    )


# Legacy endpoint
@app.get("/supplier/{product_id}", tags=["Supplier"])
def supplier_legacy(product_id: str):
    return supplier_agent(product_id=product_id)


# ── Forecast Agent ────────────────────────────────────────────────────────────
@app.get("/agent/forecast/{product_id}", tags=["Forecast"])
def forecast_by_product(product_id: str):
    """Return pre-computed demand forecast for a specific product."""
    return forecast_agent(product_id)


@app.post("/agent/forecast/run", tags=["Forecast"])
def forecast_run(background_tasks: BackgroundTasks):
    """Trigger full demand forecast pipeline for all products (runs in background)."""
    background_tasks.add_task(generate_demand_forecast)
    return {"status": "Forecast pipeline started in background."}


# Legacy endpoints
@app.get("/forecast/{product_id}", tags=["Forecast"])
def forecast_legacy(product_id: str):
    return forecast_agent(product_id)

@app.post("/forecast/run", tags=["Forecast"])
def forecast_run_legacy(background_tasks: BackgroundTasks):
    background_tasks.add_task(generate_demand_forecast)
    return {"status": "Forecast pipeline started."}


# ── Pricing Agent ─────────────────────────────────────────────────────────────
@app.get("/agent/pricing/{product_id}", tags=["Pricing"])
def pricing_by_product(product_id: str, store_id: str = "store001"):
    """Dynamic pricing recommendation with multi-factor analysis and explanation."""
    return pricing_agent(product_id, store_id=store_id)


# Legacy endpoint
@app.get("/pricing/{product_id}", tags=["Pricing"])
def pricing_legacy(product_id: str):
    return pricing_agent(product_id)


# ── Cashflow Agent ────────────────────────────────────────────────────────────
@app.get("/agent/cashflow/{vendor_id}", tags=["Cashflow"])
def cashflow_by_vendor(vendor_id: str):
    """Return cash flow balance for a vendor."""
    return cashflow_agent(vendor_id)


# Legacy endpoint
@app.get("/cashflow/{vendor_id}", tags=["Cashflow"])
def cashflow_legacy(vendor_id: str):
    return cashflow_agent(vendor_id)


# ── Festival Advisor ──────────────────────────────────────────────────────────
@app.get("/agent/festivals", tags=["Forecast"])
def festival_advice():
    """Festival-based restocking advice for the next 15 days."""
    return run_festival_advisor()


# Legacy endpoint
@app.get("/festivals", tags=["Forecast"])
def festivals_legacy():
    return run_festival_advisor()


# ── Proactive Alerts ──────────────────────────────────────────────────────────
@app.get("/agent/alerts", tags=["Alerts"])
def get_alerts(store_id: str = "store001", limit: int = 20):
    """Fetch all pending (non-dismissed) proactive alerts for a store."""
    try:
        docs = (
            db.collection("proactive_alerts")
            .where("store_id", "==", store_id)
            .where("dismissed", "==", False)
            .limit(limit)
            .get()
        )
        alerts = []
        for doc in docs:
            a = doc.to_dict()
            a["alert_id"] = doc.id
            alerts.append(a)
        return {"alerts": alerts, "count": len(alerts)}
    except Exception as e:
        return {"alerts": [], "error": str(e)}


@app.delete("/agent/alerts/{alert_id}", tags=["Alerts"])
def dismiss_alert(alert_id: str):
    """Mark an alert as dismissed."""
    try:
        db.collection("proactive_alerts").document(alert_id).update({"dismissed": True})
        return {"alert_id": alert_id, "status": "dismissed"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Alert not found: {e}")


# ── Sales Update ──────────────────────────────────────────────────────────────
@app.put("/agent/sales/{sale_id}", tags=["Sales"])
def update_sale(sale_id: str, data: dict):
    """Update an existing sale record in Firestore."""
    try:
        ref = db.collection("sales").document(sale_id)
        doc = ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail=f"Sale {sale_id} not found")
        ref.update(data)
        updated = ref.get().to_dict()
        updated["id"] = sale_id
        return {"status": "updated", "sale": updated}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Health Check ──────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {
        "status": "KiranaIQ AI Backend is running 🚀",
        "version": "2.0.0",
        "agents": ["master", "inventory", "supplier", "forecast", "pricing", "cashflow"],
        "docs": "/docs"
    }