# Prerequisite checker for the native Windows 11 build (plan §3).
# Read-only: installs nothing, changes nothing.
# Run:  powershell -ExecutionPolicy Bypass -File scripts/check_prereqs.ps1
# Exit 0 = all green, 1 = something missing (see FAIL lines).
$ErrorActionPreference = "Continue"
$fail = 0

function Check($name, [bool]$ok, $detail, $fix = "") {
  if ($ok) { Write-Host "  PASS: $name ($detail)" }
  else { Write-Host "  FAIL: $name ($detail)"; if ($fix) { Write-Host "        fix: $fix" }; $script:fail = 1 }
}

function WithTimeout([scriptblock]$sb, [int]$secs) {
  $j = Start-Job -ScriptBlock $sb
  if (Wait-Job $j -Timeout $secs) { $r = Receive-Job $j; Remove-Job $j -Force; return $r }
  Remove-Job $j -Force; return $null
}

Write-Host "[os]"
$os = Get-CimInstance Win32_OperatingSystem
Check "Windows 11" ($os.Caption -match "Windows 11") $os.Caption "install Windows 11"
$ramGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
Check "RAM >= 8 GB" ($ramGB -ge 8) "$ramGB GB total" "close apps or add RAM (8B model needs room)"

Write-Host "[disk]"
$drive = (Get-Location).Drive.Name
$freeGB = [math]::Round((Get-PSDrive $drive).Free / 1GB, 1)
Check "disk free >= 12 GB on ${drive}:" ($freeGB -ge 12) "$freeGB GB free" "free space (models ~5.2 GB + deps)"

Write-Host "[python]"
$py = WithTimeout { python --version 2>&1 } 20
$pyOk = $py -match "Python 3\.(1[1-9]|[2-9][0-9])"
Check "Python 3.11+ on PATH" $pyOk "$py" "install from python.org with Add to PATH checked"
$venv = WithTimeout { python -c "import venv; print('ok')" 2>&1 } 20
Check "venv module" ($venv -eq "ok") "$venv" "reinstall Python with default options"

Write-Host "[node]"
$nd = WithTimeout { node --version 2>&1 } 20
$ndOk = $false
if ($nd -match "v(\d+)\.") { $ndOk = [int]$Matches[1] -ge 20 }
Check "Node.js 20+" $ndOk "$nd" "install Node 20 LTS"
$npm = WithTimeout { npm --version 2>&1 } 20
Check "npm" ($npm -match "^\d+\.") "$npm" "ships with Node"

Write-Host "[ollama]"
$ol = WithTimeout { ollama --version 2>&1 } 20
Check "ollama CLI" ($ol -match "ollama version") "$ol" "install Ollama for Windows, then ollama serve"
$models = WithTimeout { ollama list 2>&1 } 90
$llmOk = @($models | Where-Object { $_ -match "llama3\.1:8b-instruct-q4_K_M" }).Count -gt 0
$embOk = @($models | Where-Object { $_ -match "nomic-embed-text" }).Count -gt 0
Check "llm model" $llmOk "llama3.1:8b-instruct-q4_K_M" "ollama pull llama3.1:8b-instruct-q4_K_M"
Check "embed model" $embOk "nomic-embed-text" "ollama pull nomic-embed-text"

Write-Host ""
if ($fail -eq 0) { Write-Host "PREREQS ALL GREEN" } else { Write-Host "PREREQS INCOMPLETE - see FAIL lines above" }
exit $fail
