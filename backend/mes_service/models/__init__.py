"""MES 数据表（库 industrial_mes）。物料编码与 ERP 一致，但不建跨库外键。"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

Qty = Numeric(14, 3)


class MesBase(DeclarativeBase):
    """MES 独立的元数据，建表时只会创建 MES 的表。"""


class ProductionLine(MesBase):
    __tablename__ = "production_lines"
    line_code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    workshop: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(10), comment="运行/异常/停机/维护")
    daily_capacity: Mapped[int] = mapped_column(comment="日产能（台）")
    supervisor: Mapped[str] = mapped_column(String(30))
    equipment: Mapped[list["Equipment"]] = relationship(back_populates="line", lazy="selectin")


class Equipment(MesBase):
    __tablename__ = "equipment"
    equipment_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    type: Mapped[str] = mapped_column(String(30))
    line_code: Mapped[str] = mapped_column(ForeignKey("production_lines.line_code"))
    status: Mapped[str] = mapped_column(String(10), comment="正常/故障/维护")
    line: Mapped[ProductionLine] = relationship(back_populates="equipment")


class WorkOrder(MesBase):
    __tablename__ = "work_orders"
    wo_no: Mapped[str] = mapped_column(String(20), primary_key=True)
    product_code: Mapped[str] = mapped_column(String(20))
    product_name: Mapped[str] = mapped_column(String(50))
    planned_qty: Mapped[int]
    completed_qty: Mapped[int]
    status: Mapped[str] = mapped_column(String(10), index=True, comment="待执行/生产中/已完成/已延期/暂停")
    priority: Mapped[str] = mapped_column(String(4), comment="高/中/低")
    planned_start: Mapped[datetime] = mapped_column(DateTime)
    planned_end: Mapped[datetime] = mapped_column(DateTime)
    line_code: Mapped[str] = mapped_column(ForeignKey("production_lines.line_code"), index=True)
    remark: Mapped[str | None] = mapped_column(String(200))
    line: Mapped[ProductionLine] = relationship(lazy="joined")
    materials: Mapped[list["WorkOrderMaterial"]] = relationship(lazy="selectin", order_by="WorkOrderMaterial.material_code")


class WorkOrderMaterial(MesBase):
    __tablename__ = "work_order_materials"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    wo_no: Mapped[str] = mapped_column(ForeignKey("work_orders.wo_no"), index=True)
    material_code: Mapped[str] = mapped_column(String(16), comment="ERP 物料编码")
    material_name: Mapped[str] = mapped_column(String(100), comment="主数据同步的物料名称")
    unit: Mapped[str] = mapped_column(String(10))
    required_qty: Mapped[Decimal] = mapped_column(Qty)
    issued_qty: Mapped[Decimal] = mapped_column(Qty, comment="已发料数量")


class ProductionPlan(MesBase):
    __tablename__ = "production_plans"
    plan_no: Mapped[str] = mapped_column(String(20), primary_key=True)
    plan_date: Mapped[date] = mapped_column(Date)
    shift: Mapped[str] = mapped_column(String(4))
    line_code: Mapped[str] = mapped_column(ForeignKey("production_lines.line_code"))
    wo_no: Mapped[str] = mapped_column(ForeignKey("work_orders.wo_no"))
    product_code: Mapped[str] = mapped_column(String(20))
    product_name: Mapped[str] = mapped_column(String(50))
    planned_qty: Mapped[int]
    actual_qty: Mapped[int]
    line: Mapped[ProductionLine] = relationship(lazy="joined")
    __table_args__ = (Index("ix_plan_date_line", "plan_date", "line_code"),)


class EquipmentAlarm(MesBase):
    __tablename__ = "equipment_alarms"
    alarm_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    equipment_code: Mapped[str] = mapped_column(ForeignKey("equipment.equipment_code"))
    line_code: Mapped[str] = mapped_column(ForeignKey("production_lines.line_code"))
    alarm_level: Mapped[str] = mapped_column(String(4), comment="提示/一般/严重")
    alarm_type: Mapped[str] = mapped_column(String(10))
    start_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, comment="为空表示未恢复")
    duration_min: Mapped[int | None]
    wo_no: Mapped[str | None] = mapped_column(String(20), comment="报警时在产工单")
    description: Mapped[str] = mapped_column(String(200))
    equipment: Mapped[Equipment] = relationship(lazy="joined")
