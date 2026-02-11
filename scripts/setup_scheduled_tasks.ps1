# setup_scheduled_tasks.ps1 — One-time setup for Exocortex scheduled tasks.
# Must be run as Administrator.
#
# Creates two Windows Task Scheduler jobs:
#   1. ExocortexBackup      — daily at 3:00 AM (runs scheduled_backup.py)
#   2. ExocortexHealthCheck  — every 15 minutes (runs healthcheck.ps1)

param(
    [switch]$Force  # Re-create tasks even if they already exist
)

$ErrorActionPreference = "Stop"

# Resolve paths relative to this script's location
$ScriptDir  = $PSScriptRoot
$ProjectDir = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$PythonExe  = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) { $PythonExe = "python" }

Write-Host "=== Exocortex Scheduled Tasks Setup ===" -ForegroundColor Cyan
Write-Host "Project: $ProjectDir"
Write-Host "Python:  $PythonExe"
Write-Host ""

# ── Helper ────────────────────────────────────────────────────────────────────

function Register-ExocortexTask {
    param(
        [string]$TaskName,
        [string]$Description,
        [string]$Command,
        [string]$Arguments,
        [string]$TriggerSpec  # "daily_3am" or "every_15min"
    )

    $existing = schtasks /query /tn $TaskName 2>$null
    if ($existing -and -not $Force) {
        Write-Host "[SKIP] $TaskName already exists. Use -Force to recreate." -ForegroundColor Yellow
        return
    }

    if ($existing -and $Force) {
        Write-Host "[DEL]  Removing existing: $TaskName" -ForegroundColor Yellow
        schtasks /delete /tn $TaskName /f | Out-Null
    }

    if ($TriggerSpec -eq "daily_3am") {
        schtasks /create `
            /tn $TaskName `
            /tr "$Command $Arguments" `
            /sc DAILY `
            /st 03:00 `
            /rl HIGHEST `
            /f
    } elseif ($TriggerSpec -eq "every_15min") {
        schtasks /create `
            /tn $TaskName `
            /tr "$Command $Arguments" `
            /sc MINUTE `
            /mo 15 `
            /rl HIGHEST `
            /f
    }

    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK]   $TaskName registered." -ForegroundColor Green
    } else {
        Write-Host "[FAIL] $TaskName registration failed." -ForegroundColor Red
    }
}

# ── Task 1: Daily Backup (W4) ────────────────────────────────────────────────

Register-ExocortexTask `
    -TaskName "ExocortexBackup" `
    -Description "Daily backup of Exocortex brain data (FalkorDB + Qdrant)" `
    -Command $PythonExe `
    -Arguments "$ScriptDir\scheduled_backup.py" `
    -TriggerSpec "daily_3am"

# ── Task 2: Health Check every 15 min (W5) ───────────────────────────────────

Register-ExocortexTask `
    -TaskName "ExocortexHealthCheck" `
    -Description "Periodic health check with toast notifications on failure" `
    -Command "powershell.exe" `
    -Arguments "-ExecutionPolicy Bypass -File `"$ScriptDir\healthcheck.ps1`"" `
    -TriggerSpec "every_15min"

# ── Verification ──────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "=== Verifying ===" -ForegroundColor Cyan

foreach ($tn in @("ExocortexBackup", "ExocortexHealthCheck")) {
    $check = schtasks /query /tn $tn 2>$null
    if ($check) {
        Write-Host "[OK]   $tn is registered." -ForegroundColor Green
    } else {
        Write-Host "[FAIL] $tn is NOT registered." -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Done. Run 'schtasks /query /tn ExocortexBackup' to verify." -ForegroundColor Cyan
