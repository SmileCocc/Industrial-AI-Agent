"""一键重置模拟数据：python -m seed [erp|mes]

只删除并重建 industrial_erp / industrial_mes 中本项目定义的表，不触碰实例中的其他库。
"""
import sys
from collections import Counter

from sqlalchemy import insert
from sqlalchemy.orm import DeclarativeBase

from common.config import get_settings
from common.db import ensure_database, make_engine
from erp_service import models as erp
from mes_service import models as mes
from seed.generate import build

# 表的插入顺序（先主表后明细表）
ERP_TABLES = [erp.Supplier, erp.Material, erp.PurchaseOrder, erp.InventoryTransaction]
MES_TABLES = [mes.ProductionLine, mes.Equipment, mes.WorkOrder, mes.WorkOrderMaterial, mes.ProductionPlan, mes.EquipmentAlarm]


def reset(db_name: str, base: type[DeclarativeBase], tables: list, data: dict) -> None:
    ensure_database(db_name)
    engine = make_engine(db_name)
    base.metadata.drop_all(engine)
    base.metadata.create_all(engine)
    with engine.begin() as conn:
        for model in tables:
            rows = data[model.__tablename__]
            conn.execute(insert(model), rows)
            print(f"  {db_name}.{model.__tablename__}: {len(rows)} 条")
    engine.dispose()


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    if target not in ("all", "erp", "mes"):
        sys.exit("用法: python -m seed [all|erp|mes]")
    s = get_settings()
    data = build()
    if target in ("all", "erp"):
        reset(s.erp_db_name, erp.ErpBase, ERP_TABLES, data["erp"])
    if target in ("all", "mes"):
        reset(s.mes_db_name, mes.MesBase, MES_TABLES, data["mes"])
    status = Counter(w["status"] for w in data["mes"]["work_orders"])
    print("工单状态分布:", dict(status))
    print("场景工单:", ", ".join(f"{k}={v}" for k, v in data["wo_no_of"].items()))


if __name__ == "__main__":
    main()
