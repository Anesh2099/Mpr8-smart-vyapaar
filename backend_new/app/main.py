"""
app/main.py -- FastAPI application with all AI agent endpoints.

Endpoint design:
  POST /agent/master/chat          <- main conversational interface
  POST /agent/inventory/run        <- NL inventory query
  GET  /agent/inventory/status     <- full inventory summary + alerts
  GET  /agent/inventory/low-stock  <- low stock items only
  GET  /agent/inventory/expiry     <- near-expiry items
  GET  /agent/inventory/reorder/{product_id} <- reorder calculation
  POST /agent/inventory/add        <- add inventory item
  PUT  /agent/inventory/edit/{product_id}    <- edit inventory item
  DELETE /agent/inventory/delete/{product_id}<- delete inventory item
  GET  /agent/supplier/list        <- list all suppliers
  GET  /agent/supplier/orders      <- list purchase orders
  POST /agent/supplier/orders/add  <- add purchase order
  DELETE /agent/supplier/orders/{order_id}   <- delete purchase order
  GET  /agent/supplier/{product_id}<- supplier recommendations
  POST /agent/supplier/run         <- NL supplier command
  GET  /agent/forecast/{product_id}<- demand forecast for a product
  POST /agent/forecast/run         <- trigger full forecast pipeline
  POST /agent/forecast/seed-data   <- alias for forecast/run
  GET  /agent/pricing/{product_id} <- pricing recommendation
  GET  /agent/cashflow/{vendor_id} <- cash flow balance
  GET  /agent/festivals            <- festival stock advisor
  GET  /agent/alerts               <- proactive alerts queue
  DELETE /agent/alerts/{alert_id}  <- dismiss an alert
  GET  /agent/sales/list           <- list all sales
  POST /agent/sales/add            <- add a sale
  DELETE /agent/sales/{sale_id}    <- delete a sale
  PUT  /agent/sales/{sale_id}      <- update a sale
  GET  /agent/chat/{session_id}    <- conversation history
  DELETE /agent/chat/{session_id}  <- clear chat history
  GET  /                           <- health check
"""

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, AsyncSessionLocal
from app.models import (
    CustomerSale, SaleItem, Inventory, PurchaseOrder,
    OrderItem, Supplier, ProactiveAlert,
)
from app.agents.master_agent import assistant_agent
from app.agents.inventory_agent import (
    inventory_agent, check_low_stock, check_expiry, suggest_reorder
)
from app.agents.supplier_agent import supplier_agent, discover_suppliers
from app.agents.pricing_agent import pricing_agent
from app.agents.cashflow_agent import cashflow_agent
from app.agents.forecast_agent import (
    forecast_agent, run_festival_advisor, generate_demand_forecast
)
from app.agents.proactive_agent import run_proactive_monitoring
from app.routers.metrics import router as metrics_router
from app.services.db_service import get_active_alerts, dismiss_alert as db_dismiss_alert
from app.services.conversation_store import get_history, clear_history
from app.core.cache import RedisCache
from app.schemas.models import (
    ChatRequest, InventoryRunRequest, SupplierRunRequest,
    PricingRunRequest, ForecastRunRequest, InventoryItem,
)


# -- Background: daily inventory snapshot --------------------------------------
async def snapshot_inventory():
    """Snapshot current inventory levels every 24 hours for historical charts."""
    from datetime import date as _date
    from app.models import InventorySnapshot
    while True:
        await asyncio.sleep(86400)  # 24 hours
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Inventory))
                for item in result.scalars().all():
                    snap = InventorySnapshot(
                        product_name=item.product_name,
                        stock_level=int(item.stock or 0),
                        snapshot_date=_date.today(),
                    )
                    db.add(snap)
                await db.commit()
        except Exception:
            pass  # Never crash the background task


# -- Lifespan: start background monitoring on startup -------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize redis
    RedisCache.get_instance()
    task = asyncio.create_task(run_proactive_monitoring())
    snap_task = asyncio.create_task(snapshot_inventory())
    yield
    task.cancel()
    snap_task.cancel()
    await RedisCache.close()


