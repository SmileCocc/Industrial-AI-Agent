# Industrial AI Agent 架构设计（第一阶段）

> 状态：已确认（2026-11-18）。本文档记录所有关键技术决策，后续阶段如有调整在此更新，并在「决策记录」中注明原因。

## 1. 总体架构

```
┌──────────────────────────────┐
│  Vue 3 前端 (5173)            │  只访问 AI 服务一个入口
└──────────────┬───────────────┘
               │ HTTP /api/*
┌──────────────▼───────────────────────────────────────────┐
│  AI Agent 服务 (8000)  FastAPI                            │
│  ├─ /api/agent/*   Agent 对话（LangGraph + Tool Calling） │
│  ├─ /api/erp/*  /api/mes/*   只读网关（白名单 GET 转发）   │
│  ├─ /api/dashboard  驾驶舱聚合指标（后端计算）             │
│  ├─ /api/system/*   健康检查、调用记录、模型配置/连接测试   │
│  └─ industrial_agent 库（对话历史、执行轨迹、调用日志）    │
└───────┬──────────────────────────────┬───────────────────┘
        │ HTTPX（超时、服务令牌）        │
┌───────▼────────┐              ┌──────▼─────────┐
│ ERP 服务 (8001) │              │ MES 服务 (8002) │
│ industrial_erp  │              │ industrial_mes  │
└────────────────┘              └────────────────┘
        ▲ 业务编码关联：material_code / supplier_code ▲
        └── 同一 MySQL 实例上的三个独立库，无跨库外键、无跨库查询 ──┘

                 ┌───────────────────────────┐
AI 服务 ────────► │ 云端 OpenAI 兼容模型 API   │
                 └───────────────────────────┘
```

**关键决策**

| 编号 | 决策 | 理由 |
|---|---|---|
| D1 | 前端只调用 AI 服务（8000），ERP/MES 数据经 AI 服务只读网关转发 | 统一鉴权入口、统一记录「最近调用记录」、避免三处 CORS 配置；ERP/MES 保持纯业务服务 |
| D2 | 网关只转发白名单内的 GET 路径 | 第一版生产数据只读，杜绝前端借网关写数据 |
| D3 | ERP、MES、AI 服务各用一个独立 MySQL 库（`industrial_erp` / `industrial_mes` / `industrial_agent`），每个服务只持有自己库的连接；跨系统只通过业务编码关联 | 模拟真实系统数据隔离；Agent 只能通过 HTTP 获取 ERP/MES 数据 |
| D4 | 驾驶舱指标、缺料计算由后端 Python 代码确定性计算 | 指标不在前端写死；数值计算不交给大模型，避免算错 |
| D5 | 不引入 Redis、消息队列、Docker | Demo 规模不需要，降低 Windows 本地运行门槛 |
| D6 | 数据库使用本机已安装的 MySQL（3306），连接信息只放在 `.env` | 用户指定；库名加 `industrial_` 前缀，避免与实例中已有库冲突 |

## 2. 技术选型

| 层 | 选型 | 说明 |
|---|---|---|
| 前端 | Vue 3 + TS + Vite + Element Plus + Pinia + Vue Router + Axios + ECharts | 按需求指定 |
| Markdown | `markdown-it` + `DOMPurify` | 支持表格；渲染前做 XSS 过滤（模型输出视为不可信内容） |
| 后端框架 | FastAPI + Uvicorn + Pydantic v2 + pydantic-settings | 三个服务共用 |
| 数据库 | MySQL 9.x（本机 3306），字符集 utf8mb4 | 用户指定 |
| 数据访问 | SQLAlchemy 2.0（ORM）+ PyMySQL（+ cryptography，用于 MySQL 8+ 默认的 caching_sha2_password 认证） | ORM 自动参数化查询；PyMySQL 为纯 Python 驱动，在 Python 3.14 上无需编译 |
| Agent 编排 | LangGraph `StateGraph` | 单 Agent 循环：model 节点 ↔ tools 节点 |
| 模型调用 | `openai` 官方 Python SDK（`AsyncOpenAI`，自定义 `base_url`） | 直接拿到原生 `tool_calls`，便于校验是否真实调用工具、控制超时和错误类型；不额外引入 langchain-openai |
| 服务间调用 | HTTPX `AsyncClient` | 统一超时（连接 3s / 读取 10s，可配置） |
| 测试 | pytest + httpx | API 测试与工具调用测试 |
| 依赖管理 | `pyproject.toml` + `backend/.venv`（pip 安装） | 不强制 uv/poetry |

