$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimeDir = Join-Path $projectRoot ".runtime"
$appPidFile = Join-Path $runtimeDir "backend.pid"

if (Test-Path $appPidFile) {
    $backendPid = Get-Content $appPidFile | Select-Object -First 1
    try {
        $proc = Get-Process -Id ([int]$backendPid) -ErrorAction Stop
        "Backend: RUNNING (PID=$($proc.Id))" | Write-Host
    } catch {
        "Backend: NOT RUNNING (stale PID file)." | Write-Host
    }
} else {
    "Backend: NOT RUNNING" | Write-Host
}

try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:5000/health" -Method Get -TimeoutSec 5
    "Health endpoint: $($health.status)" | Write-Host
} catch {
    "Health endpoint: unavailable" | Write-Host
}
