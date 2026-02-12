<#
.SYNOPSIS
    Auto-recovery wrapper for the Claude Memory MCP server.

.DESCRIPTION
    Runs the MCP server in a resilient loop, restarting on crash.
    Exits cleanly on Ctrl+C or after MAX_RESTARTS consecutive failures.

.NOTES
    Logs restart events to logs/mcp_server_restarts.log.
    Designed to be called from mcp_config.json instead of bare python.
#>

param(
    [int]$MaxRestarts = 5,
    [int]$CooldownSeconds = 3
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $ProjectRoot) { $ProjectRoot = Split-Path -Parent $PSScriptRoot }

# Resolve paths
$PythonExe = "C:\Users\Asus\AppData\Local\Programs\Python\Python312\python.exe"
$SrcPath = Join-Path $ProjectRoot "src"
$LogDir = Join-Path $ProjectRoot "logs"
$LogFile = Join-Path $LogDir "mcp_server_restarts.log"

# Ensure log directory exists
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

function Write-RestartLog {
    param([string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $Message"
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
    Write-Host $line
}

$consecutiveFailures = 0

Write-RestartLog "MCP server wrapper started (max_restarts=$MaxRestarts, cooldown=${CooldownSeconds}s)"

while ($consecutiveFailures -lt $MaxRestarts) {
    try {
        Write-RestartLog "Starting MCP server..."
        $env:PYTHONPATH = $SrcPath

        & $PythonExe -m claude_memory.server 2>&1

        $exitCode = $LASTEXITCODE
        if ($exitCode -eq 0) {
            Write-RestartLog "MCP server exited cleanly (code 0). Stopping wrapper."
            break
        }

        $consecutiveFailures++
        Write-RestartLog "MCP server crashed (exit code: $exitCode). Failure $consecutiveFailures/$MaxRestarts."

        if ($consecutiveFailures -lt $MaxRestarts) {
            Write-RestartLog "Restarting in ${CooldownSeconds}s..."
            Start-Sleep -Seconds $CooldownSeconds
        }
    }
    catch {
        $consecutiveFailures++
        Write-RestartLog "MCP server threw exception: $($_.Exception.Message). Failure $consecutiveFailures/$MaxRestarts."

        if ($consecutiveFailures -lt $MaxRestarts) {
            Start-Sleep -Seconds $CooldownSeconds
        }
    }
}

if ($consecutiveFailures -ge $MaxRestarts) {
    Write-RestartLog "FATAL: Max restarts ($MaxRestarts) reached. MCP server is DOWN."
    exit 1
}

exit 0
