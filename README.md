# Industrial AI Agent

制造业企业 AI 智能助手：AI Agent 通过 HTTP 对接模拟 ERP、MES 两个独立业务系统，完成跨系统数据查询、生产分析、缺料诊断和业务问答。

- 架构设计：[docs/architecture.md](docs/architecture.md)
- 接口文档：[docs/api.md](docs/api.md)
- 演示指南：[docs/demo-guide.md](docs/demo-guide.md)

## 项目进展

| 阶段 | 内容 | 状态 |
|---|---|---|
| 1 | 架构设计 | 已完成（2026-11-18 确认，数据库改为 MySQL） |
| 2 | ERP/MES 模拟服务 | 已完成，20 项接口测试通过 |
| 3 | AI Agent（模型接入、工具调用、缺料分析） | 已通过 Magpie 原生工具调用和缺料对话端到端验收 |
| 4 | 生产计划、库存预警、设备异常、生产经营分析 | 已完成，4 项真实模型验收通过 |
| 5 | 前端页面 | 已完成，九页已接入真实 API |
| 6 | 联调与验收 | 离线测试、异常场景、浏览器验收和 5 项真实模型验收均已通过 |

## 环境要求

Windows 11 / Python 3.11+（当前使用 3.14）/ Node.js 18+ / MySQL 8+（本机 3306）

