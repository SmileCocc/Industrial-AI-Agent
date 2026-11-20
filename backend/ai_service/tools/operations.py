"""经营分析仅使用业务 HTTP 数据；所有日期按本地生产日。"""
from collections import defaultdict
from datetime import date, timedelta

from .shortage import analyze, chunks, pages


def totals(rows):
    planned = sum(r['planned_qty'] for r in rows)
    actual = sum(r['actual_qty'] for r in rows)
    return {'planned': planned, 'actual': actual, 'rate_pct': round(100 * actual / planned, 2) if planned else None}


async def operations(get, scenario):
    today = date.today()
    day = today.isoformat()
    yesterday = (today - timedelta(days=1)).isoformat()
    start = (today - timedelta(days=6)).isoformat() if scenario == 'equipment' else day
    if scenario == 'inventory':
        rows = await pages(get, 'ERP', '/inventory/low-stock', {})
        codes = sorted({r['supplier_code'] for r in rows})
        suppliers = {}
        for batch in chunks(codes, 50):
            for supplier in await pages(get, 'ERP', '/suppliers', {'codes': ','.join(batch)}):
                suppliers[supplier['supplier_code']] = supplier['name']
        return {'date': day, 'count': len(rows), 'materials': [
            {k: r[k] for k in ('material_code', 'name', 'unit', 'available_stock', 'safety_stock', 'gap_to_safety', 'supplier_code')} |
            {'supplier': suppliers.get(r['supplier_code'])} for r in rows]}

    alarms = await pages(get, 'MES', '/equipment/alarms', {'start_date': start, 'end_date': day})
    lines = await get('MES', '/production-lines', {})
    if scenario == 'equipment':
        devices = defaultdict(list)
        for a in alarms:
            devices[a['equipment_code']].append(a)
        orders = {}
        for batch in chunks(sorted({a['wo_no'] for a in alarms if a['wo_no']}), 50):
            for w in await pages(get, 'MES', '/work-orders', {'wo_nos': ','.join(batch)}):
                orders[w['wo_no']] = {k: w[k] for k in ('status', 'completion_rate', 'is_overdue')}
        return {'start': start, 'end': day, 'alarm_count': len(alarms), 'devices': [
            {'code': code, 'name': group[0]['equipment_name'], 'line': group[0]['line_code'], 'count': len(group),
             'active': sum(a['is_active'] for a in group), 'severe': sum(a['alarm_level'] == '严重' for a in group),
             'example_alarm': group[0]['alarm_id'], 'orders': sorted({a['wo_no'] for a in group if a['wo_no']})}
            for code, group in devices.items()], 'linked_orders': orders,
            'line_status': {r['line_code']: r['status'] for r in lines}}

    plans = await pages(get, 'MES', '/production-plans', {'plan_date': day})
    result = {'date': day, 'total': totals(plans), 'lines': [
        {'line': line['line_code'], 'name': line['name'], **totals([p for p in plans if p['line_code'] == line['line_code']]),
         'alarms_started_today': sum(a['line_code'] == line['line_code'] for a in alarms)} for line in lines]}
    if scenario == 'efficiency':
        prior = await pages(get, 'MES', '/production-plans', {'plan_date': yesterday})
        shortage = await analyze(get, None)
        orders = await pages(get, 'MES', '/work-orders', {'start_date': day, 'end_date': day})
        result.update(previous_date=yesterday, previous=totals(prior),
                      delayed_orders=[w['wo_no'] for w in orders if w['is_overdue']],
                      shortages={w['wo_no']: [(g['material_code'], g['shortage_qty']) for g in w['shortages']]
                                 for w in shortage['work_orders'] if w['shortages']},
                      active_alarms=[{'id': a['alarm_id'], 'line': a['line_code'], 'order': a['wo_no']} for a in
                                     await pages(get, 'MES', '/equipment/alarms', {'active_only': True})])
    return result