## 3. 目录结构

仓库根目录即当前 `hello-agent/`（等同需求中的 `industrial-ai-agent/`）。

```
hello-agent/
├── frontend/
│   └── src/
│       ├── api/          # axios 实例与各模块接口
│       ├── components/   # AgentTrace、ChatMessage、MetricCard、StatusTag 等
│       ├── layouts/      # MainLayout（侧边栏 + 顶栏）
│       ├── router/
│       ├── stores/       # chat、system
│       ├── types/        # 与后端 Pydantic 模型对应的 TS 类型
│       └── views/        # 9 个页面
├── backend/
│   ├── common/           # 配置加载、日志（含密钥脱敏）、统一响应、鉴权依赖占位
│   ├── ai_service/
│   │   ├── agent/        # graph.py（LangGraph）、llm.py（模型客户端）、prompts.py
│   │   ├── tools/        # erp_tools.py、mes_tools.py、registry.py、clients.py
│   │   ├── models/       # 请求/响应模型、industrial_agent 库的表
│   │   ├── api/          # agent、gateway、dashboard、system 路由
│   │   └── main.py
│   ├── erp_service/  {api, models, services, seed.py, main.py}   # seed.py 负责建库、建表、写入模拟数据
│   ├── mes_service/  {api, models, services, seed.py, main.py}
│   ├── tests/
│   ├── pyproject.toml
│   └── .env.example
├── scripts/  init.ps1  dev.ps1  stop.ps1  reset-data.ps1
├── docs/     architecture.md  api.md  demo-guide.md
├── .gitignore  CLAUDE.md  README.md
```

## 4. 数据库设计

### 4.1 时间基准

模拟数据以**重置当天**为基准日生成（例如工单计划开始时间 = 今天 ± N 天）。这样「今天」「最近一周」之类的问题在任何日期演示都有数据。重置数据即重新生成。

### 4.2 ERP（库 industrial_erp）

**suppliers 供应商**

| 字段 | 类型 | 说明 |
|---|---|---|
| supplier_code | TEXT PK | 如 `SUP-001` |
| name | TEXT | 供应商名称 |
| contact / phone | TEXT | 联系人、电话 |
| lead_time_days | INT | 平均交货周期 |
| rating | TEXT | A/B/C |

**materials 物料（含库存数量）**

| 字段 | 类型 | 说明 |
|---|---|---|
| material_code | TEXT PK | 如 `MAT-1001` |
| name / spec / category / unit | TEXT | 名称、规格、分类（电子件/结构件/包材/原材料…）、单位 |
| safety_stock | NUMERIC | 安全库存 |
| current_stock | NUMERIC | 当前库存（账面） |
| reserved_stock | NUMERIC | 已被其他订单占用 |
| available_stock | NUMERIC | 可用库存 = current − reserved（生成时计算并存储，只读系统无需触发器） |
| supplier_code | TEXT | 主供应商（逻辑关联 suppliers） |
| warehouse | TEXT | 仓库 |

**inventory_transactions 库存变动（≥50 条）**

`id, material_code, txn_type(入库/出库/调拨/盘点), quantity(带正负), balance_after, ref_no(采购单号或 MES 工单号), txn_time, operator`

**purchase_orders 采购订单**

