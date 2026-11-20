"""同一参数模型用于运行时校验和 OpenAI Schema。"""
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from common.schemas import EQUIPMENT_CODE, LINE_CODE, MATERIAL_CODE, SUPPLIER_CODE, WO_NO

Material = Annotated[str, Field(pattern=MATERIAL_CODE)]
Supplier = Annotated[str, Field(pattern=SUPPLIER_CODE)]
Order = Annotated[str, Field(pattern=WO_NO)]
Line = Annotated[str, Field(pattern=LINE_CODE)]
Orders = Annotated[list[Order], Field(min_length=1, max_length=50)]
Text = Annotated[str, Field(min_length=1, max_length=50)]


class Args(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Page(Args):
    page: int = Field(1, ge=1, le=10000, strict=True)
    page_size: int = Field(50, ge=1, le=50, strict=True)


class Inventory(Page):
    material_codes: Annotated[list[Material], Field(min_length=1, max_length=100)] | None = None
    category: Text | None = None


class Detail(Args):
    material_code: Material


class Suppliers(Page):
    supplier_code: Supplier | None = None
    keyword: Text | None = None


class Purchases(Page):
    material_code: Material | None = None
    supplier_code: Supplier | None = None
    status: Literal['已下单', '部分到货', '已完成', '已延期', '未完成'] | None = None


class Window(Page):
    line_code: Line | None = None
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode='after')
    def check_window(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError('日期范围无效')
        return self


class WorkOrders(Window):
    wo_nos: Orders | None = None
    status: Literal['待执行', '生产中', '已完成', '已延期', '暂停', '未完成'] | None = None


class Plans(Window):
    plan_date: date | None = None
    wo_no: Order | None = None


class Lines(Args):
    line_code: Line | None = None


class Alarms(Window):
    wo_no: Order | None = None
    equipment_code: Annotated[str, Field(pattern=EQUIPMENT_CODE)] | None = None
    level: Literal['提示', '一般', '严重'] | None = None
    active_only: bool = Field(False, strict=True)


class Materials(Args):
    wo_nos: Orders


class Shortage(Args):
    wo_nos: Orders | None = None


class Operations(Args):
    scenario: Literal['plan', 'inventory', 'equipment', 'efficiency'] = Field(description='今日计划、库存预警、近七日设备异常、今日经营分析')
