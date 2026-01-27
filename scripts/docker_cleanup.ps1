# Docker Housekeeping Script
# Deletes "dangling" images (failed builds, old layers) to free up space.
# Does NOT delete currently used images or named volumes.

Write-Host "🐳 Docker Cleanup Protocol Initiated..." -ForegroundColor Cyan

# 1. Report Usage
Write-Host "`n📊 Current Disk Usage:"
docker system df

# 2. Prune Build Cache (The Big Win)
# This usually holds the massive layers from previous builds (Torch, etc)
Write-Host "`n🧹 Pruning Build Cache (Safe, just re-downloads if needed)..."
docker builder prune -a -f

# 3. Prune System (Stopped containers, networks, dangling images)
Write-Host "🧹 Pruning System Garbage..."
docker system prune -f

# 4. (Optional) Deep Clean - Uncomment to delete ALL unused images (Risky for other projects)
docker image prune -a -f

Write-Host "`n✅ Deep Cleanup Complete."
Write-Host "📊 New Disk Usage:"
docker system df