`po_no PK, supplier_code, material_code, quantity, received_qty, status(已下单/部分到货/已完成/已延期), order_date, expected_date`

> 采购订单用于缺料分析时说明「是否已有在途补货、预计何时到货」。

### 4.3 MES（库 industrial_mes）

**production_lines 生产线（≥5）**

`line_code PK, name, workshop, status(运行/停机/维护), daily_capacity, supervisor`

**equipment 设备**

`equipment_code PK, name, type, line_code, status`

**work_orders 生产工单（≥20）**

| 字段 | 说明 |
|---|---|
| wo_no PK | 如 `WO-20261118-001` |
| product_code / product_name | 产品 |
| planned_qty / completed_qty | 计划数量、已完成数量 |
| status | 待执行 / 生产中 / 已完成 / 已延期 / 暂停 |
| planned_start / planned_end | 计划开始/结束时间 |
| line_code | 生产线 |
| priority | 高/中/低 |

**work_order_materials 工单物料需求**

`id, wo_no, material_code（对应 ERP 物料编码）, required_qty, issued_qty`

> 未发料需求 = required_qty − issued_qty，这是与 ERP 可用库存比较的数量。

**production_plans 生产计划（≥20）**

`plan_no PK, plan_date, line_code, product_code, wo_no, planned_qty, actual_qty, shift(白班/夜班)`

> 完成率 = actual_qty / planned_qty，按日、按生产线汇总。每日生产趋势也来自此表（覆盖过去 7 天 + 今天）。

**equipment_alarms 设备报警（≥30）**

`alarm_id PK, equipment_code, line_code, alarm_level(提示/一般/严重), alarm_type(温度/振动/卡料/通讯/电气), start_time, end_time(可空=未恢复), duration_min, wo_no(可空，报警发生时在产工单), description`

### 4.4 必备测试数据（种子脚本保证一定存在）

| 场景 | 构造方式 |
|---|---|
| 正常库存工单 | 所有物料未发料需求 ≤ 可用库存 |
| 部分缺料工单 | 1 种物料缺口约 10%–30% |
| 严重缺料工单 | 多种物料缺口 > 50%，或可用库存为 0 |
| 已完成工单 | completed_qty = planned_qty，status=已完成 |
| 延迟工单 | planned_end < 今天且未完成 |
| 设备异常导致延迟 | 同一生产线今天有「严重」报警且关联该工单，计划完成率明显偏低 |
| 物料竞争 | 两张工单需求同一物料，单张够、合计不够（检验 Agent 是否考虑需求汇总） |

种子数据使用固定随机种子，重置结果可复现。

## 5. API 设计

统一约定：
- 列表接口返回 `{ "items": [...], "total": n }`，支持 `page`、`page_size`（上限 200）及业务过滤参数。
- 错误返回 `{ "detail": "...", "code": "..." }`，HTTP 状态码按语义（400/404/422/500/502/504）。
- 所有参数由 Pydantic/Query 校验（编码格式用正则约束，日期用 `date` 类型）。
- ERP/MES 校验请求头 `X-Service-Token`（来自环境变量；为空时不校验，便于本地调试）。这是服务间鉴权预留位。

### 5.1 ERP（8001）

| 方法 路径 | 参数 | 说明 |
|---|---|---|
| GET /health | | 服务与数据库状态 |
| GET /api/materials | category, keyword, page, page_size | 物料列表 |
| GET /api/materials/{code} | | 物料详情（含主供应商、最近库存变动、在途采购） |
| GET /api/inventory | codes(逗号分隔，批量), category | 库存查询，缺料分析时批量取多个物料 |
| GET /api/inventory/low-stock | | available_stock < safety_stock 的物料，含缺口 |
| GET /api/inventory/transactions | material_code, start_date, end_date | 库存变动记录 |
| GET /api/suppliers | code, keyword | 供应商 |
| GET /api/purchase-orders | material_code, supplier_code, status | 采购订单 |

