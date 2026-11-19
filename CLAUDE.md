# CLAUDE.md

制造业 AI Agent 项目。设计与决策见 docs/architecture.md，进展见 README.md。

## 规则

- 按阶段开发，每个阶段需用户确认后再进入下一阶段。
- 使用中文沟通；代码精简，关键业务逻辑写中文注释。
- 没有实际运行过的功能不能声称测试通过。
- 关键技术决策写入 docs/architecture.md 的决策记录，进展更新 README.md。
- ERP/MES 第一版只读。Agent 只能通过 HTTP 访问 ERP/MES，不连接其数据库、不执行任意 SQL。
- 禁止关键词匹配或硬编码答案冒充 Agent；只执行模型原生 tool_calls。
- 密钥只放 backend/.env（已 gitignore），不能出现在代码、日志和响应中。

## 结构与命令

- backend/：common（配置、数据库、日志、鉴权）、erp_service、mes_service、ai_service、seed（模拟数据）、tests
- 数据库：本机 MySQL 3306，库 industrial_erp / industrial_mes / industrial_agent；ERP、MES 各自使用独立的 DeclarativeBase
- Python：backend/.venv（Python 3.14）。在 backend 目录运行：
  - 重置数据：`.venv\Scripts\python -m seed`
  - 单独启动：`.venv\Scripts\python -m uvicorn erp_service.main:app --port 8001`
  - 测试（需服务已启动）：`.venv\Scripts\python -m pytest`
- 脚本：scripts/init.ps1、dev.ps1（`-Services erp,mes` 可选）、stop.ps1、reset-data.ps1
- Windows 控制台为 GBK，Python 输出中文需设 `PYTHONIOENCODING=utf-8`（脚本已设置）
