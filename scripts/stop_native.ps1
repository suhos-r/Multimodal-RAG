# Stop everything run_native.ps1 started (API + UI + native qdrant).
# Run:  powershell -ExecutionPolicy Bypass -File scripts/stop_native.ps1
param([int]$ApiPort = 8000, [int]$UiPort = 3000)
$ErrorActionPreference = "Continue"
$ROOT = Split-Path -Parent $PSScriptRoot
$PIDFILE = Join-Path $ROOT ".native_pids"

if (Test-Path $PIDFILE) {
  foreach ($id in (Get-Content $PIDFILE -Raw).Split(",")) {
    $id = $id.Trim()
    if ($id -match '^\d+$') { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue; Write-Host "  stopped pid $id" }
  }
  Remove-Item $PIDFILE -Force -ErrorAction SilentlyContinue
}
foreach ($port in @($ApiPort, $UiPort)) {
  $pid = (netstat -ano | Select-String "0.0.0.0:$port" | Select-Object -First 1) -replace '.*\s(\d+)\s*$', '$1'
  if ($pid -match '^\d+$') { Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue; Write-Host "  freed port $port" }
}
Get-Process -Name qdrant -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host "stopped (volumes/data files untouched)"
