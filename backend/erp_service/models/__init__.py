"""ERP 数据表（库 industrial_erp）。"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

Qty = Numeric(14, 3)


class ErpBase(DeclarativeBase):
    """ERP 独立的元数据，建表时只会创建 ERP 的表。"""


class Supplier(ErpBase):
    __tablename__ = "suppliers"
    supplier_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(50), comment="主营品类")
    contact: Mapped[str] = mapped_column(String(50))
    phone: Mapped[str] = mapped_column(String(30))
    address: Mapped[str] = mapped_column(String(200))
    lead_time_days: Mapped[int] = mapped_column(comment="平均交货周期（天）")
    rating: Mapped[str] = mapped_column(String(2), comment="供应商评级 A/B/C")


class Material(ErpBase):
    __tablename__ = "materials"
    material_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    spec: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(50), index=True)
    unit: Mapped[str] = mapped_column(String(10))
    safety_stock: Mapped[Decimal] = mapped_column(Qty)
    current_stock: Mapped[Decimal] = mapped_column(Qty, comment="账面库存")
    reserved_stock: Mapped[Decimal] = mapped_column(Qty, comment="已占用库存")
    available_stock: Mapped[Decimal] = mapped_column(Qty, comment="可用库存 = 账面 - 占用")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    warehouse: Mapped[str] = mapped_column(String(30))
    supplier_code: Mapped[str] = mapped_column(ForeignKey("suppliers.supplier_code"), comment="主供应商")
    supplier: Mapped[Supplier] = relationship(lazy="joined")


class InventoryTransaction(ErpBase):
    __tablename__ = "inventory_transactions"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    material_code: Mapped[str] = mapped_column(ForeignKey("materials.material_code"))
    txn_type: Mapped[str] = mapped_column(String(10), comment="入库/出库/盘点")
    quantity: Mapped[Decimal] = mapped_column(Qty, comment="正数入、负数出")
    balance_after: Mapped[Decimal] = mapped_column(Qty)
    ref_no: Mapped[str | None] = mapped_column(String(30), comment="采购单号 / MES 工单号")
    txn_time: Mapped[datetime] = mapped_column(DateTime)
    operator: Mapped[str] = mapped_column(String(30))
    remark: Mapped[str | None] = mapped_column(String(200))
    __table_args__ = (Index("ix_txn_material_time", "material_code", "txn_time"),)


class PurchaseOrder(ErpBase):
    __tablename__ = "purchase_orders"
    po_no: Mapped[str] = mapped_column(String(20), primary_key=True)
    supplier_code: Mapped[str] = mapped_column(ForeignKey("suppliers.supplier_code"), index=True)
    material_code: Mapped[str] = mapped_column(ForeignKey("materials.material_code"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Qty)
    received_qty: Mapped[Decimal] = mapped_column(Qty)
    status: Mapped[str] = mapped_column(String(10), comment="已下单/部分到货/已完成/已延期")
    order_date: Mapped[date] = mapped_column(Date)
    expected_date: Mapped[date] = mapped_column(Date)
    supplier: Mapped[Supplier] = relationship(lazy="joined")
    material: Mapped[Material] = relationship(lazy="joined")
