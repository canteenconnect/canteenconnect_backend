$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

if (-not (Test-Path ".venv\\Scripts\\python.exe")) {
    throw "Virtual environment is missing. Create it with: python -m venv .venv"
}

powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $projectRoot "start.ps1")

try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:5000/health" -Method Get -TimeoutSec 10
    "Deployment successful. Health: $($health.status)" | Write-Host
} catch {
    "Deployment started but health check failed on http://127.0.0.1:5000/health" | Write-Host
    exit 1
}