### 5.2 MES（8002）

| 方法 路径 | 参数 | 说明 |
|---|---|---|
| GET /health | | |
| GET /api/work-orders | status, line_code, start_date, end_date | 工单列表（含完成率） |
| GET /api/work-orders/{code} | | 工单详情 |
| GET /api/work-orders/{code}/materials | | 工单物料需求 |
| GET /api/work-orders/materials | wo_nos(批量) | 批量物料需求，避免 Agent 逐张调用超出次数限制 |
| GET /api/production-plans | plan_date, start_date, end_date, line_code | 生产计划（含实际产量、完成率） |
| GET /api/production-lines | | 生产线状态 |
| GET /api/equipment/alarms | start_date, end_date, line_code, level, wo_no | 设备报警 |

### 5.3 AI 服务（8000）

| 方法 路径 | 说明 |
|---|---|
| GET /health | |
| POST /api/agent/chat | `{conversation_id?, message}` → `{conversation_id, answer(markdown), trace[], tool_calls[], usage, duration_ms}` |
| POST /api/agent/chat/stream | 第二版：SSE，事件结构与 trace 相同 |
| GET /api/agent/conversations | 历史对话列表 |
| GET /api/agent/conversations/{id} | 对话消息与每轮执行轨迹 |
| GET /api/agent/tools | 工具清单（名称、描述、所属系统、JSON Schema 参数、调用统计） |
| GET /api/dashboard | 驾驶舱指标与图表数据（后端调 ERP/MES 后计算） |
| GET /api/erp/{path}、/api/mes/{path} | 只读网关（白名单） |
| GET /api/system/integrations | 三个服务的地址、健康检查结果、响应耗时 |
| GET /api/system/call-logs | 最近服务调用记录 |
| GET /api/system/model-config | 模型配置（API Key 只返回是否已配置，如 `sk-****`） |
| POST /api/system/model-test | 模型连接测试 + Tool Calling 能力探测 |

鉴权预留：所有 `/api/*` 路由挂 `Depends(get_current_user)`，第一版返回固定演示用户，后续可替换为 JWT。

## 6. Agent 设计

### 6.1 LangGraph 工作流

```
START → prepare（加载历史、注入系统提示和当前日期）
      → model（调用大模型，携带 tools 定义）
          ├─ 返回 tool_calls → tools（并发执行工具，记录轨迹）→ 回到 model
          ├─ 返回最终文本   → finalize（整理结构化结果）→ END
          └─ 超出步数/超时  → finalize（返回已获取的数据与说明）→ END
```

State 字段：`messages, trace, tool_call_count, step, started_at, error`。

### 6.2 约束

| 项 | 默认值（环境变量可调） |
|---|---|
| 模型最大轮次 `AGENT_MAX_STEPS` | 8 |
| 工具最大调用次数 `AGENT_MAX_TOOL_CALLS` | 15 |
| 单次模型请求超时 `MODEL_TIMEOUT` | 60s |
| 整体请求超时 `AGENT_TIMEOUT` | 120s |
| 单次工具 HTTP 超时 | 10s |
| 工具返回给模型的最大条数 | 50 条（超出截断并告知模型 total） |

### 6.3 工具

所有工具都是 Pydantic 参数模型 + 异步函数，函数内部只用 HTTPX 调用对应服务，自动生成 JSON Schema 传给模型。

