# Safe Start Protocol
# Resumes the system while PRESERVING your data.

Write-Host "Resuming The Exocortex..." -ForegroundColor Green

# Start containers (Builds only if necessary, preserves volumes)
docker-compose up -d

# Wait a moment
Start-Sleep -Seconds 5

# Status
docker-compose ps

Write-Host ""
Write-Host "System is Online." -ForegroundColor Green
Write-Host "   - Data:      PRESERVED (Volume kept)" -ForegroundColor Green
Write-Host "   - Dashboard: http://localhost:8501" -ForegroundColor Green
Write-Host "   - GraphDB:   http://localhost:3000" -ForegroundColor Green
