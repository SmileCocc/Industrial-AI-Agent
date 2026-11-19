"""ERP 接口响应模型。数量字段统一输出为数字。"""
from datetime import date, datetime

from common.schemas import ORMModel


class SupplierOut(ORMModel):
    supplier_code: str
    name: str
    category: str
    contact: str
    phone: str
    address: str
    lead_time_days: int
    rating: str


class MaterialOut(ORMModel):
    material_code: str
    name: str
    spec: str
    category: str
    unit: str
    safety_stock: float
    current_stock: float
    reserved_stock: float
    available_stock: float
    unit_price: float
    warehouse: str
    supplier_code: str
    supplier_name: str


class InventoryOut(ORMModel):
    material_code: str
    name: str
    category: str
    unit: str
    current_stock: float
    reserved_stock: float
    available_stock: float
    safety_stock: float
    below_safety: bool
    gap_to_safety: float  # 低于安全库存的差额，未低于为 0
    warehouse: str


class LowStockOut(InventoryOut):
    supplier_code: str
    supplier_name: str
    lead_time_days: int


class TransactionOut(ORMModel):
    id: int
    material_code: str
    txn_type: str
    quantity: float
    balance_after: float
    ref_no: str | None
    txn_time: datetime
    operator: str
    remark: str | None


class PurchaseOrderOut(ORMModel):
    po_no: str
    supplier_code: str
    supplier_name: str
    material_code: str
    material_name: str
    quantity: float
    received_qty: float
    pending_qty: float
    status: str
    order_date: date
    expected_date: date
    is_overdue: bool


class MaterialDetail(MaterialOut):
    supplier: SupplierOut
    recent_transactions: list[TransactionOut]
    open_purchase_orders: list[PurchaseOrderOut]