## 快速开始

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\init.ps1   # 创建 .venv、安装依赖、建库并生成模拟数据
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1    # 启动服务（已实现的服务）
powershell -ExecutionPolicy Bypass -File .\scripts\stop.ps1   # 停止服务
powershell -ExecutionPolicy Bypass -File .\scripts\reset-data.ps1  # 以今天为基准重置模拟数据
```

首次运行 init.ps1 会从 `backend/.env.example` 复制出 `backend/.env`，需要填写 `MYSQL_PASSWORD` 和模型配置。

| 服务 | 端口 | 数据库 |
|---|---|---|
| AI Agent | 8000 | industrial_agent |
| ERP | 8001 | industrial_erp |
| MES | 8002 | industrial_mes |
| 前端 | 5173 | |

## 模拟数据

以重置当天为基准日期生成，同一天重置结果相同。

| 数据 | 数量 |
|---|---|
| 供应商 / 物料 | 13 / 36 |
| 采购订单 / 库存变动 | 24 / 198 |
| 生产线 / 设备 | 6 / 19 |
| 工单 / 工单物料需求 | 23 / 207 |
| 生产计划 / 设备报警 | 68 / 34 |

内置测试场景（今天的待执行工单）：

| 场景 | 数据 |
|---|---|
| 严重缺料 | 变频器工单：IGBT 可用库存只够在产工单，缺 100%；散热器缺 60% |
| 部分缺料 | 控制器工单：CPU 模块缺 20% |
| 物料竞争 | 电源工单：MOSFET 单张够用，与 3 张在产工单合计后缺 50% |
| 正常库存 | 其他工单 |
| 设备异常导致延期 | L02 伺服电机线连续 3 天严重报警，今天仍有 1 条未恢复，关联延期工单 |
| 原因待核实的延期 | L03 控制器延期工单，无报警、无缺料 |
| 低库存但不缺料 | 导热硅脂、产品标签、屏蔽电缆低于安全库存，但满足工单需求 |

今日计划总完成率约 70%，L02 约 23%，L01、L03、L06 也未达标。

## 测试

服务启动后，在 backend 目录运行：

```powershell
.venv\Scripts\python -m pytest
```

2026-11-18 实测：init.ps1 → dev.ps1 → pytest 20 passed → stop.ps1 全流程通过。

演示步骤和预期结果见 [docs/demo-guide.md](docs/demo-guide.md)。

## 第三阶段验收

Agent 服务已接入 11 个只读工具。2026-11-19 在已有模拟数据上直接运行缺料工具，共发生 19 次 ERP/MES HTTP 请求。工单 WO-20261118-006 需要 250 个 IGBT，90 个可用库存已分配给在产工单，因此缺 250 个。未重置数据库。

在 `backend/.env` 填写 Magpie 的 `MODEL_BASE_URL`（OpenAI 兼容 API 根地址）、`MODEL_NAME`、`MODEL_API_KEY`。使用 `scripts/dev.ps1` 启动三个服务。在 http://127.0.0.1:8000/docs 可依次执行 `POST /api/system/model-test` 和 `POST /api/agent/chat`。

真实模型验收用例位于 `backend/tests/test_agent_live.py`。PowerShell 在 `backend` 目录设置 `$env:RUN_MAGPIE_LIVE="1"` 后运行 `.venv\Scripts\python -m pytest tests/test_agent_live.py -q`。未提供网关配置时探测和对话均返回 503。2026-11-19 实测通过（1 passed，93.65 秒）。首次报告生成超过 60 秒，本机模型和整轮超时分别调整为 115 秒、170 秒。

## 第四阶段验收

`analyze_operations` 工具支持四类业务分析。在三个服务启动后，从 `backend` 目录启用 `RUN_MAGPIE_LIVE=1` 并执行 `python -m pytest tests/test_operations_live.py -q`。测试从自然语言问题进入 Agent，再通过业务接口独立核对聚合结果。

2026-11-19 实测四项均通过。今日计划 1,995 台，MES 已报工 0 台。ERP 返回 7 种低库存物料。11 月 13–19 日共有 13 台设备产生 27 条报警。综合报告对比昨日完成率 70.16%，将实际效率变化列为待核实。

## 第五阶段使用与验证

运行 `scripts/dev.ps1` 后打开 http://127.0.0.1:5173 。新检出项目先安装前端依赖（frontend 下 `npm ci`）。已有模拟数据可直接使用。助手支持历史对话、Markdown 表格和逐步展开的工具轨迹，驾驶舱从后端计算六项指标。

已通过 `npm run build`；浏览器验证了九页导航、工单详情、四张图表、历史报告、375px 助手布局及真实库存问答。

## 第六阶段验收

2026-11-20 用 reset-data.ps1 重置数据，dev.ps1 启动四个服务，健康检查全部通过。

| 项目 | 结果 |
|---|---|
| 离线测试（接口、工具、Agent 循环、控制台） | `pytest` 51 passed，5 skipped（跳过的是需要 `RUN_MAGPIE_LIVE=1` 的真实模型用例） |
| 跨系统数据 | 直接执行工具：缺料分析 17 次 HTTP 请求，识别 3 张缺料工单；驾驶舱完成率 70.16%（2,031 / 1,425）与 MES 计划汇总一致 |
| 真实模型 | 原服务商停用后改用本机 Magpie（`http://127.0.0.1:3425/v1`）。当前模型 `kiro/claude-haiku-5.5`，2026-11-20 实测 5 passed（123.5 秒）。中途在 `opencode-zen/deepseek-v4.1-flash-free` 上首轮 2 passed 3 failed，原因是输出达到 4,096 token 上限被截断（按设计返回 502）；`MODEL_MAX_TOKENS` 调为 8192 后该 3 项也通过 |
| 非法参数 | 未登记查询参数、超出范围的分页、错误日期、空消息、超长消息、多余字段、非法 UUID 均返回 422 |
| 白名单 | `/api/erp/admin/sql`、格式错误的编码、`..` 和 `%2e%2e` 路径穿越均返回 404 |
| ERP 停机 | 网关返回 502，驾驶舱返回 502，集成页 ERP 为异常，MES 不受影响；缺料工具返回「ERP 服务请求失败」，轨迹保留成功的 MES 请求和失败的 ERP 请求。重启后恢复 |
| 业务接口超时 | ERP 地址不可达时工具在 1.1 秒后返回「ERP 服务超时」，事件状态为 timeout |
| 模型异常 | 空密钥 503；网关不可达 502；限流 429。三种情况都不生成回答，并保存失败轨迹 |
| 密钥 | 扫描 11 个日志文件、16 条对话记录、6 个控制台接口响应和前端构建产物，均未出现模型密钥；配置页只显示是否已配置 |
| 前端 | 九页均加载真实数据；工单状态筛选和详情抽屉正常；历史报告回放含表格和 8 步轨迹；模型限流时助手和配置页显示「模型服务限流」 |

## 性能与构建优化

2026-11-20 处理了第一阶段验收记录的已知问题。

| 项目 | 处理 | 结果 |
|---|---|---|
| 驾驶舱刷新慢 | 缺料分析、经营分析、驾驶舱改为并行请求，并发上限 8 | 仍为 40 次业务接口，耗时 2.9 秒降到约 0.3 秒 |
| 前端分包过大 | Element Plus 按需引入具体组件，避免主入口整包；大依赖拆成独立分包；图表仅在驾驶舱路由加载 | 最大 JS 分包由约 1 MB 降到 542 kB（ECharts，gzip 187 kB），Element Plus 951 kB 降到 300 kB（gzip 102 kB），构建无体积警告 |
| 模型重复查询 | 提示词要求组合工具返回后直接写报告，并对四类分析固定工具；组合工具结果附带收尾提示 | 单元测试覆盖；真实模型实测 5 项中的 4 项只调用 1–2 次工具，效率分析调用 5 次（四个场景加缺料），不再出现 7–12 次重复查询 |
| `dev.ps1` 接管道不返回 | 改经 `cmd /c start /b` 启动，子进程不再继承脚本输出句柄；进程号按监听端口记录 | `dev.ps1 | tail` 正常返回，四个服务健康检查通过 |
