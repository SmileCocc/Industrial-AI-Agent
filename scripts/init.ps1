# 初始化开发环境：Python 虚拟环境、后端依赖、.env、前端依赖、模拟数据
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Venv = Join-Path $Backend ".venv"
$Py = Join-Path $Venv "Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"

function Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

Step "检查 Python"
$sysPy = Get-Command python -ErrorAction SilentlyContinue
if (-not $sysPy) { throw "未找到 python，请安装 Python 3.11+ 并加入 PATH" }
$ver = & python -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ([version]$ver -lt [version]"3.11") { throw "Python 版本为 $ver，需要 3.11+" }
Write-Host "    Python $ver"

if (-not (Test-Path $Py)) {
    Step "创建虚拟环境 backend\.venv"
    & python -m venv $Venv
}

Step "安装后端依赖"
& $Py -m pip install -q --upgrade pip
Push-Location $Backend
try { & $Py -m pip install -q -e ".[dev]"; if ($LASTEXITCODE) { throw "依赖安装失败" } } finally { Pop-Location }

$EnvFile = Join-Path $Backend ".env"
if (-not (Test-Path $EnvFile)) {
    Step "创建 backend\.env（请填写 MYSQL_PASSWORD 与模型配置）"
    Copy-Item (Join-Path $Backend ".env.example") $EnvFile
}

$Frontend = Join-Path $Root "frontend"
if (Test-Path (Join-Path $Frontend "package.json")) {
    Step "安装前端依赖"
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "未找到 npm，请安装 Node.js 18+" }
    Push-Location $Frontend
    try { & npm.cmd install; if ($LASTEXITCODE) { throw "npm install 失败" } } finally { Pop-Location }
} else {
    Write-Host "    前端尚未创建，跳过 npm install"
}

Step "检查 MySQL 连接并生成模拟数据"
Push-Location $Backend
try {
    & $Py -c "from common.config import get_settings; from common.db import ensure_database; ensure_database(get_settings().erp_db_name)"
    if ($LASTEXITCODE) { throw "无法连接 MySQL，请检查 backend\.env 中的 MYSQL_* 配置以及 MySQL 服务是否启动" }
    & $Py -m seed
    if ($LASTEXITCODE) { throw "生成模拟数据失败" }
} finally { Pop-Location }

Write-Host "初始化完成。启动：powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1" -ForegroundColor Green
