# healthcheck.ps1 — Quick system health probe for Exocortex stack.
# Checks: FalkorDB ping, Qdrant health, Embedding server /health.
# Exit 0 = all OK, Exit 1 = at least one service down.

param(
    [string]$FalkorHost = "localhost",
    [int]$FalkorPort = 6379,
    [string]$QdrantUrl = "http://localhost:6333",
    [string]$EmbeddingUrl = "http://localhost:8001"
)

$failed = @()

# 1. FalkorDB (Redis PING)
Write-Host "[CHECK] FalkorDB at ${FalkorHost}:${FalkorPort}..." -NoNewline
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.Connect($FalkorHost, $FalkorPort)
    $tcp.Close()
    Write-Host " OK" -ForegroundColor Green
} catch {
    Write-Host " FAIL" -ForegroundColor Red
    $failed += "FalkorDB"
}

# 2. Qdrant health endpoint
Write-Host "[CHECK] Qdrant at ${QdrantUrl}/healthz..." -NoNewline
try {
    $resp = Invoke-WebRequest -Uri "${QdrantUrl}/healthz" `
        -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
    if ($resp.StatusCode -eq 200) {
        Write-Host " OK" -ForegroundColor Green
    } else {
        Write-Host " FAIL ($($resp.StatusCode))" -ForegroundColor Red
        $failed += "Qdrant"
    }
} catch {
    Write-Host " FAIL" -ForegroundColor Red
    $failed += "Qdrant"
}

# 3. Embedding server
Write-Host "[CHECK] Embedding at ${EmbeddingUrl}/health..." -NoNewline
try {
    $resp = Invoke-WebRequest -Uri "${EmbeddingUrl}/health" `
        -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
    if ($resp.StatusCode -eq 200) {
        Write-Host " OK" -ForegroundColor Green
    } else {
        Write-Host " FAIL ($($resp.StatusCode))" -ForegroundColor Red
        $failed += "Embedding"
    }
} catch {
    Write-Host " FAIL" -ForegroundColor Red
    $failed += "Embedding"
}

# 4. Backup status (last_run_status.json)
$statusFile = Join-Path $PSScriptRoot "..\backups\last_run_status.json"
Write-Host "[CHECK] Backup status file..." -NoNewline
if (Test-Path $statusFile) {
    try {
        $statusJson = Get-Content $statusFile -Raw | ConvertFrom-Json
        $lastRun = [datetime]::Parse($statusJson.timestamp)
        $age = (Get-Date) - $lastRun
        if ($statusJson.status -ne "OK") {
            Write-Host " DEGRADED ($($statusJson.status))" -ForegroundColor Yellow
            $failed += "Backup($($statusJson.status))"
        } elseif ($age.TotalHours -gt 36) {
            Write-Host " STALE ($([math]::Round($age.TotalHours,1))h old)" -ForegroundColor Yellow
            $failed += "Backup(stale)"
        } else {
            Write-Host " OK ($($statusJson.backup_tag))" -ForegroundColor Green
        }
    } catch {
        Write-Host " PARSE ERROR" -ForegroundColor Red
        $failed += "Backup(parse_error)"
    }
} else {
    Write-Host " MISSING (no status file)" -ForegroundColor Yellow
    $failed += "Backup(no_status_file)"
}
# 5. MCP server process check (R-6)
Write-Host "[CHECK] MCP server process..." -NoNewline
$mcpProc = Get-Process -Name "python" -ErrorAction SilentlyContinue |
    Where-Object {
        try { $_.CommandLine -match "claude_memory\.server" } catch { $false }
    }
if ($mcpProc) {
    Write-Host " OK (PID: $($mcpProc.Id -join ', '))" -ForegroundColor Green
} else {
    Write-Host " NOT RUNNING" -ForegroundColor Red
    $failed += "MCP_Server(not_running)"
}

# Summary
Write-Host ""
if ($failed.Count -eq 0) {
    Write-Host "[RESULT] All services healthy." -ForegroundColor Green
    exit 0
} else {
    $list = $failed -join ", "
    Write-Host "[RESULT] FAILING: $list" -ForegroundColor Red

    # R-3: Telegram alerting (enabled by env vars)
    $telegramToken = $env:EXOCORTEX_TELEGRAM_TOKEN
    $telegramChatId = $env:EXOCORTEX_TELEGRAM_CHAT_ID
    if ($telegramToken -and $telegramChatId) {
        try {
            $msg = "[Exocortex Health Alert] FAILING: $list"
            $uri = "https://api.telegram.org/bot${telegramToken}/sendMessage"
            Invoke-RestMethod -Uri $uri -Method Post -Body @{
                chat_id = $telegramChatId
                text    = $msg
            } | Out-Null
            Write-Host "[ALERT] Telegram notification sent." -ForegroundColor Cyan
        } catch {
            Write-Host "[ALERT] Telegram send failed: $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }

    # Toast notification (Windows 10+)
    try {
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
            [Windows.UI.Notifications.ToastTemplateType]::ToastText02
        )
        $text = $template.GetElementsByTagName("text")
        $text[0].AppendChild($template.CreateTextNode("Exocortex Health Alert")) | Out-Null
        $text[1].AppendChild($template.CreateTextNode("FAILING: $list")) | Out-Null
        $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Exocortex")
        $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
        $notifier.Show($toast)
    } catch {
        # Toast not available -- already printed to console
    }
    exit 1
}
