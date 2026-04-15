"""
app/schemas/models.py — Shared Pydantic request/response models.
"""

from pydantic import BaseModel, Field
from typing import Any, Optional


# ── Requests ──────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str = Field(..., description="Natural language user query")
    session_id: str = Field(default="default", description="Conversation session ID")
    store_id: str = Field(default="store001", description="Store/vendor identifier")


class InventoryRunRequest(BaseModel):
    query: str = Field(..., description="Natural language inventory query")
    store_id: str = Field(default="store001")


class InventoryItem(BaseModel):
    productName: str
    sku: str
    stock: int
    reorderLevel: int
    supplier: str
    price: float
    category: Optional[str] = "General"
    store_id: str = "store001"


class SupplierRunRequest(BaseModel):
    query: str = Field(..., description="Natural language supplier command")
    product_id: Optional[str] = None
    store_id: str = Field(default="store001")


class PricingRunRequest(BaseModel):
    product_id: str
    store_id: str = Field(default="store001")


class ForecastRunRequest(BaseModel):
    product_id: Optional[str] = None  # None = run for all products


# ── Response Building Blocks ──────────────────────────────────────────────────

class ActionCard(BaseModel):
    type: str  # e.g. "draft_order", "draft_negotiation", "reorder_alert"
    title: str
    data: dict[str, Any]


class AgentResponse(BaseModel):
    message: str
    agent: str
    agent_trace: list[str] = []
    action_cards: list[ActionCard] = []
    alerts: list[dict] = []
    session_id: str = "default"
    raw_data: Optional[dict] = None


# ── Alert ─────────────────────────────────────────────────────────────────────

class Alert(BaseModel):
    alert_id: Optional[str] = None
    type: str           # "low_stock" | "expiry" | "high_demand" | "supplier_price"
    severity: str       # "info" | "warning" | "critical"
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    message: str
    suggested_action: Optional[str] = None
    store_id: str = "store001"
