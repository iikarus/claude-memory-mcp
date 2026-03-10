# setup_scheduled_tasks.ps1 — One-time setup for Exocortex scheduled tasks.
# Must be run as Administrator.
#
# Creates two Windows Task Scheduler jobs:
#   1. ExocortexBackup      — daily at 11:00 PM (runs scheduled_backup.py)
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
        [string]$WorkDir,
        [string]$TriggerSpec  # "daily_11pm" or "every_15min"
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

    # Build the action: wrap command and arguments in quotes for paths with spaces
    $action = New-ScheduledTaskAction `
        -Execute "`"$Command`"" `
        -Argument "`"$Arguments`"" `
        -WorkingDirectory "`"$WorkDir`""

    if ($TriggerSpec -eq "daily_11pm") {
        $trigger = New-ScheduledTaskTrigger -Daily -At "11:00 PM"
    } elseif ($TriggerSpec -eq "every_15min") {
        $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
            -RepetitionInterval (New-TimeSpan -Minutes 15) `
            -RepetitionDuration (New-TimeSpan -Days 365)
    }

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RunOnlyIfNetworkAvailable:$false

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Description $Description `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -RunLevel Highest `
        -Force:$Force

    if ($?) {
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
    -WorkDir $ProjectDir `
    -TriggerSpec "daily_11pm"

# ── Task 2: Health Check every 15 min (W5) ───────────────────────────────────

Register-ExocortexTask `
    -TaskName "ExocortexHealthCheck" `
    -Description "Periodic health check with toast notifications on failure" `
    -Command "powershell.exe" `
    -Arguments "-ExecutionPolicy Bypass -File `"$ScriptDir\healthcheck.ps1`"" `
    -WorkDir $ProjectDir `
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