app = FastAPI(
    title="KiranaIQ -- Hyperlocal Vendor Intelligence API",
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

# Register metrics router
app.include_router(metrics_router, prefix="/agent/metrics", tags=["Metrics"])


# =============================================================================
# Assistant / Master Agent
# =============================================================================

@app.post("/agent/master/chat", tags=["Assistant"])
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    Main conversational interface. Accepts natural language queries,
    routes to correct agent(s), returns structured response with
    message, action_cards, alerts, and agent_trace.
    """
    return await assistant_agent(
        db=db,
        query=req.query,
        session_id=req.session_id,
        store_id=req.store_id,
    )


@app.post("/assistant", tags=["Assistant"])
async def chat_legacy(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Backward-compatible alias for /agent/master/chat."""
    return await assistant_agent(
        db=db,
        query=req.query,
        session_id=req.session_id,
        store_id=req.store_id,
    )


# =============================================================================
# Chat History
# =============================================================================

@app.get("/agent/chat/{session_id}", tags=["Assistant"])
def get_chat_history(session_id: str):
    """Return conversation history for a session."""
    return {"session_id": session_id, "history": get_history(session_id)}


@app.delete("/agent/chat/{session_id}", tags=["Assistant"])
def delete_chat_history(session_id: str):
    """Clear conversation history for a session."""
    clear_history(session_id)
    return {"session_id": session_id, "status": "cleared"}


# =============================================================================
# Inventory Agent
# =============================================================================

@app.get("/agent/inventory/list", tags=["Inventory"])
async def inventory_list(
    store_id: str = "store001",
    db: AsyncSession = Depends(get_db),
):
    """Fast lightweight inventory list — no AI agent, no alert writes.
    Returns products with computed status flags but skips LLM and alert persistence."""
    try:
        result = await db.execute(
            select(Inventory).where(Inventory.store_id == store_id)
        )
        rows = result.scalars().all()
        products = []
        low_stock_count = 0
        for r in rows:
            stock = float(r.stock or 0)
            reorder_level = float(r.reorder_level or 10)
            is_low = stock < reorder_level
            if is_low:
                low_stock_count += 1
            products.append({
                "id": str(r.id),
                "product_id": r.product_id,
                "product_name": r.product_name,
                "sku": r.sku,
                "stock": stock,
                "reorder_level": reorder_level,
                "price": float(r.price) if r.price is not None else None,
                "wholesale_cost": float(r.wholesale_cost) if r.wholesale_cost is not None else None,
                "supplier": r.supplier,
                "category": r.category,
                "is_low_stock": is_low,
                "stock_status": "critical" if stock == 0 else ("low" if is_low else "ok"),
            })
        return {
            "agent": "inventory",
            "store_id": store_id,
            "message": f"Inventory loaded: {len(products)} products.",
            "products": products,
            "low_stock_count": low_stock_count,
        }
    except Exception as e:
        return {"products": [], "error": str(e)}


@app.get("/agent/inventory/status", tags=["Inventory"])
async def inventory_status(
    store_id: str = "store001",
    db: AsyncSession = Depends(get_db),
):
    """Full inventory summary with stock levels, alerts, and product list."""
    return await inventory_agent(db, store_id=store_id)


@app.post("/agent/inventory/run", tags=["Inventory"])
async def inventory_run(
    req: InventoryRunRequest,
    db: AsyncSession = Depends(get_db),
):
    """Natural language inventory query -- e.g. 'How much milk do I have?'"""
    return await inventory_agent(db, query=req.query, store_id=req.store_id)


@app.get("/agent/inventory/low-stock", tags=["Inventory"])
async def inventory_low_stock(
    store_id: str = "store001",
    db: AsyncSession = Depends(get_db),
):
    """Return all products below reorder threshold with reorder recommendations."""
    return {"low_stock_items": await check_low_stock(db, store_id=store_id)}


@app.get("/agent/inventory/expiry", tags=["Inventory"])
async def inventory_expiry(
    store_id: str = "store001",
    db: AsyncSession = Depends(get_db),
):
    """Return near-expiry items with clearance suggestions."""
    return {"expiring_items": await check_expiry(db, store_id=store_id)}


@app.get("/agent/inventory/reorder/{product_id}", tags=["Inventory"])
async def inventory_reorder(
    product_id: str,
    store_id: str = "store001",
    db: AsyncSession = Depends(get_db),
):
    """Calculate recommended reorder quantity for a product."""
    return await suggest_reorder(db, product_id, store_id=store_id)


@app.post("/agent/inventory/add", tags=["Inventory"])
async def add_inventory_item(
    item: InventoryItem,
    store_id: str = "store001",
    db: AsyncSession = Depends(get_db),
):
    """Add a new product to the inventory table."""
    try:
        data = item.dict()
        product_id = data.get("sku", "").lower().replace(" ", "-") or str(uuid.uuid4())
        row = Inventory(
            id=uuid.uuid4(),
            store_id=store_id,
            product_id=product_id,
            product_name=data.get("productName") or data.get("product_name", ""),
            sku=data.get("sku"),
            stock=float(data.get("stock", 0)),
            reorder_level=float(data.get("reorderLevel") or data.get("reorder_level") or 10),
            price=float(data["price"]) if data.get("price") is not None else None,
            wholesale_cost=float(data["wholesaleCost"]) if data.get("wholesaleCost") is not None else None,
            supplier=data.get("supplier"),
            category=data.get("category"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(row)
        await db.commit()
        return {"status": "success", "product_id": product_id}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/agent/inventory/edit/{product_id}", tags=["Inventory"])
async def edit_inventory_item(
    product_id: str,
    item: InventoryItem,
    store_id: str = "store001",
    db: AsyncSession = Depends(get_db),
):
    """Update an existing product in the inventory table."""
    try:
        data = item.dict()
        await db.execute(
            update(Inventory)
            .where(Inventory.product_id == product_id, Inventory.store_id == store_id)
            .values(
                product_name=data.get("productName") or data.get("product_name"),
                sku=data.get("sku"),
                stock=float(data.get("stock", 0)),
                reorder_level=float(data.get("reorderLevel") or data.get("reorder_level") or 10),
                price=float(data["price"]) if data.get("price") is not None else None,
                wholesale_cost=float(data["wholesaleCost"]) if data.get("wholesaleCost") is not None else None,
                supplier=data.get("supplier"),
                category=data.get("category"),
                updated_at=datetime.utcnow(),
            )
        )
        await db.commit()
        return {"status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/agent/inventory/update-price/{product_id}", tags=["Inventory"])
async def update_product_price(
    product_id: str,
    body: dict,
    store_id: str = "store001",
    db: AsyncSession = Depends(get_db),
):
    """Lightweight partial update — primarily for applying new prices from the Pricing page.
    Accepts a JSON body with any subset of fields: {price, stock, reorder_level, ...}"""
    try:
        allowed = {}
        if "price" in body and body["price"] is not None:
            allowed["price"] = float(body["price"])
        if "stock" in body:
            allowed["stock"] = float(body["stock"])
        if "reorder_level" in body:
            allowed["reorder_level"] = float(body["reorder_level"])
        if not allowed:
            raise HTTPException(status_code=400, detail="No valid fields to update")

        allowed["updated_at"] = datetime.utcnow()

        result = await db.execute(
            update(Inventory)
            .where(Inventory.product_id == product_id, Inventory.store_id == store_id)
            .values(**allowed)
        )
        await db.commit()

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

        return {"status": "success", "product_id": product_id, "updated_fields": list(allowed.keys())}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/agent/inventory/delete/{product_id}", tags=["Inventory"])
async def delete_inventory_item(
    product_id: str,
    store_id: str = "store001",
    db: AsyncSession = Depends(get_db),
):
    """Delete a product from the inventory table."""
    try:
        await db.execute(
            delete(Inventory).where(
                Inventory.product_id == product_id,
                Inventory.store_id == store_id,
            )
        )
        await db.commit()
        return {"status": "deleted"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))



# Legacy endpoints
@app.get("/inventory", tags=["Inventory"])
async def inventory_legacy(store_id: str = "store001", db: AsyncSession = Depends(get_db)):
    return await inventory_agent(db, store_id=store_id)


# =============================================================================
# Supplier Agent
# =============================================================================

@app.get("/agent/supplier/list", tags=["Supplier"])
async def get_supplier_list(
    store_id: str = "store001",
    db: AsyncSession = Depends(get_db),
):
    """Return all suppliers for a store."""
    try:
        result = await db.execute(
            select(Supplier).where(Supplier.store_id == store_id).limit(100)
        )
        rows = result.scalars().all()
        suppliers = [
            {
                "id": str(r.id),
                "supplier_name": r.supplier_name,
                "products": r.products or [],
                "price_per_unit": r.price_per_unit,
                "reliability": r.reliability,
                "contact": r.contact,
                "lead_time_days": r.lead_time_days,
                "store_id": r.store_id,
            }
            for r in rows
        ]
        return {"suppliers": suppliers}
    except Exception as e:
        return {"suppliers": [], "error": str(e)}


@app.get("/agent/supplier/orders", tags=["Supplier"])
async def get_purchase_orders(
    store_id: str = "store001",
    db: AsyncSession = Depends(get_db),
):
    """Return all purchase orders for a store, newest first."""
    try:
        result = await db.execute(
            select(PurchaseOrder)
            .where(PurchaseOrder.store_id == store_id)
            .order_by(PurchaseOrder.order_date.desc())
            .limit(100)
        )
        rows = result.scalars().all()
        orders = [
            {
                "id": str(r.id),
                "supplier": r.supplier,
                "status": r.status,
                "total_amount": r.total_amount,
                "order_date": str(r.order_date),
                "store_id": r.store_id,
            }
            for r in rows
        ]
        return {"orders": orders}
    except Exception as e:
        return {"orders": [], "error": str(e)}


@app.post("/agent/supplier/orders/add", tags=["Supplier"])
async def add_purchase_order(
    orderData: dict,
    db: AsyncSession = Depends(get_db),
):
    """Add a new purchase order."""
    try:
        store_id = orderData.get("store_id", "store001")
        order_id = uuid.uuid4()
        order = PurchaseOrder(
            id=order_id,
            store_id=store_id,
            supplier=orderData.get("supplier", "Unknown"),
            status=orderData.get("status", "pending"),
            total_amount=float(orderData["total_amount"]) if orderData.get("total_amount") is not None else None,
            order_date=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        db.add(order)
        for item in orderData.get("items", []):
            oi = OrderItem(
                id=uuid.uuid4(),
                order_id=order_id,
                product_name=str(item.get("product_name") or item.get("productName") or ""),
                quantity=float(item.get("quantity", 0)),
                unit_price=float(item["unit_price"]) if item.get("unit_price") is not None else None,
            )
            db.add(oi)
        await db.commit()
        return {"status": "success", "order_id": str(order_id)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/agent/supplier/orders/{order_id}", tags=["Supplier"])
async def delete_purchase_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a purchase order."""
    try:
        await db.execute(
            delete(OrderItem).where(OrderItem.order_id == uuid.UUID(order_id))
        )
        await db.execute(
            delete(PurchaseOrder).where(PurchaseOrder.id == uuid.UUID(order_id))
        )
        await db.commit()
        return {"status": "deleted"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agent/supplier/{product_id}", tags=["Supplier"])
async def supplier_by_product(
    product_id: str,
    quantity: Optional[int] = None,
    budget: Optional[float] = None,
    store_id: str = "store001",
    db: AsyncSession = Depends(get_db),
):
    """Find and rank suppliers for a specific product."""
    return await supplier_agent(
        db, store_id=store_id,
        product_id=product_id, quantity=quantity, budget=budget,
    )


@app.post("/agent/supplier/run", tags=["Supplier"])
async def supplier_run(
    req: SupplierRunRequest,
    db: AsyncSession = Depends(get_db),
):
    """Natural language supplier command -- e.g. 'Find me 20 units of sugar under Rs.500'"""
    return await supplier_agent(db, product_id=req.product_id, query=req.query)


# Legacy
@app.get("/supplier/{product_id}", tags=["Supplier"])
async def supplier_legacy(product_id: str, db: AsyncSession = Depends(get_db)):
    return await supplier_agent(db, product_id=product_id)


# =============================================================================
# Forecast Agent
# =============================================================================

@app.get("/agent/forecast/{product_id}", tags=["Forecast"])
async def forecast_by_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return pre-computed demand forecast for a specific product."""
    return await forecast_agent(db, product_id)


@app.post("/agent/forecast/run", tags=["Forecast"])
async def forecast_run(
    background_tasks: BackgroundTasks,
    store_id: str = "store001",
):
    """Trigger full demand forecast pipeline for all products (runs in background)."""
    async def _bg():
        async with AsyncSessionLocal() as db:
            await generate_demand_forecast(db, store_id)

    background_tasks.add_task(_bg)
    return {"status": "Forecast pipeline started in background."}


@app.post("/agent/forecast/seed-data", tags=["Forecast"])
async def forecast_seed(
    background_tasks: BackgroundTasks,
    store_id: str = "store001",
):
    """Alias for /agent/forecast/run — triggers demand forecast computation."""
    async def _bg():
        async with AsyncSessionLocal() as db:
            await generate_demand_forecast(db, store_id)

    background_tasks.add_task(_bg)
    return {"status": "Forecast seed started in background."}


# Legacy
@app.get("/forecast/{product_id}", tags=["Forecast"])
async def forecast_legacy(product_id: str, db: AsyncSession = Depends(get_db)):
    return await forecast_agent(db, product_id)


@app.post("/forecast/run", tags=["Forecast"])
async def forecast_run_legacy(background_tasks: BackgroundTasks, store_id: str = "store001"):
    async def _bg():
        async with AsyncSessionLocal() as db:
            await generate_demand_forecast(db, store_id)
    background_tasks.add_task(_bg)
    return {"status": "Forecast pipeline started."}


# =============================================================================
# Pricing Agent
# =============================================================================

@app.get("/agent/pricing/{product_id}", tags=["Pricing"])
async def pricing_by_product(
    product_id: str,
    store_id: str = "store001",
    db: AsyncSession = Depends(get_db),
):
    """Dynamic pricing recommendation with multi-factor analysis and explanation."""
    return await pricing_agent(db, product_id, store_id=store_id)


# Legacy
@app.get("/pricing/{product_id}", tags=["Pricing"])
async def pricing_legacy(product_id: str, db: AsyncSession = Depends(get_db)):
    return await pricing_agent(db, product_id)


# =============================================================================
# Cashflow Agent
# =============================================================================

@app.get("/agent/cashflow/{vendor_id}", tags=["Cashflow"])
async def cashflow_by_vendor(
    vendor_id: str,
    store_id: str = "store001",
    db: AsyncSession = Depends(get_db),
):
    """Return cash flow balance for a store."""
    return await cashflow_agent(db, store_id=store_id)


# Legacy
@app.get("/cashflow/{vendor_id}", tags=["Cashflow"])
async def cashflow_legacy(vendor_id: str, db: AsyncSession = Depends(get_db)):
    return await cashflow_agent(db)


# =============================================================================
# Festival Advisor
# =============================================================================

@app.get("/agent/festivals", tags=["Forecast"])
async def festival_advice():
    """Festival-based restocking advice for the next 15 days."""
    return await run_festival_advisor()


@app.get("/festivals", tags=["Forecast"])
async def festivals_legacy():
    return await run_festival_advisor()


# =============================================================================
# Proactive Alerts
# =============================================================================

@app.get("/agent/alerts", tags=["Alerts"])
async def get_alerts(
    store_id: str = "store001",
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Fetch all pending (non-dismissed) proactive alerts for a store."""
    try:
        rows = await get_active_alerts(db, store_id)
        alerts = []
        for row in rows[:limit]:
            alerts.append({
                "alert_id":         str(row.id),
                "alert_type":       row.alert_type,
                "severity":         row.severity,
                "product_id":       str(row.product_id) if row.product_id else None,
                "product_name":     row.product_name,
                "message":          row.message,
                "suggested_action": row.suggested_action,
                "dismissed":        row.dismissed,
                "created_at":       str(row.created_at),
                "store_id":         row.store_id,
            })
        return {"alerts": alerts, "count": len(alerts)}
    except Exception as e:
        return {"alerts": [], "error": str(e)}


@app.delete("/agent/alerts/{alert_id}", tags=["Alerts"])
async def dismiss_alert_endpoint(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Mark an alert as dismissed."""
    try:
        await db_dismiss_alert(db, alert_id)
        return {"alert_id": alert_id, "status": "dismissed"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Alert not found or dismiss failed: {e}")


# =============================================================================
# Sales
# =============================================================================

@app.get("/agent/sales/list", tags=["Sales"])
async def get_sales_list(
    store_id: str = "store001",
    db: AsyncSession = Depends(get_db),
):
    """Return all sales (newest first) for a store, with items eagerly loaded."""
    try:
        from sqlalchemy.orm import selectinload
        result = await db.execute(
            select(CustomerSale)
            .options(selectinload(CustomerSale.items))
            .where(CustomerSale.store_id == store_id)
            .order_by(CustomerSale.sale_date.desc())
            .limit(100)
        )
        rows = result.unique().scalars().all()
        sales = []
        for r in rows:
            sale_items = []
            if hasattr(r, 'items') and r.items:
                for si in r.items:
                    sale_items.append({
                        "name": si.product_name,
                        "quantity": si.quantity,
                        "price": si.price,
                    })
            sales.append({
                "id":             str(r.id),
                "customer":       r.customer,
                "total":          r.total,
                "payment_method": r.payment_method,
                "paymentMethod":  r.payment_method,
                "sale_date":      str(r.sale_date),
                "date":           str(r.sale_date).split(" ")[0] if r.sale_date else None,
                "store_id":       r.store_id,
                "items":          sale_items,
            })
        return {"sales": sales}
    except Exception as e:
        return {"sales": [], "error": str(e)}


@app.post("/agent/sales/add", tags=["Sales"])
async def add_sale(
    saleData: dict,
    db: AsyncSession = Depends(get_db),
):
    """Add a new sale record."""
    try:
        store_id = saleData.get("store_id", "store001")
        sale_id = uuid.uuid4()
        sale_date = datetime.utcnow()
        if saleData.get("date"):
            try:
                sale_date = datetime.fromisoformat(str(saleData["date"]))
            except Exception:
                pass

        sale = CustomerSale(
            id=sale_id,
            store_id=store_id,
            customer=saleData.get("customer"),
            total=float(saleData.get("total", 0)),
            payment_method=saleData.get("paymentMethod") or saleData.get("payment_method"),
            sale_date=sale_date,
            created_at=datetime.utcnow(),
        )
        db.add(sale)

        for item in saleData.get("items", []):
            si = SaleItem(
                id=uuid.uuid4(),
                sale_id=sale_id,
                product_id=str(item.get("productId") or item.get("product_id") or ""),
                product_name=str(item.get("productName") or item.get("product_name") or ""),
                quantity=float(item.get("quantity", 0)),
                price=float(item.get("price", 0)),
            )
            db.add(si)

        await db.commit()
        return {"status": "success", "sale_id": str(sale_id)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/agent/sales/{sale_id}", tags=["Sales"])
async def delete_sale(
    sale_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a sale record and its items."""
    try:
        await db.execute(delete(SaleItem).where(SaleItem.sale_id == uuid.UUID(sale_id)))
        await db.execute(delete(CustomerSale).where(CustomerSale.id == uuid.UUID(sale_id)))
        await db.commit()
        return {"status": "deleted"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/agent/sales/{sale_id}", tags=["Sales"])
async def update_sale(
    sale_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    """Update an existing sale record."""
    try:
        result = await db.execute(
            select(CustomerSale).where(CustomerSale.id == uuid.UUID(sale_id))
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail=f"Sale {sale_id} not found")

        await db.execute(
            update(CustomerSale)
            .where(CustomerSale.id == uuid.UUID(sale_id))
            .values(**{k: v for k, v in data.items() if k not in ("id", "store_id")})
        )
        await db.commit()
        return {"status": "updated", "sale_id": sale_id}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Health Check
# =============================================================================

@app.get("/", tags=["Health"])
def root():
    return {
        "status": "KiranaIQ AI Backend is running",
        "version": "2.0.0",
        "database": "PostgreSQL (Supabase)",
        "agents": ["master", "inventory", "supplier", "forecast", "pricing", "cashflow"],
        "docs": "/docs",
    }