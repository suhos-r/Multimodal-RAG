# Demo acceptance script (Windows/PowerShell 5.1+). 7 gates, fail-fast.
# Needs: API at $Api (uvicorn or compose), Postgres reachable. Ollama optional
# (mock answers still exercise citations/cache/agent paths? No — demo uses REAL stack).
# Run:  powershell -ExecutionPolicy Bypass -File scripts/demo.ps1 [-Api http://localhost:8000]
param([string]$Api = "http://localhost:8000")
$ErrorActionPreference = "Stop"

function JPost($path, $body, $tok) {
  $h = @{ "Content-Type" = "application/json" }
  if ($tok) { $h["Authorization"] = "Bearer $tok" }
  Invoke-RestMethod -Uri "$Api$path" -Method Post -Headers $h -Body ($body | ConvertTo-Json -Depth 6)
}
function JGet($path, $tok) {
  Invoke-RestMethod -Uri "$Api$path" -Method Get -Headers @{ Authorization = "Bearer $tok" }
}
function Assert($cond, $msg) { if (-not $cond) { throw "DEMO FAIL: $msg" }; Write-Host "  ok: $msg" }
function SseDone($sessionId, $query, $tok, $extra) {
  $b = @{ session_id = $sessionId; query = $query } + $extra
  $raw = Invoke-WebRequest -Uri "$Api/api/chat" -Method Post `
    -Headers @{ Authorization = "Bearer $tok"; "Content-Type" = "application/json" } `
    -Body ($b | ConvertTo-Json -Depth 6) -UseBasicParsing
  $line = ($raw.Content -split "`n" | Where-Object { $_ -match '"done"' } | Select-Object -Last 1) -replace '^data:\s*', ''
  return ($line | ConvertFrom-Json).done
}

Write-Host "[0] health"
$h = Invoke-RestMethod "$Api/health"
Assert ($h.ok -eq $true) "api healthy ($($h.deps.db)/$($h.deps.qdrant)/$($h.deps.redis))"

Write-Host "[1] signup + session"
$ts = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$tokA = (JPost "/api/auth/signup" @{ email = "demo$ts@x.com"; password = "demopass12" } $null).access_token
$tokB = (JPost "/api/auth/signup" @{ email = "demo2$ts@x.com"; password = "demopass12" } $null).access_token
$sid = (JPost "/api/sessions" @{} $tokA).id
Assert ($sid) "session created"

Write-Host "[2] upload 3 types -> ready"
$pngB64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
[IO.File]::WriteAllBytes("$env:TEMP\demo_px.png", [Convert]::FromBase64String($pngB64))
$files = @("seed_kb\rag_guide.txt", "seed_kb\q3_table.csv", "$env:TEMP\demo_px.png")
$docIds = @()
foreach ($f in $files) {
  $full = if ([IO.Path]::IsPathRooted($f)) { $f } else { Join-Path (Get-Location) $f }
  Add-Type -AssemblyName System.Net.Http
  $hc = New-Object System.Net.Http.HttpClient
  $mp = New-Object System.Net.Http.MultipartFormDataContent
  $fs = [IO.File]::OpenRead($full)
  $sc = New-Object System.Net.Http.StreamContent($fs)
  $mp.Add($sc, "file", [IO.Path]::GetFileName($full))
  $mp.Add((New-Object System.Net.Http.StringContent("private")), "scope")
  $req = New-Object System.Net.Http.HttpRequestMessage([Net.Http.HttpMethod]::Post, "$Api/api/documents/upload")
  $req.Headers.Authorization = New-Object System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", $tokA)
  $req.Content = $mp
  $resp = $hc.SendAsync($req).Result
  $fs.Close(); $hc.Dispose()
  Assert ($resp.IsSuccessStatusCode) "upload $(Split-Path $f -Leaf)"
  $docId = ($resp.Content.ReadAsStringAsync().Result | ConvertFrom-Json).doc_id
  $docIds += $docId
  JPost "/api/documents/$docId/process" @{} $tokA | Out-Null
  $st = $null
  for ($i = 0; $i -lt 30; $i++) {
    $st = JGet "/api/documents/$docId/status" $tokA
    if ($st.status -in @("ready", "failed")) { break }
    Start-Sleep -Seconds 2
  }
  Assert ($st.status -eq "ready") "$([IO.Path]::GetFileName($f)) ready"
}

Write-Host "[3] cited answer"
$done = SseDone $sid "How long are digital goods refundable under Meridian?" $tokA @{}
Assert ($done.citations.Count -ge 1) "citations >= 1 (got $($done.citations.Count))"
Assert ($done.answer -match "\[1\]") "answer carries [1]"

Write-Host "[4] repeat -> cached, no LLM"
$done2 = SseDone $sid "How long are digital goods refundable under Meridian?" $tokA @{}
Assert ($done2.cached -eq $true) "second ask cached:true"

Write-Host "[5] agent abstains with trace"
$done3 = SseDone $sid "What is the Mars office address?" $tokA @{ mode = "agent" }
Assert ($done3.answer -eq "I don't know based on the knowledge base.") "agent abstains"
Assert ($done3.trace_steps -ge 2) "trace non-empty ($($done3.trace_steps) steps)"

Write-Host "[6] feedback moves helpfulness"
$msgs = JGet "/api/sessions/$sid/messages?limit=200" $tokA
$mid = ($msgs | Where-Object { $_.role -eq "assistant" } | Select-Object -First 1).id
JPost "/api/feedback" @{ message_id = $mid; rating = -1; comment = "demo check" } $tokA | Out-Null
$stats = JGet "/api/admin/stats" $tokA
Assert ($stats.feedback_down -ge 1) "downvote counted"

Write-Host "[7] second user isolated"
$mine = JGet "/api/sessions" $tokB
Assert ($mine.Count -eq 0) "user B sees empty list"
try {
  SseDone $sid "hi" $tokB @{} | Out-Null
  throw "DEMO FAIL: B reached A's session"
} catch {
  if ($_ -match "DEMO FAIL") { throw $_ }
  Write-Host "  ok: B blocked from A session"
}

Write-Host "`nDEMO 7/7 GREEN"
