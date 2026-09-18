# Nightly backup: Postgres dump + Qdrant snapshot list. 7-day retention.
# Run:  powershell -ExecutionPolicy Bypass -File scripts/backup.ps1
param([string]$OutDir = "backups")
$ErrorActionPreference = "Stop"
$day = Get-Date -Format "yyyyMMdd"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
Write-Host "pg_dump..."
docker compose exec -T postgres pg_dump -U rag -d rag > "$OutDir\pg_$day.sql"
Write-Host "qdrant snapshots..."
$snaps = Invoke-RestMethod -Uri "http://localhost:6333/collections" -Method Get
$snaps.result.collections | ForEach-Object {
  Invoke-RestMethod -Uri "http://localhost:6333/collections/$($_.name)/snapshots" -Method Post | Out-Null
  Write-Host "  snapshot: $($_.name)"
}
Get-ChildItem $OutDir | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } | Remove-Item
Write-Host "backup done -> $OutDir (see ops/restore_log.md for restore drill)"
