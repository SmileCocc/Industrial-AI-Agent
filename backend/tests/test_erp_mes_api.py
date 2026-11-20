"""ERP / MES 接口测试：通过真实 HTTP 请求访问已启动的服务（需先运行 dev.ps1 或单独启动 8001/8002）。

运行：.venv\\Scripts\\python -m pytest tests/test_erp_mes_api.py -v
"""
from datetime import date, timedelta

import httpx
import pytest

from common.config import get_settings

S = get_settings()
TODAY = date.today()


@pytest.fixture(scope="module")
def erp():
    with httpx.Client(base_url=S.erp_base_url, timeout=10) as c:
        yield c


@pytest.fixture(scope="module")
def mes():
    with httpx.Client(base_url=S.mes_base_url, timeout=10) as c:
        yield c


def ok(resp: httpx.Response):
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------- ERP ----------------

def test_erp_health(erp):
    assert ok(erp.get("/health"))["database_ok"] is True


def test_materials_list_and_filter(erp):
    data = ok(erp.get("/api/materials", params={"page_size": 200}))
    assert data["total"] >= 30
    assert ok(erp.get("/api/materials", params={"category": "功率器件"}))["total"] == 2
    assert ok(erp.get("/api/materials", params={"keyword": "IGBT"}))["items"][0]["material_code"] == "MAT-1001"


def test_material_detail(erp):
    d = ok(erp.get("/api/materials/MAT-1001"))
    assert d["supplier"]["supplier_code"] == "SUP-001"
    assert d["recent_transactions"]
    assert any(po["status"] == "已延期" and po["is_overdue"] for po in d["open_purchase_orders"])


def test_material_not_found_and_bad_code(erp):
    assert erp.get("/api/materials/MAT-9999").status_code == 404
    assert erp.get("/api/materials/abc").status_code == 422


def test_inventory_batch(erp):
    data = ok(erp.get("/api/inventory", params={"codes": "MAT-1001,MAT-1002,MAT-1007"}))
    assert {i["material_code"] for i in data["items"]} == {"MAT-1001", "MAT-1002", "MAT-1007"}
    assert erp.get("/api/inventory", params={"codes": "MAT-1001,DROP TABLE"}).status_code == 422


def test_low_stock(erp):
    items = ok(erp.get("/api/inventory/low-stock"))["items"]
    codes = {i["material_code"] for i in items}
    # 缺料场景物料和“低库存但不缺料”物料都应出现
    assert {"MAT-1001", "MAT-1018", "MAT-1007", "MAT-1033", "MAT-1036", "MAT-1027"} <= codes
    assert all(i["available_stock"] < i["safety_stock"] and i["supplier_name"] for i in items)


def test_transactions(erp):
    data = ok(erp.get("/api/inventory/transactions", params={"page_size": 200}))
    assert data["total"] >= 50
    one = ok(erp.get("/api/inventory/transactions", params={"material_code": "MAT-1031", "page_size": 200}))["items"]
    # 余额连续性：按时间正序，每条余额 = 上一条余额 + 本次数量
    rows = sorted(one, key=lambda x: (x["txn_time"], x["id"]))
    for prev, cur in zip(rows, rows[1:]):
        assert abs(prev["balance_after"] + cur["quantity"] - cur["balance_after"]) < 1e-6
    current = ok(erp.get("/api/materials/MAT-1031"))["current_stock"]
    assert abs(rows[-1]["balance_after"] - current) < 1e-6
    assert erp.get("/api/inventory/transactions",
                   params={"start_date": "2026-12-01", "end_date": "2026-11-01"}).status_code == 422


def test_suppliers(erp):
    assert ok(erp.get("/api/suppliers"))["total"] >= 10
    assert ok(erp.get("/api/suppliers", params={"codes": "SUP-001"}))["items"][0]["name"].startswith("深圳")


def test_purchase_orders(erp):
    assert ok(erp.get("/api/purchase-orders"))["total"] >= 20
    open_pos = ok(erp.get("/api/purchase-orders", params={"status": "未完成"}))["items"]
    assert open_pos and all(p["status"] != "已完成" for p in open_pos)
    assert erp.get("/api/purchase-orders", params={"status": "xx"}).status_code == 422


def test_pagination_limit(erp):
    assert erp.get("/api/materials", params={"page_size": 500}).status_code == 422


# ---------------- MES ----------------

def test_mes_health(mes):
    assert ok(mes.get("/health"))["database_ok"] is True


