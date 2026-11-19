# API 文档

服务启动后可在 Swagger 页面查看完整参数：ERP http://127.0.0.1:8001/docs ，MES http://127.0.0.1:8002/docs 。

## 通用约定

- 全部为只读 GET 接口。
- 列表返回 `{"items": [...], "total": n, "page": 1, "page_size": 50}`；`page_size` 上限 200，超出返回 422。
- 参数格式校验失败返回 422，资源不存在返回 404，未处理异常返回 500 `{"detail": "服务内部错误", "code": "INTERNAL_ERROR"}`。
- `.env` 中 `SERVICE_TOKEN` 非空时，`/api/*` 需要请求头 `X-Service-Token`，否则返回 401。`/health` 不校验。
- 编码格式：物料 `MAT-1001`，供应商 `SUP-001`，工单 `WO-20261118-001`，生产线 `L01`，设备 `EQ-L01-01`。
- 批量参数用逗号分隔，例如 `codes=MAT-1001,MAT-1002`，最多 100 个（批量工单物料需求最多 50 个）。

## ERP（8001，库 industrial_erp）

| 接口 | 参数 | 说明 |
|---|---|---|
| GET /health | | `database_ok` 表示数据库可用 |
| GET /api/materials | category, keyword, page, page_size | 物料列表，keyword 匹配编码/名称/规格 |
| GET /api/materials/categories | | 物料分类清单 |
| GET /api/materials/{code} | | 物料详情：主供应商、最近 10 条库存变动、未完成采购单 |
| GET /api/inventory | codes, category | 库存，含 `below_safety`、`gap_to_safety` |
| GET /api/inventory/low-stock | | 可用库存 < 安全库存的物料，按紧缺程度排序，含供应商与交货周期 |
| GET /api/inventory/transactions | material_code, start_date, end_date | 库存变动，`balance_after` 为变动后结存 |
| GET /api/suppliers | codes, keyword | 供应商 |
| GET /api/purchase-orders | material_codes, supplier_code, status | status 可选 已下单/部分到货/已完成/已延期/未完成；含 `pending_qty`、`is_overdue` |

库存口径：`available_stock = current_stock - reserved_stock`。

## MES（8002，库 industrial_mes）

| 接口 | 参数 | 说明 |
|---|---|---|
| GET /health | | |
| GET /api/work-orders | status, line_code, start_date, end_date, wo_nos | status 可选 待执行/生产中/已完成/已延期/暂停/未完成；日期过滤为计划时间窗口与区间有交集 |
| GET /api/work-orders/materials | wo_nos（必填） | 批量查询多张工单的物料需求 |
| GET /api/work-orders/{code} | | 工单详情：物料需求、每日计划、关联报警 |
| GET /api/work-orders/{code}/materials | | 单张工单物料需求，`pending_qty = required_qty - issued_qty` |
| GET /api/production-plans | plan_date, start_date, end_date, line_code, wo_no | 生产计划，含实际产量 `actual_qty` 与 `completion_rate`（%） |
| GET /api/production-lines | line_code | 生产线状态、设备、未恢复报警数、生产中工单 |
| GET /api/equipment/alarms | start_date, end_date, line_code, level, wo_no, equipment_code, active_only | 设备报警，`is_active` 表示未恢复 |

## 跨系统关联

MES 工单物料需求中的 `material_code` 与 ERP 物料编码一致。两个数据库之间没有外键，关联只能通过调用两边的 HTTP 接口完成。

## AI 服务（8000）

第三阶段实现，接口设计见 [architecture.md](architecture.md) 第 5.3 节。