| 工具 | 系统 | 调用接口 | 主要参数 |
|---|---|---|---|
| query_material_inventory | ERP | GET /api/inventory | material_codes: list[str], category |
| query_low_stock_materials | ERP | GET /api/inventory/low-stock | 无 |
| query_material_detail | ERP | GET /api/materials/{code} | material_code |
| query_supplier | ERP | GET /api/suppliers | supplier_code, keyword |
| query_purchase_orders | ERP | GET /api/purchase-orders | material_code, supplier_code, status |
| query_work_orders | MES | GET /api/work-orders | status, line_code, start_date, end_date |
| query_production_plans | MES | GET /api/production-plans | plan_date, start_date, end_date, line_code |
| query_production_line_status | MES | GET /api/production-lines | line_code |
| query_equipment_alarms | MES | GET /api/equipment/alarms | start_date, end_date, line_code, level |
| query_work_order_materials | MES | GET /api/work-orders/materials | wo_nos: list[str] |
| analyze_material_shortage（建议新增） | ERP+MES | 内部调用上面两类接口 | wo_nos 可选，默认今天待执行/生产中工单 |

**关于 `analyze_material_shortage`（已确认新增）**：缺料计算涉及按物料汇总多张工单需求、减去可用库存，交给大模型心算容易出错。建议增加这个组合工具，由 Python 确定性计算缺口，结果同时供 Agent 和驾驶舱「缺料工单」指标使用。它仍然只通过 HTTP 调用 ERP/MES。不加的话，模型需要自行比较两次工具返回的数字。

### 6.4 真实性保障

1. 模型只能通过 API 原生 `tool_calls` 字段触发工具；回复正文里出现的类工具 JSON 一律不解析、不执行。
2. 工具名不在注册表、参数校验失败：不调用业务系统，把错误作为 tool 结果返回给模型，并记入轨迹。
3. 业务服务超时/5xx：工具返回结构化错误（`{"error": "MES 服务超时"}`），模型需在报告中说明数据缺失。
4. 系统提示要求：结论必须引用工具数据；数据不足以证明的原因标注「待核实」。
5. 模型连接测试会发送一个强制 `tool_choice` 的探测请求，未返回 `tool_calls` 即判定「该模型不支持 Tool Calling」，对话接口在此状态下直接报错，不降级为纯聊天。
6. API Key 只在 `llm.py` 内部使用；日志格式化器对 `sk-`、`Bearer` 等模式统一脱敏；所有对外响应不包含 Key。

### 6.5 执行轨迹（前端可视化的数据来源）

每个轨迹事件：

```json
{
  "seq": 3,
  "stage": "understanding | planning | calling_mes | calling_erp | integrating | reporting | error",
  "type": "model_call | tool_call | final",
  "tool_name": "query_work_orders",
  "system": "MES",
  "arguments": {"status": "待执行", "start_date": "2026-11-18"},
  "status": "success | error | timeout",
  "duration_ms": 132,
  "summary": "返回 6 条工单",
  "error": null,
  "timestamp": "2026-11-18T09:30:01+08:00"
}
```

阶段由后端根据真实事件确定：首次模型调用 = 理解/规划，工具调用按所属系统标记为 MES/ERP，工具全部返回后的模型调用 = 整合数据，最终文本 = 生成报告。第一版随响应一次返回，第二版通过 SSE 逐条推送，事件结构不变。

### 6.6 五个场景对应的典型工具链

| 场景 | 工具链 |
|---|---|
| 缺料分析 | query_work_orders → analyze_material_shortage（或 query_work_order_materials + query_material_inventory）→ query_production_plans → query_purchase_orders |
| 计划完成率 | query_production_plans → query_production_line_status → query_equipment_alarms |
| 库存预警 | query_low_stock_materials → query_supplier → query_purchase_orders |
| 设备异常 | query_equipment_alarms → query_production_line_status → query_work_orders |
| 效率下降综合分析 | 计划 + 工单 + 缺料 + 报警，多步并发调用 |

工具链由模型自主决定，表中只是预期路径，用于验收时对照。

## 7. 安全与工程质量

- 只读：ERP/MES 第一版不提供任何写接口；数据重置只能通过本地脚本执行，不暴露 HTTP 接口。
- 无任意 SQL：所有查询为 ORM 固定查询，过滤参数绑定。
- 不涉及 PLC/设备控制，工具清单中没有任何控制类工具。
- 日志：`backend/logs/` 下按服务写文件，记录请求、工具调用、异常堆栈，密钥脱敏。
- `.env` 加入 `.gitignore`，仓库只提交 `.env.example`。

