# 停止 dev.ps1 启动的服务：先按 PID 文件结束进程树，再按端口兜底（只清理 python/node 进程）
$Root = Split-Path -Parent $PSScriptRoot
$PidFile = Join-Path $Root ".run\pids.json"

if (Test-Path $PidFile) {
    (Get-Content $PidFile -Raw | ConvertFrom-Json).PSObject.Properties | ForEach-Object {
        if (Get-Process -Id $_.Value -ErrorAction SilentlyContinue) {
            & taskkill.exe /PID $_.Value /T /F | Out-Null
            Write-Host "已停止 $($_.Name) (PID $($_.Value))"
        }
    }
    Remove-Item $PidFile
}

foreach ($port in 8000, 8001, 8002, 5173) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
            $proc = Get-Process -Id $_ -ErrorAction SilentlyContinue
            if ($proc -and $proc.ProcessName -in @("python", "node")) {
                & taskkill.exe /PID $_ /T /F | Out-Null
                Write-Host "已停止端口 $port 上的进程 $($proc.ProcessName) (PID $_)"
            } elseif ($proc) {
                Write-Warning "端口 $port 被 $($proc.ProcessName) (PID $_) 占用，非本项目进程，未处理"
            }
        }
}
Write-Host "完成"
