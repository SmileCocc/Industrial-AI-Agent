"""MES 接口响应模型。"""
from datetime import date, datetime

from common.schemas import ORMModel


class WorkOrderOut(ORMModel):
    wo_no: str
    product_code: str
    product_name: str
    planned_qty: int
    completed_qty: int
    completion_rate: float  # 完成率（%）
    status: str
    priority: str
    planned_start: datetime
    planned_end: datetime
    line_code: str
    line_name: str
    is_overdue: bool  # 计划结束时间已过但未完成
    remark: str | None


class WorkOrderMaterialOut(ORMModel):
    wo_no: str
    material_code: str
    material_name: str
    unit: str
    required_qty: float
    issued_qty: float
    pending_qty: float  # 未发料 = 需求 - 已发料，即仍需从仓库领用的数量


class WorkOrderMaterials(ORMModel):
    wo_no: str
    product_name: str
    status: str
    priority: str
    planned_start: datetime
    line_code: str
    materials: list[WorkOrderMaterialOut]


class PlanOut(ORMModel):
    plan_no: str
    plan_date: date
    shift: str
    line_code: str
    line_name: str
    wo_no: str
    product_code: str
    product_name: str
    planned_qty: int
    actual_qty: int
    completion_rate: float


class AlarmOut(ORMModel):
    alarm_id: str
    equipment_code: str
    equipment_name: str
    line_code: str
    alarm_level: str
    alarm_type: str
    start_time: datetime
    end_time: datetime | None
    duration_min: int | None
    is_active: bool  # 未恢复
    wo_no: str | None
    description: str


class EquipmentOut(ORMModel):
    equipment_code: str
    name: str
    type: str
    status: str


class LineOut(ORMModel):
    line_code: str
    name: str
    workshop: str
    status: str
    daily_capacity: int
    supervisor: str
    equipment: list[EquipmentOut]
    active_alarms: int  # 当前未恢复报警数
    running_work_orders: list[str]  # 生产中的工单


class WorkOrderDetail(WorkOrderOut):
    materials: list[WorkOrderMaterialOut]
    plans: list[PlanOut]
    alarms: list[AlarmOut]
