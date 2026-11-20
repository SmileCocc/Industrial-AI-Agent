"""只读工具入口。模型只能提交注册表声明的业务参数。"""
from datetime import datetime
from time import monotonic

import httpx
from pydantic import ValidationError

from common.config import get_settings
from . import arguments as a
from .operations import operations
from .shortage import analyze, ToolError

__all__ = ['schemas', 'execute', 'ToolError']

TOOLS = {
    'analyze_operations': (a.Operations, 'ERP+MES', '', '经营分析：选择场景以获取完整汇总与业务凭证'),
    'query_material_inventory': (a.Inventory, 'ERP', '/inventory', '按物料编码或分类查询库存'),
    'query_low_stock_materials': (a.Page, 'ERP', '/inventory/low-stock', '查询低于安全库存的物料'),
    'query_material_detail': (a.Detail, 'ERP', '/materials/{code}', '查询物料、供应商、近期流水和未完成采购单'),
    'query_supplier': (a.Suppliers, 'ERP', '/suppliers', '查询供应商'),
    'query_purchase_orders': (a.Purchases, 'ERP', '/purchase-orders', '查询采购订单、到货量和交期'),
    'query_work_orders': (a.WorkOrders, 'MES', '/work-orders', '查询工单状态、优先级和计划时间'),
    'query_production_plans': (a.Plans, 'MES', '/production-plans', '查询班次计划及实际产量'),
    'query_production_line_status': (a.Lines, 'MES', '/production-lines', '查询产线、设备及在产工单'),
    'query_equipment_alarms': (a.Alarms, 'MES', '/equipment/alarms', '查询设备报警记录'),
    'query_work_order_materials': (a.Materials, 'MES', '/work-orders/materials', '批量查询工单物料需求、已发料和待发料'),
    'analyze_material_shortage': (a.Shortage, 'ERP+MES', '', '分析竞争库存后的工单缺口，默认今日待执行和生产中工单'),
}


def schemas() -> list[dict]:
    return [{'type': 'function', 'function': {'name': name, 'description': desc,
            'parameters': args.model_json_schema()}} for name, (args, _, _, desc) in TOOLS.items()]


async def execute(name: str, arguments: dict, events: list) -> dict:
    if name not in TOOLS:
        raise ToolError('未知工具')
    model, system, path, _ = TOOLS[name]
    try:
        params = model.model_validate(arguments).model_dump(mode='json', exclude_none=True)
    except ValidationError:
        raise ToolError('工具参数不合法，请检查格式、范围和必填项') from None

    try:
        settings = get_settings()
        bases = {'ERP': settings.erp_base_url, 'MES': settings.mes_base_url}
        token = settings.service_token.get_secret_value()
        async with httpx.AsyncClient(timeout=settings.http_timeout, trust_env=False,
                                     headers={'X-Service-Token': token} if token else {}) as client:
            async def get(system, path, params):
                start = monotonic()
                event = {'stage': 'calling_' + system.lower(), 'type': 'tool_call', 'tool_name': name,
                         'system': system, 'method': 'GET', 'path': '/api' + path,
                         'arguments': {k: ('[已省略]' if k in ('keyword', 'category') else v)
                                       for k, v in params.items()}, 'status': 'error',
                         'timestamp': datetime.now().astimezone().isoformat(), 'error': None}
                try:
                    r = await client.get(bases[system].rstrip('/') + '/api' + path, params=params)
                    event['status_code'] = r.status_code
                    r.raise_for_status()
                    data = r.json()
                    if not isinstance(data, (list, dict)):
                        raise ValueError()
                    event['status'] = 'success'
                    return data
                except httpx.TimeoutException:
                    event['status'] = 'timeout'
                    raise ToolError(system + ' 服务超时') from None
                except (ValueError, httpx.HTTPError):
                    raise ToolError(system + ' 服务请求失败') from None
                finally:
                    if event['status'] != 'success':
                        event['error'] = system + ' 请求未成功'
                    event.update(seq=len(events) + 1, duration_ms=round((monotonic()-start)*1000),
                                 summary=event['error'] or '已获取业务数据')
                    events.append(event)

            if model is a.Operations:
                return await operations(get, params['scenario'])
            if model is a.Shortage:
                return await analyze(get, params.get('wo_nos'))
            if model is a.Detail:
                path = path.format(code=params.pop('material_code'))
            aliases = {a.Inventory: ('material_codes', 'codes'), a.Suppliers: ('supplier_code', 'codes'),
                       a.Purchases: ('material_code', 'material_codes')}
            if model in aliases:
                source, dest = aliases[model]
                if source in params:
                    params[dest] = params.pop(source)
            params = {k: ','.join(v) if isinstance(v, list) else v for k, v in params.items()}
            data = await get(system, path, params)
            if isinstance(data, list):
                return {'items': data[:50], 'total': len(data), 'truncated': len(data) > 50}
            if 'items' in data:
                data['truncated'] = data['page'] * data['page_size'] < data['total']
            return data
    except ToolError:
        raise
    except Exception:
        # 外部异常可能包含 URL、响应体或凭据，不能传给模型。
        raise ToolError('工具配置或服务数据异常') from None
