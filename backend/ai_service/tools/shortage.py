"""按未发料需求竞争分配 ERP 可用库存，只读，无库存预留副作用。"""
from collections import defaultdict
from datetime import date
from decimal import Decimal


class ToolError(ValueError):
    """可直接展示的工具错误，不包含上游响应或请求头。"""


def chunks(values, size):
    for i in range(0, len(values), size):
        yield values[i:i + size]


async def pages(get, system, path, params):
    rows = []
    for page in range(1, 6):
        data = await get(system, path, dict(params, page=page, page_size=50))
        batch = data['items']
        if data['page'] != page or len(batch) != min(50, max(0, data['total'] - len(rows))):
            raise ToolError('业务分页数据不完整')
        rows.extend(batch)
        if len(rows) == data['total']:
            return rows
    raise ToolError('参与分析的数据超过单次计算上限')


def allocate(orders, demands, inventory, targets):
    stock = {code: Decimal(str(row['available_stock'])) for code, row in inventory.items()}
    history = defaultdict(list)
    results = []
    # 在产先领料，同组按优先级、计划开工时间、工单号稳定排序。
    for order in sorted(orders, key=lambda w: (w['status'] != '生产中',
                        {'高': 0, '中': 1, '低': 2}[w['priority']], w['planned_start'], w['wo_no'])):
        no = order['wo_no']
        gaps = []
        for row in demands[no]:
            code = row['material_code']
            if code not in stock:
                continue  # 非目标工单的其他物料不会影响目标物料分配
            pending = max(Decimal(0), Decimal(str(row['pending_qty'])))
            before = max(Decimal(0), stock[code])
            allocated = min(pending, before)
            stock[code] = before - allocated
            gap = pending - allocated
            if no in targets and gap:
                gaps.append({'material_code': code, 'material_name': row['material_name'], 'unit': row['unit'],
                             'pending_qty': float(pending), 'available_stock': inventory[code]['available_stock'],
                             'available_before': float(before), 'allocated_qty': float(allocated),
                             'shortage_qty': float(gap), 'shortage_pct': round(float(100 * gap / pending), 2),
                             'prior_allocations': list(history[code][:50]), 'prior_allocation_total': len(history[code])})
            if allocated:
                history[code].append({'wo_no': no, 'allocated_qty': float(allocated)})
        if no in targets:
            results.append({'wo_no': no, 'status': order['status'], 'priority': order['priority'],
                            'shortages': gaps[:50], 'shortage_material_total': len(gaps)})
    return results


async def analyze(get, wo_nos):
    orders = await pages(get, 'MES', '/work-orders', {'status': '未完成'})
    today = date.today().isoformat()
    all_nos = [w['wo_no'] for w in orders]
    if len(set(all_nos)) != len(all_nos):
        raise ToolError('工单分页重复，请重试')
    targets = set(wo_nos or [w['wo_no'] for w in orders if w['status'] in ('生产中', '待执行')
                             and w['planned_start'][:10] <= today <= w['planned_end'][:10]])
    if targets.difference(all_nos):
        raise ToolError('指定工单不存在或已完成')
    if len(targets) > 50:
        raise ToolError('目标超过 50 张，请指定工单号')
    demands = {}
    if targets:
        for batch in chunks(all_nos, 50):
            rows = await get('MES', '/work-orders/materials', {'wo_nos': ','.join(batch)})
            demands.update({r['wo_no']: r['materials'] for r in rows})
        if set(demands) != set(all_nos):
            raise ToolError('工单需求数据不完整')
    codes = sorted({m['material_code'] for no in targets for m in demands[no]})
    if len(codes) > 250:
        raise ToolError('目标物料超过单次计算上限')
    inventory = {}
    for batch in chunks(codes, 50):
        rows = await pages(get, 'ERP', '/inventory', {'codes': ','.join(batch)})
        inventory.update({r['material_code']: r for r in rows})
    if set(inventory) != set(codes):
        raise ToolError('ERP 库存数据不完整')
    results = allocate(orders, demands, inventory, targets) if targets else []
    transactions = {}
    gap_codes = sorted({g['material_code'] for w in results for g in w['shortages']})
    for code in gap_codes[:50]:
        transactions[code] = await get('ERP', '/inventory/transactions',
                                       {'material_code': code, 'page': 1, 'page_size': 5})
    for w in results:
        w['plans'] = await get('MES', '/production-plans', {'wo_no': w['wo_no'], 'page': 1, 'page_size': 10})
    return {'work_orders': results, 'total': len(results), 'shortage_order_count': sum(bool(w['shortages']) for w in results),
            'competition_order_count': len(orders), 'transactions': transactions,
            'transaction_evidence_truncated': len(gap_codes) > 50 or any(w['shortage_material_total'] > 50 for w in results)}
