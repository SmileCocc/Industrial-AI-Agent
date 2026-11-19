# 一键重置模拟数据（以今天为基准日重新生成）。可选参数：all / erp / mes
param([ValidateSet("all", "erp", "mes")][string]$Target = "all")
$ErrorActionPreference = "Stop"
$Backend = Join-Path (Split-Path -Parent $PSScriptRoot) "backend"
$Py = Join-Path $Backend ".venv\Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"
if (-not (Test-Path $Py)) { throw "未找到 backend\.venv，请先运行 scripts\init.ps1" }

Push-Location $Backend
try { & $Py -m seed $Target; if ($LASTEXITCODE) { throw "重置失败" } } finally { Pop-Location }
Write-Host "模拟数据已重置" -ForegroundColor Green
