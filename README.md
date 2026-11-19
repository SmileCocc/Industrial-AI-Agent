# Industrial AI Agent

制造业企业 AI 智能助手：AI Agent 通过 HTTP 对接模拟 ERP、MES 两个独立业务系统，完成跨系统数据查询、生产分析、缺料诊断和业务问答。

- 架构设计：[docs/architecture.md](docs/architecture.md)
- 接口文档：[docs/api.md](docs/api.md)

## 项目进展

| 阶段 | 内容 | 状态 |
|---|---|---|
| 1 | 架构设计 | 已完成（2026-11-18 确认，数据库改为 MySQL） |
| 2 | ERP/MES 模拟服务 | 已完成，20 项接口测试通过 |
| 3 | AI Agent（模型接入、工具调用、缺料分析） | 未开始 |
| 4 | 其余四个业务场景 | 未开始 |
| 5 | 前端页面 | 未开始 |
| 6 | 联调与验收 | 未开始 |

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
