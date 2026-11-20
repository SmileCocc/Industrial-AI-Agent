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
    # 包装脚本在分离的 cmd 中执行，需用 npm.cmd 的完整路径。
    web = @{ Port = 5173; Dir = (Join-Path $Root "frontend"); Exe = (Get-Command npm.cmd).Source; Args = "run dev -- --port 5173 --strictPort"; Health = "http://127.0.0.1:5173/"; Check = "package.json" }
}

$pids = @{}
if (Test-Path $PidFile) {
    (Get-Content $PidFile -Raw | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $pids[$_.Name] = $_.Value }
}

$started = @()
foreach ($name in $Services) {
    $d = $defs[$name]
    if (-not $d) { Write-Warning "未知服务 $name（可选：erp, mes, ai, web）"; continue }
    if (-not (Test-Path (Join-Path $d.Dir $d.Check))) { Write-Host "跳过 $name：尚未实现" -ForegroundColor DarkGray; continue }
    if (Get-NetTCPConnection -LocalPort $d.Port -State Listen -ErrorAction SilentlyContinue) {
        Write-Warning "端口 $($d.Port) 已被占用，跳过 $name（可先运行 stop.ps1）"; continue
    }
    # 经 cmd 的 start /b 启动包装脚本：子进程不继承本脚本的输出句柄（`dev.ps1 | ...` 才能结束），
    # 日志重定向放在包装脚本内，脱离命令行后仍写入文件。
    $wrapper = Join-Path $RunDir "$name.cmd"
    @(
        '@echo off',
        "cd /d `"$($d.Dir)`"",
        "`"$($d.Exe)`" $($d.Args) > `"$(Join-Path $LogDir "$name.out.log")`" 2> `"$(Join-Path $LogDir "$name.err.log")`"",
        # start 以 cmd /K 运行批处理，服务退出后需关闭该 shell，避免占用日志文件。
        'exit'
    ) | Set-Content $wrapper -Encoding ASCII
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c start `"`" /b `"$wrapper`"" -WindowStyle Hidden | Out-Null
    $started += $name
    Write-Host "启动 $name (端口 $($d.Port))"
}

# 轮询健康检查，最多 30 秒；启动方式拿不到子进程号，端口可用后按监听进程记录。
foreach ($name in $started) {
    $d = $defs[$name]
    $ok = $false
    for ($i = 0; $i -lt 30 -and -not $ok; $i++) {
        try { Invoke-WebRequest $d.Health -UseBasicParsing -TimeoutSec 2 | Out-Null; $ok = $true } catch { Start-Sleep -Seconds 1 }
    }
    $listener = Get-NetTCPConnection -LocalPort $d.Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listener) { $pids[$name] = $listener.OwningProcess }
    if ($ok) { Write-Host "  [OK]   $name  $($d.Health)" -ForegroundColor Green }
    else { Write-Host "  [FAIL] $name  查看日志 backend\logs\$name.err.log" -ForegroundColor Red }
}
$pids | ConvertTo-Json | Set-Content $PidFile -Encoding UTF8
