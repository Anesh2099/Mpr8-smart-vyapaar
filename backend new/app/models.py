"""
models.py — SQLAlchemy 2.0 ORM models for KiranaIQ (Supabase/PostgreSQL).
"""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# ---------------------------------------------------------------------------
# 1. inventory
# ---------------------------------------------------------------------------
class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String, nullable=False)
    product_name: Mapped[str] = mapped_column(String, nullable=False)
    sku: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    stock: Mapped[float] = mapped_column(Float, default=0)
    reorder_level: Mapped[float] = mapped_column(Float, default=10)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wholesale_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    supplier: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


# ---------------------------------------------------------------------------
# 2. customer_sales
# ---------------------------------------------------------------------------
class CustomerSale(Base):
    __tablename__ = "customer_sales"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    customer: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    total: Mapped[float] = mapped_column(Float, nullable=False)
    payment_method: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sale_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship
    items: Mapped[List["SaleItem"]] = relationship(
        "SaleItem", back_populates="sale", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# 3. sale_items
# ---------------------------------------------------------------------------
class SaleItem(Base):
    __tablename__ = "sale_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_sales.id"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[str] = mapped_column(String, nullable=False)
    product_name: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationship
    sale: Mapped["CustomerSale"] = relationship("CustomerSale", back_populates="items")


# ---------------------------------------------------------------------------
# 4. purchase_orders
# ---------------------------------------------------------------------------
class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    supplier: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending")
    total_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    order_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship
    items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# 5. order_items
# ---------------------------------------------------------------------------
class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_orders.id"),
        nullable=False,
    )
    product_name: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationship
    order: Mapped["PurchaseOrder"] = relationship(
        "PurchaseOrder", back_populates="items"
    )


# ---------------------------------------------------------------------------
# 6. suppliers
# ---------------------------------------------------------------------------
class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    supplier_name: Mapped[str] = mapped_column(String, nullable=False)
    products: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String), nullable=True
    )
    price_per_unit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reliability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    contact: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    lead_time_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# 7. demand_forecast
# ---------------------------------------------------------------------------
class DemandForecast(Base):
    __tablename__ = "demand_forecast"
    __table_args__ = (UniqueConstraint("store_id", "product_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[str] = mapped_column(String, nullable=False)
    product_id: Mapped[str] = mapped_column(String, nullable=False)
    product_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    predicted_demand: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# 8. proactive_alerts
# ---------------------------------------------------------------------------
class ProactiveAlert(Base):
    __tablename__ = "proactive_alerts"
    __table_args__ = (
        UniqueConstraint("store_id", "product_id", "alert_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    alert_type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    product_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    product_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


# ---------------------------------------------------------------------------
# 9. competitor_prices
# ---------------------------------------------------------------------------
class CompetitorPrice(Base):
    __tablename__ = "competitor_prices"
    __table_args__ = (UniqueConstraint("store_id", "product_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[str] = mapped_column(String, nullable=False)
    product_id: Mapped[str] = mapped_column(String, nullable=False)
    product_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    competitor_price: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


__all__ = [
    "Inventory",
    "CustomerSale",
    "SaleItem",
    "PurchaseOrder",
    "OrderItem",
    "Supplier",
    "DemandForecast",
    "ProactiveAlert",
    "CompetitorPrice",
]
