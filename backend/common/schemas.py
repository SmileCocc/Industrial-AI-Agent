"""跨服务共用的响应结构与参数约束。"""
import re
from typing import Generic, TypeVar

from fastapi import HTTPException, Query
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")

# 业务编码格式（ERP/MES 之间按这些编码关联）
MATERIAL_CODE = r"^MAT-\d{4}$"
SUPPLIER_CODE = r"^SUP-\d{3}$"
WO_NO = r"^WO-\d{8}-\d{3}$"
LINE_CODE = r"^L\d{2}$"
EQUIPMENT_CODE = r"^EQ-L\d{2}-\d{2}$"


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class PageParams:
    def __init__(self, page: int = Query(1, ge=1, le=10000), page_size: int = Query(50, ge=1, le=200)):
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def split_codes(raw: str | None, pattern: str, max_count: int = 100) -> list[str]:
    """解析逗号分隔的编码列表并逐个校验格式。"""
    if not raw:
        return []
    codes = [c.strip() for c in raw.split(",") if c.strip()]
    if len(codes) > max_count:
        raise HTTPException(status_code=422, detail=f"一次最多查询 {max_count} 个编码")
    bad = [c for c in codes if not re.match(pattern, c)]
    if bad:
        raise HTTPException(status_code=422, detail=f"编码格式不正确: {', '.join(bad[:5])}")
    return list(dict.fromkeys(codes))