环境变量（`.env.example`）：

```
MODEL_PROVIDER=openai_compatible
MODEL_BASE_URL=
MODEL_API_KEY=
MODEL_NAME=
MODEL_TEMPERATURE=0.2
MODEL_MAX_TOKENS=4096
MODEL_TIMEOUT=60
AGENT_MAX_STEPS=8
AGENT_MAX_TOOL_CALLS=15
AGENT_TIMEOUT=120
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=
ERP_DB_NAME=industrial_erp
MES_DB_NAME=industrial_mes
AGENT_DB_NAME=industrial_agent
ERP_BASE_URL=http://127.0.0.1:8001
MES_BASE_URL=http://127.0.0.1:8002
SERVICE_TOKEN=
HTTP_TIMEOUT=10
LOG_LEVEL=INFO
```

## 8. Windows 开发环境

| 项 | 要求 | 本机检测结果 |
|---|---|---|
| Python | 3.11+ | 3.14.10（`E:\develop\Python314`） |
| Node.js | 18+ | 24.16.0 |
| npm | 9+ | 11.13.0 |
| Git | 任意 | 2.54.0 |
| PowerShell | 5.1+ | 5.1 |
| MySQL | 8.0+，3306 | 9.7.1，服务名 MySQL97，运行中 |

脚本行为：
- `init.ps1`：创建 `backend/.venv`、安装后端依赖、`npm install`、复制 `.env.example` 为 `.env`（不存在时）、检查 MySQL 连接、建库并生成模拟数据。
- `dev.ps1`：用 `Start-Process` 分别启动 ERP、MES、AI、Vite 四个进程（各自独立窗口/日志），PID 写入 `.run/pids.json`，启动后轮询 `/health`。
- `stop.ps1`：按 PID 文件结束进程，再按端口 8000/8001/8002/5173 兜底清理（`Get-NetTCPConnection`）。
- `reset-data.ps1`：调用 `python -m erp_service.seed` 与 `python -m mes_service.seed`，只删除并重建 `industrial_erp`、`industrial_mes` 两个库中本项目的表，不触碰实例中其他库。
- 每个服务也可单独启动：`uvicorn erp_service.main:app --port 8001`。

## 9. 开发计划

| 阶段 | 内容 | 验收方式 |
|---|---|---|
| 1 架构设计 | 本文档 | 用户确认 |
| 2 ERP/MES 服务 | MySQL 表结构、种子数据、API、init/dev/stop/reset 脚本 | 实际启动，pytest + 手动请求所有接口 |
| 3 AI Agent | 模型接入、连接测试、10+1 个工具、LangGraph、缺料场景 | 用真实模型完成缺料问答，检查轨迹中的真实 HTTP 调用 |
| 4 其他场景 | 场景二至五，系统提示调优 | 逐场景真实运行并核对数据 |
| 5 前端 | 9 个页面，Agent 轨迹可视化 | 浏览器实际操作 |
| 6 联调验收 | 异常场景（服务停机、模型超时、无 Tool Calling）、文档 | 全量测试记录写入 README |

## 10. 决策记录

| 日期 | 决策 | 状态 |
|---|---|---|
| 2026-11-18 | D1–D5、模型调用使用 openai SDK、SQLAlchemy 用于三个数据库 | 已确认 |
| 2026-11-18 | 新增 `analyze_material_shortage` 组合工具、批量物料需求接口 | 已确认 |
| 2026-11-18 | 数据库由 SQLite 改为本机 MySQL（D6） | 已确认（用户要求） |
| 2026-11-18 | 先使用 Python 3.14，依赖有问题再换版本 | 已确认 |
| 2026-11-18 | 模型通过本地 Magpie 网关（OpenAI 兼容接口）调用 | 已确认，第三阶段接入 |
