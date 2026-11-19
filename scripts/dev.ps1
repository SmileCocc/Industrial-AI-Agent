# 启动服务。默认启动全部；也可单独启动，例如：dev.ps1 -Services erp,mes
param([string[]]$Services = @("erp", "mes", "ai", "web"))
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Py = Join-Path $Backend ".venv\Scripts\python.exe"
$LogDir = Join-Path $Backend "logs"
$RunDir = Join-Path $Root ".run"
$PidFile = Join-Path $RunDir "pids.json"
New-Item -ItemType Directory -Force $LogDir, $RunDir | Out-Null
$env:PYTHONIOENCODING = "utf-8"

if (-not (Test-Path $Py)) { throw "未找到 backend\.venv，请先运行 scripts\init.ps1" }

# 服务定义：名称、端口、工作目录、可执行文件、参数、健康检查地址、存在性检查文件
$defs = @{
    erp = @{ Port = 8001; Dir = $Backend; Exe = $Py; Args = "-m uvicorn erp_service.main:app --host 127.0.0.1 --port 8001"; Health = "http://127.0.0.1:8001/health"; Check = "erp_service\main.py" }
    mes = @{ Port = 8002; Dir = $Backend; Exe = $Py; Args = "-m uvicorn mes_service.main:app --host 127.0.0.1 --port 8002"; Health = "http://127.0.0.1:8002/health"; Check = "mes_service\main.py" }
    ai  = @{ Port = 8000; Dir = $Backend; Exe = $Py; Args = "-m uvicorn ai_service.main:app --host 127.0.0.1 --port 8000"; Health = "http://127.0.0.1:8000/health"; Check = "ai_service\main.py" }
    web = @{ Port = 5173; Dir = (Join-Path $Root "frontend"); Exe = "npm.cmd"; Args = "run dev -- --port 5173 --strictPort"; Health = "http://127.0.0.1:5173/"; Check = "package.json" }
}

$pids = @{}
if (Test-Path $PidFile) {
    (Get-Content $PidFile -Raw | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $pids[$_.Name] = $_.Value }
}

foreach ($name in $Services) {
    $d = $defs[$name]
    if (-not $d) { Write-Warning "未知服务 $name（可选：erp, mes, ai, web）"; continue }
    if (-not (Test-Path (Join-Path $d.Dir $d.Check))) { Write-Host "跳过 $name：尚未实现" -ForegroundColor DarkGray; continue }
    if (Get-NetTCPConnection -LocalPort $d.Port -State Listen -ErrorAction SilentlyContinue) {
        Write-Warning "端口 $($d.Port) 已被占用，跳过 $name（可先运行 stop.ps1）"; continue
    }
    $p = Start-Process -FilePath $d.Exe -ArgumentList $d.Args -WorkingDirectory $d.Dir -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $LogDir "$name.out.log") -RedirectStandardError (Join-Path $LogDir "$name.err.log")
    $pids[$name] = $p.Id
    Write-Host "启动 $name (PID $($p.Id), 端口 $($d.Port))"
}
$pids | ConvertTo-Json | Set-Content $PidFile -Encoding UTF8

# 轮询健康检查，最多 30 秒
foreach ($name in $Services) {
    $d = $defs[$name]
    if (-not $d -or -not $pids.ContainsKey($name)) { continue }
    $ok = $false
    for ($i = 0; $i -lt 30 -and -not $ok; $i++) {
        try { Invoke-WebRequest $d.Health -UseBasicParsing -TimeoutSec 2 | Out-Null; $ok = $true } catch { Start-Sleep -Seconds 1 }
    }
    if ($ok) { Write-Host "  [OK]   $name  $($d.Health)" -ForegroundColor Green }
    else { Write-Host "  [FAIL] $name  查看日志 backend\logs\$name.err.log" -ForegroundColor Red }
}