def test_work_orders(mes):
    data = ok(mes.get("/api/work-orders", params={"page_size": 200}))
    assert data["total"] >= 20
    statuses = {w["status"] for w in data["items"]}
    assert {"待执行", "生产中", "已完成", "已延期"} <= statuses
    open_today = ok(mes.get("/api/work-orders", params={"status": "未完成", "start_date": TODAY, "end_date": TODAY}))
    assert all(w["status"] != "已完成" for w in open_today["items"])
    delayed = ok(mes.get("/api/work-orders", params={"status": "已延期"}))["items"]
    assert delayed and all(w["is_overdue"] for w in delayed)


def test_work_order_detail_and_materials(mes, erp):
    wo = ok(mes.get("/api/work-orders", params={"status": "待执行", "start_date": TODAY, "end_date": TODAY}))["items"][0]
    detail = ok(mes.get(f"/api/work-orders/{wo['wo_no']}"))
    assert detail["materials"] and detail["plans"]
    mats = ok(mes.get(f"/api/work-orders/{wo['wo_no']}/materials"))
    # 跨系统关联：MES 的物料编码都能在 ERP 查到
    codes = ",".join(m["material_code"] for m in mats)
    assert ok(erp.get("/api/inventory", params={"codes": codes}))["total"] == len(mats)
    assert mes.get("/api/work-orders/WO-20000101-001").status_code == 404


def test_batch_materials(mes):
    wos = ok(mes.get("/api/work-orders", params={"status": "未完成"}))["items"]
    nos = ",".join(w["wo_no"] for w in wos[:5])
    data = ok(mes.get("/api/work-orders/materials", params={"wo_nos": nos}))
    assert len(data) == 5 and all(d["materials"] for d in data)
    assert mes.get("/api/work-orders/materials").status_code == 422


def test_production_plans(mes):
    today = ok(mes.get("/api/production-plans", params={"plan_date": TODAY, "page_size": 200}))
    assert today["total"] > 0
    week = ok(mes.get("/api/production-plans", params={"start_date": TODAY - timedelta(days=6), "end_date": TODAY,
                                                     "page_size": 200}))
    assert week["total"] >= 20


def test_plan_actual_matches_work_order(mes):
    """工单已完成数量 = 该工单所有计划实际产量之和。"""
    for w in ok(mes.get("/api/work-orders", params={"page_size": 200}))["items"]:
        plans = ok(mes.get("/api/production-plans", params={"wo_no": w["wo_no"], "page_size": 200}))["items"]
        assert sum(p["actual_qty"] for p in plans) == w["completed_qty"], w["wo_no"]


def test_production_lines(mes):
    lines = ok(mes.get("/api/production-lines"))
    assert len(lines) >= 5
    l02 = next(x for x in lines if x["line_code"] == "L02")
    assert l02["status"] == "异常" and l02["active_alarms"] >= 1


def test_alarms(mes):
    data = ok(mes.get("/api/equipment/alarms", params={"page_size": 200}))
    assert data["total"] >= 30
    week = ok(mes.get("/api/equipment/alarms", params={"start_date": TODAY - timedelta(days=7), "page_size": 200}))
    cutoff = (TODAY - timedelta(days=7)).isoformat()
    expected = {a["alarm_id"] for a in data["items"] if a["start_time"][:10] >= cutoff}
    assert {a["alarm_id"] for a in week["items"]} == expected
    severe = ok(mes.get("/api/equipment/alarms", params={"line_code": "L02", "level": "严重"}))["items"]
    assert len(severe) >= 3 and any(a["is_active"] for a in severe)
    assert mes.get("/api/equipment/alarms", params={"level": "致命"}).status_code == 422


def test_delay_caused_by_alarm(mes):
    """设备异常导致延迟：延期工单关联到严重报警。"""
    delayed = ok(mes.get("/api/work-orders", params={"status": "已延期"}))["items"]
    linked = [w for w in delayed
              if any(a["alarm_level"] == "严重" for a in ok(mes.get(f"/api/work-orders/{w['wo_no']}"))["alarms"])]
    assert linked


def test_shortage_scenarios(mes, erp):
    """缺料场景：用今天的待执行工单与 ERP 可用库存核对，至少有严重缺料（某物料可用为 0 的剩余需求）。"""
    pending = ok(mes.get("/api/work-orders", params={"status": "待执行", "start_date": TODAY, "end_date": TODAY}))["items"]
    nos = ",".join(w["wo_no"] for w in pending)
    reqs = ok(mes.get("/api/work-orders/materials", params={"wo_nos": nos}))
    codes = sorted({m["material_code"] for r in reqs for m in r["materials"]})
    inv = {i["material_code"]: i for i in ok(erp.get("/api/inventory", params={"codes": ",".join(codes)}))["items"]}
    short = {m["material_code"] for r in reqs for m in r["materials"]
             if m["pending_qty"] > inv[m["material_code"]]["available_stock"]}
    assert {"MAT-1001", "MAT-1018"} <= short  # 变频器工单：IGBT、散热器不足
