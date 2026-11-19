"""ERP 只读接口。"""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from common.auth import verify_service_token
from common.schemas import MATERIAL_CODE, SUPPLIER_CODE, Page, PageParams, split_codes
from erp_service.database import get_db
from erp_service.models.schemas import (
    InventoryOut, LowStockOut, MaterialDetail, MaterialOut, PurchaseOrderOut, SupplierOut, TransactionOut,
)
from erp_service.services import queries as q

router = APIRouter(prefix="/api", dependencies=[Depends(verify_service_token)])

PoStatus = Literal["已下单", "部分到货", "已完成", "已延期", "未完成"]


def page(items, total, p: PageParams) -> dict:
    return {"items": items, "total": total, "page": p.page, "page_size": p.page_size}


@router.get("/materials", response_model=Page[MaterialOut], summary="物料列表")
def materials(
    category: str | None = Query(None, max_length=50),
    keyword: str | None = Query(None, max_length=50),
    p: PageParams = Depends(), db: Session = Depends(get_db),
):
    return page(*q.list_materials(db, p, category, keyword), p)


@router.get("/materials/categories", response_model=list[str], summary="物料分类")
def material_categories(db: Session = Depends(get_db)):
    return q.categories(db)


@router.get("/materials/{code}", response_model=MaterialDetail, summary="物料详情")
def material_detail(code: str = Path(pattern=MATERIAL_CODE), db: Session = Depends(get_db)):
    detail = q.material_detail(db, code)
    if not detail:
        raise HTTPException(404, f"物料 {code} 不存在")
    return detail


@router.get("/inventory", response_model=Page[InventoryOut], summary="库存查询（支持批量编码）")
def inventory(
    codes: str | None = Query(None, description="物料编码，逗号分隔，最多 100 个"),
    category: str | None = Query(None, max_length=50),
    p: PageParams = Depends(), db: Session = Depends(get_db),
):
    return page(*q.list_inventory(db, p, split_codes(codes, MATERIAL_CODE), category), p)


@router.get("/inventory/low-stock", response_model=Page[LowStockOut], summary="低于安全库存的物料")
def low_stock(p: PageParams = Depends(), db: Session = Depends(get_db)):
    return page(*q.list_low_stock(db, p), p)


@router.get("/inventory/transactions", response_model=Page[TransactionOut], summary="库存变动记录")
def transactions(
    material_code: str | None = Query(None, pattern=MATERIAL_CODE),
    start_date: date | None = None,
    end_date: date | None = None,
    p: PageParams = Depends(), db: Session = Depends(get_db),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, "start_date 不能晚于 end_date")
    return page(*q.list_transactions(db, p, material_code, start_date, end_date), p)


@router.get("/suppliers", response_model=Page[SupplierOut], summary="供应商")
def suppliers(
    codes: str | None = Query(None, description="供应商编码，逗号分隔"),
    keyword: str | None = Query(None, max_length=50),
    p: PageParams = Depends(), db: Session = Depends(get_db),
):
    return page(*q.list_suppliers(db, p, split_codes(codes, SUPPLIER_CODE), keyword), p)


@router.get("/purchase-orders", response_model=Page[PurchaseOrderOut], summary="采购订单")
def purchase_orders(
    material_codes: str | None = Query(None, description="物料编码，逗号分隔"),
    supplier_code: str | None = Query(None, pattern=SUPPLIER_CODE),
    status: PoStatus | None = Query(None, description="未完成 = 已下单 + 部分到货 + 已延期"),
    p: PageParams = Depends(), db: Session = Depends(get_db),
):
    codes = split_codes(material_codes, MATERIAL_CODE)
    return page(*q.list_purchase_orders(db, p, codes, supplier_code, status), p)
