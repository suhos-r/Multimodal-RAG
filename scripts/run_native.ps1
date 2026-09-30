# Native run script: backend (sqlite) + UI, optional native Qdrant. No Docker.
# Run:  powershell -ExecutionPolicy Bypass -File scripts/run_native.ps1
# Env knobs: $env:DATABASE_URL, $env:QDRANT_URL, -ApiPort, -UiPort, -SkipInstall.
param([int]$ApiPort = 8000, [int]$UiPort = 3000, [switch]$SkipInstall)
$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot
$PIDFILE = Join-Path $ROOT ".native_pids"

function Free-Port($port) {
  $pid = (netstat -ano | Select-String "0.0.0.0:$port" | Select-Object -First 1) -replace '.*\s(\d+)\s*$', '$1'
  if ($pid -match '^\d+$') { Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue; Write-Host "  freed port $port" }
}

Write-Host "[1/5] prerequisites"
& "$PSScriptRoot\check_prereqs.ps1"
if ($LASTEXITCODE -ne 0) { throw "prerequisites incomplete - fix FAIL lines above" }

Write-Host "[2/5] backend venv"
if (-not (Test-Path "$ROOT\.venv\Scripts\python.exe") -or -not $SkipInstall) {
  if (-not (Test-Path "$ROOT\.venv")) { python -m venv "$ROOT\.venv" }
  & "$ROOT\.venv\Scripts\pip" install -r "$ROOT\backend\requirements.txt"
  if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
} else { Write-Host "  reusing .venv (-SkipInstall borne out: interpreter present)" }

Write-Host "[3/5] database"
if (-not $env:DATABASE_URL) { $env:DATABASE_URL = "sqlite+aiosqlite:///./rag.db" }
Push-Location "$ROOT\backend"
& "$ROOT\.venv\Scripts\python" -m app.init_db
Pop-Location

Write-Host "[4/5] qdrant (optional - lexical fallback otherwise)"
$qdrantExe = Join-Path $ROOT "tools\qdrant\qdrant.exe"
if (-not $env:QDRANT_URL) { $env:QDRANT_URL = "http://localhost:6333" }
try { $q = Invoke-RestMethod "$($env:QDRANT_URL)/readyz" -TimeoutSec 5; Write-Host "  qdrant already up: $q" }
catch {
  if (Test-Path $qdrantExe) {
    Start-Process -FilePath $qdrantExe -WorkingDirectory (Split-Path $qdrantExe) -WindowStyle Hidden
    Write-Host "  started native qdrant"
  } else { Write-Host "  WARNING: no qdrant - dense retrieval falls back to lexical" }
}

Write-Host "[5/5] api + ui"
Free-Port $ApiPort
$apiEnv = @{ DATABASE_URL = $env:DATABASE_URL; QDRANT_URL = $env:QDRANT_URL }
if ($env:OLLAMA_BASE_URL) { $apiEnv["OLLAMA_BASE_URL"] = $env:OLLAMA_BASE_URL }
$api = Start-Process -FilePath "$ROOT\.venv\Scripts\python.exe" `
  -ArgumentList "-m uvicorn app.main:app --host 0.0.0.0 --port $ApiPort" `
  -WorkingDirectory "$ROOT\backend" -WindowStyle Hidden -PassThru
$ui = Start-Process -FilePath "cmd.exe" `
  -ArgumentList "/c npm run dev -- -p $UiPort > %TEMP%\nextdev.log 2>&1" `
  -WorkingDirectory "$ROOT\frontend" -WindowStyle Hidden -PassThru
"$($api.Id),$($ui.Id)" | Out-File $PIDFILE -Encoding ascii

Write-Host "waiting for api..."
for ($i = 0; $i -lt 30; $i++) {
  try {
    $h = Invoke-RestMethod "http://localhost:$ApiPort/health" -TimeoutSec 5
    if ($h.deps.db -eq "ok") { Write-Host "  api ok (db=$($h.deps.db) qdrant=$($h.deps.qdrant) redis=$($h.deps.redis))" ; break }
  } catch { Start-Sleep -Seconds 2 }
}
Write-Host ""
Write-Host "UI:  http://localhost:$UiPort/login"
Write-Host "API: http://localhost:$ApiPort/docs  (stop: scripts/stop_native.ps1)"
