# Cold Test Protocol
# Ensures the CODEBASE is clean, typed, and logically sound from a fresh start.

$ErrorActionPreference = "Stop"

# 1. Clean Artifacts
Write-Host "🧹 Cleaning pycache and temp files..." -ForegroundColor Cyan
Get-ChildItem -Path . -Include __pycache__ -Recurse -ErrorAction SilentlyContinue | Remove-Item -Force -Recurse
Get-ChildItem -Path . -Include .pytest_cache -Recurse -ErrorAction SilentlyContinue | Remove-Item -Force -Recurse
Get-ChildItem -Path . -Include .mypy_cache -Recurse -ErrorAction SilentlyContinue | Remove-Item -Force -Recurse

# 2. Run Pre-commit (Static Analysis)
Write-Host "🛡️ Running Mercenary Checks (Pre-commit)..." -ForegroundColor Yellow
pre-commit run --all-files

# 3. Run Unit Tests
Write-Host "🧪 Running Unit Tests..." -ForegroundColor Yellow
pytest

# 4. Run Day-in-the-Life Simulation
Write-Host "🧬 Running Simulation..." -ForegroundColor Yellow
python scripts/simulate_day.py

Write-Host "`n✅ Cold Test Complete. All Systems Green." -ForegroundColor Green
