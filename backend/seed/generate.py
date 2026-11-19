"""根据 catalog 生成 ERP、MES 两套模拟数据（纯 Python 数据结构，不访问数据库）。

以今天为基准日；随机数使用固定种子，同一天重置结果完全一致。
"""
import math
import random
from datetime import date, datetime, time, timedelta

from seed.catalog import BOM, EQUIPMENT, LINES, MATERIALS, PRODUCTS, SUPPLIERS, WORK_ORDERS

INTEGER_UNITS = {"个", "块", "套", "张"}
OPEN_STATUS = ("待执行", "生产中", "已延期", "暂停")


def _qty(value: float, unit: str) -> float:
    return float(math.ceil(value)) if unit in INTEGER_UNITS else round(value, 3)


def _split(total: int, n: int) -> list[int]:
    base = total // n
    return [base] * (n - 1) + [total - base * (n - 1)]


def build(today: date | None = None) -> dict:
    today = today or date.today()
    rnd = random.Random(42)
    at = lambda off, h=8, m=0: datetime.combine(today + timedelta(days=off), time(h, m))  # noqa: E731
    unit_of = {m[0]: m[4] for m in MATERIALS}
    name_of = {m[0]: m[1] for m in MATERIALS}

    # ---------------- MES：工单、物料需求、生产计划 ----------------
    work_orders, wo_materials, plans = [], [], []
    wo_no_of: dict[str, str] = {}
    seq_by_date: dict[date, int] = {}
    plan_seq: dict[date, int] = {}

    for key, prod, line, s, e, qty, status, prio, rate, today_actual, issue_ratio, remark in WORK_ORDERS:
        start_day = today + timedelta(days=s)
        seq_by_date[start_day] = seq_by_date.get(start_day, 0) + 1
        wo_no = f"WO-{start_day:%Y%m%d}-{seq_by_date[start_day]:03d}"
        wo_no_of[key] = wo_no
        product_code, product_name = PRODUCTS[prod]

        # 生成每日计划：计划量平均分摊；过去按达成率、今天按指定产量、未来为 0
        offsets = list(range(s, e + 1))
        day_plans = _split(qty, len(offsets))
        rates = rate if isinstance(rate, list) else [rate] * len(offsets)
        rows = []
        for i, (off, planned) in enumerate(zip(offsets, day_plans)):
            if off < 0:
                actual = planned if status == "已完成" else round(planned * rates[i])
            elif off == 0:
                actual = today_actual
            else:
                actual = 0
            rows.append((off, planned, actual))
        if status == "已延期":
            # 延期工单今天继续生产，追加一条今日计划，计划量 = 剩余未完成数量
            done = sum(r[2] for r in rows)
            rows.append((0, qty - done, today_actual))
        completed = sum(r[2] for r in rows)

        for off, planned, actual in rows:
            d = today + timedelta(days=off)
            plan_seq[d] = plan_seq.get(d, 0) + 1
            plans.append({
                "plan_no": f"PP-{d:%Y%m%d}-{plan_seq[d]:03d}", "plan_date": d, "shift": "白班",
                "line_code": line, "wo_no": wo_no, "product_code": product_code, "product_name": product_name,
                "planned_qty": planned, "actual_qty": actual,
            })

        work_orders.append({
            "wo_no": wo_no, "product_code": product_code, "product_name": product_name,
            "planned_qty": qty, "completed_qty": completed, "status": status, "priority": prio,
            "planned_start": at(s, 8), "planned_end": at(e, 20), "line_code": line, "remark": remark,
        })
        for code, per_unit in BOM[prod].items():
            unit = unit_of[code]
            required = _qty(per_unit * qty, unit)
            wo_materials.append({
                "wo_no": wo_no, "material_code": code, "material_name": name_of[code], "unit": unit,
                "required_qty": required, "issued_qty": _qty(required * issue_ratio, unit),
            })

    # ---------------- ERP：库存数量由 MES 需求推导，保证缺料场景成立 ----------------
    wo_by_key = {k: w for k, w in zip([x[0] for x in WORK_ORDERS], work_orders)}
    pending = lambda key, code: next(  # noqa: E731  某工单某物料的未发料数量
        (m["required_qty"] - m["issued_qty"] for m in wo_materials
         if m["wo_no"] == wo_no_of[key] and m["material_code"] == code), 0)
    open_demand: dict[str, float] = {}
    for m in wo_materials:
        wo = next(w for w in work_orders if w["wo_no"] == m["wo_no"])
        if wo["status"] in OPEN_STATUS:
            open_demand[m["material_code"]] = open_demand.get(m["material_code"], 0) + m["required_qty"] - m["issued_qty"]

    # 指定场景的可用库存（缺料分析按“已开工优先，再按优先级、开工时间”分配库存）
    overrides = {
        "MAT-1001": pending("R1", "MAT-1001"),                                   # IGBT：只够在产 R1，P1 缺 100%
        "MAT-1018": pending("R1", "MAT-1018") + 0.4 * pending("P1", "MAT-1018"),  # 散热器：P1 缺 60%
        "MAT-1007": 0.8 * pending("P2", "MAT-1007"),                             # CPU 模块：P2 缺 20%
        "MAT-1002": sum(pending(k, "MAT-1002") for k in ("R3", "R6", "R7"))      # MOSFET：P3 单独够，合计后缺 50%
                    + 0.5 * pending("P3", "MAT-1002"),
    }
    low_but_enough = {"MAT-1033", "MAT-1036", "MAT-1027"}  # 低于安全库存但不缺料，用于区分“预警”和“缺料”

    materials = []
    for code, name, spec, cat, unit, sup, price, wh in MATERIALS:
        demand = open_demand.get(code, 0)
        if code in overrides:
            available = _qty(overrides[code], unit)
            safety = _qty(max(demand * 0.5, available * 1.5, 10), unit)
            reserved = 0.0
        else:
            available = _qty(demand * rnd.uniform(1.4, 2.6) + rnd.uniform(50, 300), unit)
            safety = _qty(available * 1.4, unit) if code in low_but_enough else _qty(demand * rnd.uniform(0.3, 0.6) + 20, unit)
            reserved = _qty(available * rnd.uniform(0, 0.08), unit)
        materials.append({
            "material_code": code, "name": name, "spec": spec, "category": cat, "unit": unit,
            "safety_stock": safety, "current_stock": round(available + reserved, 3), "reserved_stock": reserved,
            "available_stock": available, "unit_price": price, "warehouse": wh, "supplier_code": sup,
        })
    mat = {m["material_code"]: m for m in materials}
    supplier_of = {m[0]: m[5] for m in MATERIALS}
    lead_of = {s[0]: s[6] for s in SUPPLIERS}

    # 采购订单：在途 / 延期 / 部分到货 + 历史已完成
    po_specs = [
        ("MAT-1001", -25, -2, 600, 0, "已延期"),
        ("MAT-1001", -3, 12, 400, 0, "已下单"),
        ("MAT-1018", -10, 1, 500, 100, "部分到货"),
        ("MAT-1007", -15, 3, 300, 0, "已下单"),
        ("MAT-1002", -5, 2, 2000, 0, "已下单"),
        ("MAT-1027", -4, 3, 3000, 0, "已下单"),
    ]
    history = rnd.sample([m[0] for m in MATERIALS if m[0] not in overrides], 18)
    for code in history:
        order_off = -rnd.randint(18, 40)
        qty = _qty(mat[code]["current_stock"] * rnd.uniform(0.3, 0.6), unit_of[code])
        po_specs.append((code, order_off, min(order_off + lead_of[supplier_of[code]], -1), qty, qty, "已完成"))
    po_specs.sort(key=lambda x: x[1])
    purchase_orders, po_seq = [], {}
    for code, o_off, e_off, qty, recv, status in po_specs:
        od = today + timedelta(days=o_off)
        po_seq[od] = po_seq.get(od, 0) + 1
        purchase_orders.append({
            "po_no": f"PO-{od:%Y%m%d}-{po_seq[od]:03d}", "supplier_code": supplier_of[code], "material_code": code,
            "quantity": qty, "received_qty": recv, "status": status,
            "order_date": od, "expected_date": today + timedelta(days=e_off),
        })

    # 库存变动：采购入库 + 工单领料出库 + 少量盘点，倒推期初结存保证余额连续
    moves: list[dict] = []
    for po in purchase_orders:
        if po["received_qty"]:
            t = datetime.combine(min(po["expected_date"], today - timedelta(days=1)), time(10, 0))
            moves.append({"material_code": po["material_code"], "txn_type": "入库", "quantity": po["received_qty"],
                          "ref_no": po["po_no"], "txn_time": t, "operator": "仓管员-赵亮", "remark": "采购入库"})
    for m in wo_materials:
        if m["issued_qty"]:
            wo = next(w for w in work_orders if w["wo_no"] == m["wo_no"])
            moves.append({"material_code": m["material_code"], "txn_type": "出库", "quantity": -m["issued_qty"],
                          "ref_no": m["wo_no"], "txn_time": wo["planned_start"].replace(hour=7, minute=30),
                          "operator": "仓管员-孙婷", "remark": "生产领料"})
    for code in rnd.sample([m[0] for m in MATERIALS if m[0] not in overrides], 4):
        adj = -_qty(rnd.uniform(1, 5), unit_of[code])
        moves.append({"material_code": code, "txn_type": "盘点", "quantity": adj, "ref_no": None,
                      "txn_time": at(-rnd.randint(2, 8), 17, 30), "operator": "仓管员-赵亮", "remark": "月度盘点盘亏"})

    transactions = []
    for code in mat:
        rows = sorted((x for x in moves if x["material_code"] == code), key=lambda x: x["txn_time"])
        balance = round(mat[code]["current_stock"] - sum(x["quantity"] for x in rows), 3)
        if balance < 0:  # 理论上不会出现；出现时把差额计入期初，避免负库存
            balance = 0.0
        transactions.append({"material_code": code, "txn_type": "期初", "quantity": balance, "balance_after": balance,
                             "ref_no": None, "txn_time": at(-45, 0, 0), "operator": "系统", "remark": "期初结存"})
        for x in rows:
            balance = round(balance + x["quantity"], 3)
            transactions.append(x | {"balance_after": balance})

    # ---------------- MES：生产线、设备、报警 ----------------
    lines = [{"line_code": c, "name": n, "workshop": w, "status": "异常" if c == "L02" else "运行",
              "daily_capacity": cap, "supervisor": sup} for c, n, w, cap, sup in LINES]
    equipment = [{"equipment_code": ec, "name": en, "type": et, "line_code": lc,
                  "status": "故障" if ec == "EQ-L02-01" else "正常"}
                 for lc, items in EQUIPMENT.items() for ec, en, et in items]

    def running_wo(line: str, moment: datetime) -> str | None:
        for w in work_orders:
            if w["line_code"] == line and w["planned_start"] <= moment <= w["planned_end"] + timedelta(days=1) \
                    and w["status"] != "待执行":
                return w["wo_no"]
        return None

    # 设备异常导致延迟：L02 连续三天严重报警，关联延期工单 D1 与在产工单 R2
    d1, r2 = wo_no_of["D1"], wo_no_of["R2"]
    alarm_specs = [
        ("EQ-L02-01", "严重", "设备故障", at(-2, 8, 30), 120, d1, "绕线机断线保护频繁触发，停机更换张力器"),
        ("EQ-L02-02", "一般", "压力异常", at(-2, 14, 0), 45, d1, "转子压装压力超上限，调整工装后恢复"),
        ("EQ-L02-01", "严重", "设备故障", at(-1, 9, 10), 180, d1, "绕线张力波动超限，导致线圈不良率上升"),
        ("EQ-L02-03", "一般", "振动超限", at(-1, 15, 0), 40, d1, "动平衡机振动值超标，重新校准"),
        ("EQ-L02-01", "严重", "设备故障", at(0, 8, 20), None, r2, "绕线机伺服驱动器报过流故障，等待备件"),
        ("EQ-L02-02", "一般", "通讯异常", at(0, 10, 5), 25, r2, "压装机与 MES 通讯中断"),
    ]
    random_types = [
        ("温度异常", "设备温度超出设定范围"), ("通讯异常", "PLC 与上位机通讯超时"), ("卡料", "送料机构卡料"),
        ("气压不足", "气源压力低于 0.5MPa"), ("传感器异常", "检测传感器信号丢失"), ("电气故障", "电机过载保护动作"),
    ]
    all_eq = [(e["equipment_code"], e["line_code"]) for e in equipment if e["line_code"] != "L02"]
    for _ in range(28):
        ec, lc = rnd.choice(all_eq)
        off = -rnd.randint(0, 7)
        start = at(off, rnd.randint(8, 19), rnd.choice([0, 10, 20, 30, 40, 50]))
        if start > datetime.now():
            start = at(off - 1, start.hour, start.minute)
        atype, desc = rnd.choice(random_types)
        level = rnd.choices(["提示", "一般", "严重"], weights=[5, 4, 1])[0]
        dur = rnd.randint(5, 25) if level == "提示" else rnd.randint(15, 60)
        alarm_specs.append((ec, level, atype, start, dur, running_wo(lc, start), desc))

    alarm_specs.sort(key=lambda a: a[3])
    alarms, alarm_seq = [], {}
    line_of_eq = {e["equipment_code"]: e["line_code"] for e in equipment}
    for ec, level, atype, start, dur, wo_no, desc in alarm_specs:
        d = start.date()
        alarm_seq[d] = alarm_seq.get(d, 0) + 1
        alarms.append({
            "alarm_id": f"ALM-{d:%Y%m%d}-{alarm_seq[d]:03d}", "equipment_code": ec, "line_code": line_of_eq[ec],
            "alarm_level": level, "alarm_type": atype, "start_time": start,
            "end_time": start + timedelta(minutes=dur) if dur else None, "duration_min": dur,
            "wo_no": wo_no, "description": desc,
        })

    suppliers = [dict(zip(["supplier_code", "name", "category", "contact", "phone", "address", "lead_time_days", "rating"], s))
                 for s in SUPPLIERS]
    return {
        "erp": {"suppliers": suppliers, "materials": materials, "purchase_orders": purchase_orders,
                "inventory_transactions": transactions},
        "mes": {"production_lines": lines, "equipment": equipment, "work_orders": work_orders,
                "work_order_materials": wo_materials, "production_plans": plans, "equipment_alarms": alarms},
        "wo_no_of": wo_no_of,
    }
