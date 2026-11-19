"""ERP 查询逻辑。全部为只读 ORM 查询，参数自动绑定，不拼接 SQL。"""
from datetime import date, datetime, time

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from common.schemas import PageParams
from erp_service.models import InventoryTransaction, Material, PurchaseOrder, Supplier

OPEN_PO_STATUS = ("已下单", "部分到货", "已延期")


def _page(db: Session, stmt, params: PageParams) -> tuple[list, int]:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = db.scalars(stmt.offset(params.offset).limit(params.page_size)).unique().all()
    return list(rows), total or 0


def material_dict(m: Material) -> dict:
    return {c.name: getattr(m, c.name) for c in Material.__table__.columns} | {"supplier_name": m.supplier.name}


def inventory_dict(m: Material) -> dict:
    gap = max(float(m.safety_stock) - float(m.available_stock), 0)
    return {
        "material_code": m.material_code, "name": m.name, "category": m.category, "unit": m.unit,
        "current_stock": m.current_stock, "reserved_stock": m.reserved_stock,
        "available_stock": m.available_stock, "safety_stock": m.safety_stock,
        "below_safety": m.available_stock < m.safety_stock, "gap_to_safety": round(gap, 3),
        "warehouse": m.warehouse,
        "supplier_code": m.supplier_code, "supplier_name": m.supplier.name,
        "lead_time_days": m.supplier.lead_time_days,
    }


def po_dict(po: PurchaseOrder) -> dict:
    pending = float(po.quantity) - float(po.received_qty)
    return {
        "po_no": po.po_no, "supplier_code": po.supplier_code, "supplier_name": po.supplier.name,
        "material_code": po.material_code, "material_name": po.material.name,
        "quantity": po.quantity, "received_qty": po.received_qty, "pending_qty": round(pending, 3),
        "status": po.status, "order_date": po.order_date, "expected_date": po.expected_date,
        # 逾期：未完成且预计到货日早于今天
        "is_overdue": po.status != "已完成" and po.expected_date < date.today(),
    }


def list_materials(db: Session, params: PageParams, category: str | None, keyword: str | None):
    stmt = select(Material).order_by(Material.material_code)
    if category:
        stmt = stmt.where(Material.category == category)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(Material.name.like(like), Material.material_code.like(like), Material.spec.like(like)))
    rows, total = _page(db, stmt, params)
    return [material_dict(m) for m in rows], total


def material_detail(db: Session, code: str) -> dict | None:
    m = db.get(Material, code)
    if not m:
        return None
    txns = db.scalars(
        select(InventoryTransaction).where(InventoryTransaction.material_code == code)
        .order_by(InventoryTransaction.txn_time.desc()).limit(10)
    ).all()
    pos = db.scalars(
        select(PurchaseOrder).where(PurchaseOrder.material_code == code, PurchaseOrder.status.in_(OPEN_PO_STATUS))
        .order_by(PurchaseOrder.expected_date)
    ).unique().all()
    return material_dict(m) | {
        "supplier": m.supplier,
        "recent_transactions": list(txns),
        "open_purchase_orders": [po_dict(p) for p in pos],
    }


def list_inventory(db: Session, params: PageParams, codes: list[str], category: str | None):
    stmt = select(Material).order_by(Material.material_code)
    if codes:
        stmt = stmt.where(Material.material_code.in_(codes))
    if category:
        stmt = stmt.where(Material.category == category)
    rows, total = _page(db, stmt, params)
    return [inventory_dict(m) for m in rows], total


def list_low_stock(db: Session, params: PageParams):
    # 低库存判定：可用库存 < 安全库存；按 可用/安全 比例从低到高排序（越靠前越紧缺）
    stmt = (
        select(Material).where(Material.available_stock < Material.safety_stock)
        .order_by((Material.available_stock / Material.safety_stock).asc())
    )
    rows, total = _page(db, stmt, params)
    return [inventory_dict(m) for m in rows], total


def list_transactions(db: Session, params: PageParams, material_code: str | None, start: date | None, end: date | None):
    stmt = select(InventoryTransaction).order_by(InventoryTransaction.txn_time.desc())
    if material_code:
        stmt = stmt.where(InventoryTransaction.material_code == material_code)
    if start:
        stmt = stmt.where(InventoryTransaction.txn_time >= datetime.combine(start, time.min))
    if end:
        stmt = stmt.where(InventoryTransaction.txn_time <= datetime.combine(end, time.max))
    return _page(db, stmt, params)


def list_suppliers(db: Session, params: PageParams, codes: list[str], keyword: str | None):
    stmt = select(Supplier).order_by(Supplier.supplier_code)
    if codes:
        stmt = stmt.where(Supplier.supplier_code.in_(codes))
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(Supplier.name.like(like), Supplier.category.like(like)))
    return _page(db, stmt, params)


def list_purchase_orders(db: Session, params: PageParams, material_codes: list[str],
                         supplier_code: str | None, status: str | None):
    stmt = select(PurchaseOrder).order_by(PurchaseOrder.expected_date.desc())
    if material_codes:
        stmt = stmt.where(PurchaseOrder.material_code.in_(material_codes))
    if supplier_code:
        stmt = stmt.where(PurchaseOrder.supplier_code == supplier_code)
    if status == "未完成":
        stmt = stmt.where(PurchaseOrder.status.in_(OPEN_PO_STATUS))
    elif status:
        stmt = stmt.where(PurchaseOrder.status == status)
    rows, total = _page(db, stmt, params)
    return [po_dict(p) for p in rows], total


def categories(db: Session) -> list[str]:
    return list(db.scalars(select(Material.category).distinct().order_by(Material.category)))
