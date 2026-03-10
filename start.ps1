$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimeDir = Join-Path $projectRoot ".runtime"
$pythonExe = Join-Path $projectRoot ".venv\\Scripts\\python.exe"

if (-not (Test-Path $runtimeDir)) {
    New-Item -ItemType Directory -Path $runtimeDir | Out-Null
}

if (Test-Path $pythonExe) {
    $python = $pythonExe
} else {
    $python = "python"
}

$existing = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object { $_.CommandLine -like "*$projectRoot*" -and $_.CommandLine -like "*run.py*" }
if (-not $existing) {
    Start-Process -FilePath $python -ArgumentList "run.py" -WorkingDirectory $projectRoot -RedirectStandardOutput (Join-Path $runtimeDir "backend.log") -RedirectStandardError (Join-Path $runtimeDir "backend.err.log") | Out-Null
    Start-Sleep -Seconds 2
}

$listenerPid = (Get-NetTCPConnection -LocalPort 5000 -State Listen | Select-Object -First 1 -ExpandProperty OwningProcess)
if ($listenerPid) {
    Set-Content -Path (Join-Path $runtimeDir "backend.pid") -Value $listenerPid
    "Backend started on http://127.0.0.1:5000 (PID=$listenerPid)." | Write-Host
} else {
    "Backend launch attempted, but port 5000 is not listening yet." | Write-Host
}
