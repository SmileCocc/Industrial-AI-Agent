"""MES 查询逻辑。全部为只读 ORM 查询。"""
from datetime import date, datetime, time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from common.schemas import PageParams
from mes_service.models import EquipmentAlarm, ProductionLine, ProductionPlan, WorkOrder

OPEN_WO_STATUS = ("待执行", "生产中", "已延期", "暂停")


def _rate(actual: float, planned: float) -> float:
    return round(actual / planned * 100, 1) if planned else 0.0


def _page(db: Session, stmt, params: PageParams) -> tuple[list, int]:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = db.scalars(stmt.offset(params.offset).limit(params.page_size)).unique().all()
    return list(rows), total or 0


def wo_dict(wo: WorkOrder) -> dict:
    return {c.name: getattr(wo, c.name) for c in WorkOrder.__table__.columns} | {
        "line_name": wo.line.name,
        "completion_rate": _rate(wo.completed_qty, wo.planned_qty),
        "is_overdue": wo.status != "已完成" and wo.planned_end < datetime.now(),
    }


def wom_list(wo: WorkOrder) -> list[dict]:
    return [{
        "wo_no": m.wo_no, "material_code": m.material_code, "material_name": m.material_name, "unit": m.unit,
        "required_qty": m.required_qty, "issued_qty": m.issued_qty,
        "pending_qty": round(float(m.required_qty) - float(m.issued_qty), 3),
    } for m in wo.materials]


def plan_dict(p: ProductionPlan) -> dict:
    return {c.name: getattr(p, c.name) for c in ProductionPlan.__table__.columns} | {
        "line_name": p.line.name, "completion_rate": _rate(p.actual_qty, p.planned_qty),
    }


def alarm_dict(a: EquipmentAlarm) -> dict:
    return {c.name: getattr(a, c.name) for c in EquipmentAlarm.__table__.columns} | {
        "equipment_name": a.equipment.name, "is_active": a.end_time is None,
    }


def list_work_orders(db: Session, params: PageParams, status: str | None, line_code: str | None,
                     start: date | None, end: date | None, wo_nos: list[str]):
    stmt = select(WorkOrder).order_by(WorkOrder.planned_start, WorkOrder.wo_no)
    if status == "未完成":
        stmt = stmt.where(WorkOrder.status.in_(OPEN_WO_STATUS))
    elif status:
        stmt = stmt.where(WorkOrder.status == status)
    if line_code:
        stmt = stmt.where(WorkOrder.line_code == line_code)
    # 日期过滤：计划时间窗口与 [start, end] 有交集即返回
    if start:
        stmt = stmt.where(WorkOrder.planned_end >= datetime.combine(start, time.min))
    if end:
        stmt = stmt.where(WorkOrder.planned_start <= datetime.combine(end, time.max))
    if wo_nos:
        stmt = stmt.where(WorkOrder.wo_no.in_(wo_nos))
    rows, total = _page(db, stmt, params)
    return [wo_dict(w) for w in rows], total


def work_order_detail(db: Session, wo_no: str) -> dict | None:
    wo = db.get(WorkOrder, wo_no)
    if not wo:
        return None
    plans = db.scalars(select(ProductionPlan).where(ProductionPlan.wo_no == wo_no).order_by(ProductionPlan.plan_date)).all()
    alarms = db.scalars(select(EquipmentAlarm).where(EquipmentAlarm.wo_no == wo_no).order_by(EquipmentAlarm.start_time)).all()
    return wo_dict(wo) | {
        "materials": wom_list(wo),
        "plans": [plan_dict(p) for p in plans],
        "alarms": [alarm_dict(a) for a in alarms],
    }


def work_order_materials(db: Session, wo_nos: list[str]) -> list[dict]:
    rows = db.scalars(select(WorkOrder).where(WorkOrder.wo_no.in_(wo_nos)).order_by(WorkOrder.wo_no)).unique().all()
    return [{
        "wo_no": w.wo_no, "product_name": w.product_name, "status": w.status, "priority": w.priority,
        "planned_start": w.planned_start, "line_code": w.line_code, "materials": wom_list(w),
    } for w in rows]


def list_plans(db: Session, params: PageParams, plan_date: date | None, start: date | None, end: date | None,
               line_code: str | None, wo_no: str | None):
    stmt = select(ProductionPlan).order_by(ProductionPlan.plan_date, ProductionPlan.line_code, ProductionPlan.plan_no)
    if plan_date:
        stmt = stmt.where(ProductionPlan.plan_date == plan_date)
    if start:
        stmt = stmt.where(ProductionPlan.plan_date >= start)
    if end:
        stmt = stmt.where(ProductionPlan.plan_date <= end)
    if line_code:
        stmt = stmt.where(ProductionPlan.line_code == line_code)
    if wo_no:
        stmt = stmt.where(ProductionPlan.wo_no == wo_no)
    rows, total = _page(db, stmt, params)
    return [plan_dict(p) for p in rows], total


def list_lines(db: Session, line_code: str | None) -> list[dict]:
    stmt = select(ProductionLine).order_by(ProductionLine.line_code)
    if line_code:
        stmt = stmt.where(ProductionLine.line_code == line_code)
    lines = db.scalars(stmt).all()
    active = dict(db.execute(
        select(EquipmentAlarm.line_code, func.count()).where(EquipmentAlarm.end_time.is_(None)).group_by(EquipmentAlarm.line_code)
    ).all())
    running: dict[str, list[str]] = {}
    for wo_no, lc in db.execute(select(WorkOrder.wo_no, WorkOrder.line_code).where(WorkOrder.status == "生产中")):
        running.setdefault(lc, []).append(wo_no)
    return [{
        "line_code": ln.line_code, "name": ln.name, "workshop": ln.workshop, "status": ln.status,
        "daily_capacity": ln.daily_capacity, "supervisor": ln.supervisor, "equipment": ln.equipment,
        "active_alarms": active.get(ln.line_code, 0), "running_work_orders": running.get(ln.line_code, []),
    } for ln in lines]


def list_alarms(db: Session, params: PageParams, start: date | None, end: date | None, line_code: str | None,
                level: str | None, wo_no: str | None, equipment_code: str | None, active_only: bool):
    stmt = select(EquipmentAlarm).order_by(EquipmentAlarm.start_time.desc())
    if start:
        stmt = stmt.where(EquipmentAlarm.start_time >= datetime.combine(start, time.min))
    if end:
        stmt = stmt.where(EquipmentAlarm.start_time <= datetime.combine(end, time.max))
    if line_code:
        stmt = stmt.where(EquipmentAlarm.line_code == line_code)
    if level:
        stmt = stmt.where(EquipmentAlarm.alarm_level == level)
    if wo_no:
        stmt = stmt.where(EquipmentAlarm.wo_no == wo_no)
    if equipment_code:
        stmt = stmt.where(EquipmentAlarm.equipment_code == equipment_code)
    if active_only:
        stmt = stmt.where(EquipmentAlarm.end_time.is_(None))
    rows, total = _page(db, stmt, params)
    return [alarm_dict(a) for a in rows], total
