$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimeDir = Join-Path $projectRoot ".runtime"
$appPidFile = Join-Path $runtimeDir "backend.pid"

if (Test-Path $appPidFile) {
    $backendPid = Get-Content $appPidFile | Select-Object -First 1
    if ($backendPid) {
        try {
            Stop-Process -Id ([int]$backendPid) -Force -ErrorAction Stop
            "Stopped backend process PID=$backendPid." | Write-Host
        } catch {
            "Backend PID file existed but process could not be stopped." | Write-Host
        }
    }
    Remove-Item $appPidFile -Force
}

$existing = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object { $_.CommandLine -like "*$projectRoot*" -and $_.CommandLine -like "*run.py*" }
foreach ($proc in $existing) {
    try {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
        "Stopped backend process PID=$($proc.ProcessId)." | Write-Host
    } catch {
    }
}
