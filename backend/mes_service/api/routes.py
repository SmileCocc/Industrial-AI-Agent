"""MES 只读接口。"""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from common.auth import verify_service_token
from common.schemas import EQUIPMENT_CODE, LINE_CODE, WO_NO, Page, PageParams, split_codes
from mes_service.database import get_db
from mes_service.models.schemas import (
    AlarmOut, LineOut, PlanOut, WorkOrderDetail, WorkOrderMaterialOut, WorkOrderMaterials, WorkOrderOut,
)
from mes_service.services import queries as q

router = APIRouter(prefix="/api", dependencies=[Depends(verify_service_token)])

WoStatus = Literal["待执行", "生产中", "已完成", "已延期", "暂停", "未完成"]
AlarmLevel = Literal["提示", "一般", "严重"]


def page(items, total, p: PageParams) -> dict:
    return {"items": items, "total": total, "page": p.page, "page_size": p.page_size}


def check_range(start: date | None, end: date | None) -> None:
    if start and end and start > end:
        raise HTTPException(422, "start_date 不能晚于 end_date")


@router.get("/work-orders", response_model=Page[WorkOrderOut], summary="生产工单")
def work_orders(
    status: WoStatus | None = Query(None, description="未完成 = 待执行 + 生产中 + 已延期 + 暂停"),
    line_code: str | None = Query(None, pattern=LINE_CODE),
    start_date: date | None = Query(None, description="与计划时间窗口有交集"),
    end_date: date | None = None,
    wo_nos: str | None = Query(None, description="工单号，逗号分隔"),
    p: PageParams = Depends(), db: Session = Depends(get_db),
):
    check_range(start_date, end_date)
    return page(*q.list_work_orders(db, p, status, line_code, start_date, end_date, split_codes(wo_nos, WO_NO)), p)


# 批量路由必须声明在 /{code} 之前
@router.get("/work-orders/materials", response_model=list[WorkOrderMaterials], summary="批量查询工单物料需求")
def batch_materials(wo_nos: str = Query(..., description="工单号，逗号分隔，最多 50 个"), db: Session = Depends(get_db)):
    return q.work_order_materials(db, split_codes(wo_nos, WO_NO, max_count=50))


@router.get("/work-orders/{code}", response_model=WorkOrderDetail, summary="工单详情")
def work_order(code: str = Path(pattern=WO_NO), db: Session = Depends(get_db)):
    detail = q.work_order_detail(db, code)
    if not detail:
        raise HTTPException(404, f"工单 {code} 不存在")
    return detail


@router.get("/work-orders/{code}/materials", response_model=list[WorkOrderMaterialOut], summary="工单物料需求")
def work_order_materials(code: str = Path(pattern=WO_NO), db: Session = Depends(get_db)):
    rows = q.work_order_materials(db, [code])
    if not rows:
        raise HTTPException(404, f"工单 {code} 不存在")
    return rows[0]["materials"]


@router.get("/production-plans", response_model=Page[PlanOut], summary="生产计划（含实际产量）")
def production_plans(
    plan_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    line_code: str | None = Query(None, pattern=LINE_CODE),
    wo_no: str | None = Query(None, pattern=WO_NO),
    p: PageParams = Depends(), db: Session = Depends(get_db),
):
    check_range(start_date, end_date)
    return page(*q.list_plans(db, p, plan_date, start_date, end_date, line_code, wo_no), p)


@router.get("/production-lines", response_model=list[LineOut], summary="生产线状态")
def production_lines(line_code: str | None = Query(None, pattern=LINE_CODE), db: Session = Depends(get_db)):
    return q.list_lines(db, line_code)


@router.get("/equipment/alarms", response_model=Page[AlarmOut], summary="设备报警记录")
def equipment_alarms(
    start_date: date | None = None,
    end_date: date | None = None,
    line_code: str | None = Query(None, pattern=LINE_CODE),
    level: AlarmLevel | None = None,
    wo_no: str | None = Query(None, pattern=WO_NO),
    equipment_code: str | None = Query(None, pattern=EQUIPMENT_CODE),
    active_only: bool = Query(False, description="只看未恢复报警"),
    p: PageParams = Depends(), db: Session = Depends(get_db),
):
    check_range(start_date, end_date)
    return page(*q.list_alarms(db, p, start_date, end_date, line_code, level, wo_no, equipment_code, active_only), p)
