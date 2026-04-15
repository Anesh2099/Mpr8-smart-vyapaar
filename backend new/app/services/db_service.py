"""
db_service.py — Shared async database service layer for KiranaIQ.
All agents use these functions instead of querying Firestore or the DB directly.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, update, and_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import (
    CompetitorPrice,
    CustomerSale,
    DemandForecast,
    Inventory,
    ProactiveAlert,
    SaleItem,
    Supplier,
)
from app.core.cache import RedisCache
import json

class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)



# =============================================================================
# Inventory
# =============================================================================

async def get_all_inventory(db: AsyncSession, store_id: str) -> list:
    """Return all inventory rows for a store."""
    cache_key = f"inventory:{store_id}"
    cached = await RedisCache.get(cache_key)
    if cached:
        data = json.loads(cached)
        for d in data:
            if d.get("created_at"): d["created_at"] = datetime.fromisoformat(d["created_at"])
            if d.get("updated_at"): d["updated_at"] = datetime.fromisoformat(d["updated_at"])
            if d.get("expiry_date") and d["expiry_date"]: d["expiry_date"] = datetime.fromisoformat(d["expiry_date"])
        return [Inventory(**d) for d in data]

    result = await db.execute(
        select(Inventory).where(Inventory.store_id == store_id)
    )
    rows = list(result.scalars().all())
    data = [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]
    await RedisCache.set(cache_key, json.dumps(data, cls=CustomEncoder), ex=300)  # cache for 5 minutes
    return rows


async def get_low_stock_items(db: AsyncSession, store_id: str) -> list:
    """Return only items where stock < reorder_level (uses partial index)."""
    cache_key = f"low_stock:{store_id}"
    cached = await RedisCache.get(cache_key)
    if cached:
        data = json.loads(cached)
        for d in data:
            if d.get("created_at"): d["created_at"] = datetime.fromisoformat(d["created_at"])
            if d.get("updated_at"): d["updated_at"] = datetime.fromisoformat(d["updated_at"])
            if d.get("expiry_date") and d["expiry_date"]: d["expiry_date"] = datetime.fromisoformat(d["expiry_date"])
        return [Inventory(**d) for d in data]

    result = await db.execute(
        select(Inventory).where(
            and_(
                Inventory.store_id == store_id,
                Inventory.stock < Inventory.reorder_level,
            )
        )
    )
    rows = list(result.scalars().all())
    data = [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]
    await RedisCache.set(cache_key, json.dumps(data, cls=CustomEncoder), ex=300)
    return rows


async def get_expiring_items(db: AsyncSession, store_id: str, days: int = 5) -> list:
    """Return items where expiry_date <= now + days."""
    cache_key = f"expiring:{store_id}:{days}"
    cached = await RedisCache.get(cache_key)
    if cached:
        data = json.loads(cached)
        for d in data:
            if d.get("created_at"): d["created_at"] = datetime.fromisoformat(d["created_at"])
            if d.get("updated_at"): d["updated_at"] = datetime.fromisoformat(d["updated_at"])
            if d.get("expiry_date") and d["expiry_date"]: d["expiry_date"] = datetime.fromisoformat(d["expiry_date"])
        return [Inventory(**d) for d in data]

    cutoff = datetime.utcnow() + timedelta(days=days)
    result = await db.execute(
        select(Inventory).where(
            and_(
                Inventory.store_id == store_id,
                Inventory.expiry_date.isnot(None),
                Inventory.expiry_date <= cutoff,
            )
        )
    )
    rows = list(result.scalars().all())
    data = [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]
    await RedisCache.set(cache_key, json.dumps(data, cls=CustomEncoder), ex=300)
    return rows


async def get_inventory_item(
    db: AsyncSession, store_id: str, product_id: str
) -> Optional[Inventory]:
    """Return a single inventory item by product_id."""
    result = await db.execute(
        select(Inventory).where(
            and_(
                Inventory.store_id == store_id,
                Inventory.product_id == product_id,
            )
        )
    )
    return result.scalar_one_or_none()


async def upsert_inventory_item(db: AsyncSession, store_id: str, data: dict) -> None:
    """Insert or update an inventory item.

    data must contain 'product_id'. All other keys map directly to columns.
    Uses INSERT ... ON CONFLICT (store_id, product_id) DO UPDATE.
    """
    product_id = data.get("product_id")
    if not product_id:
        raise ValueError("upsert_inventory_item: data must include 'product_id'")

    now = datetime.utcnow()
    values = {
        "id": uuid.uuid4(),
        "store_id": store_id,
        "product_id": product_id,
        "product_name": data.get("product_name", ""),
        "sku": data.get("sku"),
        "stock": float(data.get("stock", 0)),
        "reorder_level": float(data.get("reorder_level", 10)),
        "price": float(data["price"]) if data.get("price") is not None else None,
        "wholesale_cost": float(data["wholesale_cost"]) if data.get("wholesale_cost") is not None else None,
        "supplier": data.get("supplier"),
        "expiry_date": data.get("expiry_date"),
        "category": data.get("category"),
        "created_at": now,
        "updated_at": now,
    }

    stmt = (
        pg_insert(Inventory)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["store_id", "product_id"],
            set_={
                "stock": values["stock"],
                "reorder_level": values["reorder_level"],
                "price": values["price"],
                "wholesale_cost": values["wholesale_cost"],
                "supplier": values["supplier"],
                "expiry_date": values["expiry_date"],
                "category": values["category"],
                "updated_at": now,
            },
        )
    )
    await db.execute(stmt)
    await RedisCache.delete(f"inventory:{store_id}")
    await RedisCache.delete(f"low_stock:{store_id}")
    await RedisCache.delete(f"expiring:{store_id}:5")
    await db.commit()


# =============================================================================
# Sales
# =============================================================================

async def get_sales_last_n_days(db: AsyncSession, store_id: str, n: int = 7) -> list:
    """Return sales from the last n days with their sale_items (joined load)."""
    since = datetime.utcnow() - timedelta(days=n)
    result = await db.execute(
        select(CustomerSale)
        .options(joinedload(CustomerSale.items))
        .where(
            and_(
                CustomerSale.store_id == store_id,
                CustomerSale.sale_date >= since,
            )
        )
        .order_by(CustomerSale.sale_date.desc())
    )
    return result.unique().scalars().all()


async def get_all_sales(db: AsyncSession, store_id: str) -> list:
    """Return all sales with their items."""
    result = await db.execute(
        select(CustomerSale)
        .options(joinedload(CustomerSale.items))
        .where(CustomerSale.store_id == store_id)
        .order_by(CustomerSale.sale_date.desc())
    )
    return result.unique().scalars().all()


# =============================================================================
# Suppliers
# =============================================================================

async def get_all_suppliers(db: AsyncSession, store_id: str) -> list:
    """Return all suppliers for a store."""
    result = await db.execute(
        select(Supplier).where(Supplier.store_id == store_id)
    )
    return result.scalars().all()


async def search_suppliers_by_product(
    db: AsyncSession, store_id: str, product_name: str
) -> list:
    """Return suppliers whose products array contains product_name (GIN index)."""
    result = await db.execute(
        select(Supplier).where(
            and_(
                Supplier.store_id == store_id,
                Supplier.products.any(product_name),  # type: ignore[arg-type]
            )
        )
    )
    return result.scalars().all()


# =============================================================================
# Demand Forecast
# =============================================================================

async def get_forecast(db: AsyncSession, store_id: str) -> list:
    """Return all demand forecast rows for a store."""
    cache_key = f"forecast:{store_id}"
    cached = await RedisCache.get(cache_key)
    if cached:
        data = json.loads(cached)
        for d in data:
            if d.get("updated_at"): d["updated_at"] = datetime.fromisoformat(d["updated_at"])
        return [DemandForecast(**d) for d in data]

    result = await db.execute(
        select(DemandForecast).where(DemandForecast.store_id == store_id)
    )
    rows = list(result.scalars().all())
    data = [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]
    await RedisCache.set(cache_key, json.dumps(data, cls=CustomEncoder), ex=7200)
    return rows


async def upsert_forecast(
    db: AsyncSession,
    store_id: str,
    product_id: str,
    product_name: str,
    predicted_demand: float,
) -> None:
    """Insert or update a demand forecast row.

    Conflict target: (store_id, product_id) — matches the UniqueConstraint.
    """
    now = datetime.utcnow()
    stmt = (
        pg_insert(DemandForecast)
        .values(
            id=uuid.uuid4(),
            store_id=store_id,
            product_id=product_id,
            product_name=product_name,
            predicted_demand=predicted_demand,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["store_id", "product_id"],
            set_={
                "product_name": product_name,
                "predicted_demand": predicted_demand,
                "updated_at": now,
            },
        )
    )
    await db.execute(stmt)
    await db.commit()
    await RedisCache.delete(f"forecast:{store_id}")


# =============================================================================
# Alerts
# =============================================================================

async def get_active_alerts(db: AsyncSession, store_id: str) -> list:
    """Return all non-dismissed alerts ordered by created_at DESC."""
    cache_key = f"alerts:{store_id}"
    cached = await RedisCache.get(cache_key)
    if cached:
        data = json.loads(cached)
        for d in data:
            if d.get("created_at"): d["created_at"] = datetime.fromisoformat(d["created_at"])
            if d.get("updated_at"): d["updated_at"] = datetime.fromisoformat(d["updated_at"])
        return [ProactiveAlert(**d) for d in data]

    result = await db.execute(
        select(ProactiveAlert)
        .where(
            and_(
                ProactiveAlert.store_id == store_id,
                ProactiveAlert.dismissed.is_(False),
            )
        )
        .order_by(ProactiveAlert.created_at.desc())
    )
    rows = list(result.scalars().all())
    data = [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]
    await RedisCache.set(cache_key, json.dumps(data, cls=CustomEncoder), ex=300)
    return rows


async def upsert_alert(
    db: AsyncSession,
    store_id: str,
    alert_type: str,
    product_id: Optional[str],
    product_name: Optional[str],
    message: str,
    severity: Optional[str] = None,
    suggested_action: Optional[str] = None,
) -> None:
    """Insert or update an alert, deduplicating on (store_id, product_id, alert_type).

    Never creates duplicate alerts — conflict target matches the UniqueConstraint.
    """
    now = datetime.utcnow()
    stmt = (
        pg_insert(ProactiveAlert)
        .values(
            id=uuid.uuid4(),
            store_id=store_id,
            alert_type=alert_type,
            severity=severity,
            product_id=product_id,
            product_name=product_name,
            message=message,
            suggested_action=suggested_action,
            dismissed=False,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["store_id", "product_id", "alert_type"],
            set_={
                "message": message,
                "severity": severity,
                "suggested_action": suggested_action,
                "product_name": product_name,
                "dismissed": False,   # re-activate if previously dismissed
                "updated_at": now,
            },
        )
    )
    await db.execute(stmt)
    await db.commit()
    await RedisCache.delete(f"alerts:{store_id}")


async def dismiss_alert(db: AsyncSession, alert_id: str) -> None:
    """Set dismissed = True for the given alert id."""
    result = await db.execute(
        update(ProactiveAlert)
        .where(ProactiveAlert.id == uuid.UUID(alert_id))
        .values(dismissed=True, updated_at=datetime.utcnow())
        .returning(ProactiveAlert.store_id)
    )
    store_id = result.scalar()
    await db.commit()
    if store_id:
        await RedisCache.delete(f"alerts:{store_id}")


# =============================================================================
# Pricing (single joined query)
# =============================================================================

async def get_pricing_data(
    db: AsyncSession, store_id: str, product_id: str
) -> dict:
    """Return inventory + forecast + competitor_price for one product in one query.

    Uses a single LEFT OUTER JOIN across three tables to avoid N+1 calls.
    """
    stmt = (
        select(
            Inventory.product_name,
            Inventory.price,
            Inventory.wholesale_cost,
            Inventory.stock,
            Inventory.reorder_level,
            Inventory.category,
            DemandForecast.predicted_demand,
            CompetitorPrice.competitor_price,
        )
        .select_from(Inventory)
        .outerjoin(
            DemandForecast,
            and_(
                DemandForecast.store_id == Inventory.store_id,
                DemandForecast.product_id == Inventory.product_id,
            ),
        )
        .outerjoin(
            CompetitorPrice,
            and_(
                CompetitorPrice.store_id == Inventory.store_id,
                CompetitorPrice.product_id == Inventory.product_id,
            ),
        )
        .where(
            and_(
                Inventory.store_id == store_id,
                Inventory.product_id == product_id,
            )
        )
    )

    result = await db.execute(stmt)
    row = result.fetchone()

    if row is None:
        return {}

    return {
        "product_name": row.product_name,
        "price": row.price,
        "wholesale_cost": row.wholesale_cost,
        "stock": row.stock,
        "reorder_level": row.reorder_level,
        "category": row.category,
        "predicted_demand": row.predicted_demand,
        "competitor_price": row.competitor_price,
    }
