# Cold Run Protocol
# 1. Stop and Remove Containers
Write-Host "🧊 stopping containers..." -ForegroundColor Cyan
docker-compose down -v

# 2. Build from Scratch (No Cache)
Write-Host "🔨 Building fresh images..." -ForegroundColor Cyan
docker-compose build --no-cache

# 3. Start in Detached Mode
Write-Host "🚀 Launching The Exocortex..." -ForegroundColor Cyan
docker-compose up -d

# 4. Wait for Health Check
Write-Host "⏳ Waiting for services to stabilize (10s)..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# 5. Check Status
docker-compose ps

Write-Host "`n✅ Cold Run Complete." -ForegroundColor Green
Write-Host "   - Dashboard: http://localhost:8501" -ForegroundColor Green
Write-Host "   - GraphDB:   http://localhost:3000" -ForegroundColor Green
