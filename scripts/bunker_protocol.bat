@echo off
setlocal

:: Bunker Protocol: Apocalypse-Proof Backup (Batch Version)
:: Usage: Double-click this file.

cls
echo ========================================================
echo [WARN] INITIATING BUNKER PROTOCOL
echo [INFO] Ensuring survival of The Exocortex...
echo ========================================================
echo.

set BUNKER_DIR=bunker
set DATE_STR=%date:~10,4%-%date:~4,2%-%date:~7,2%

:: 1. Create Bunker Directory
if not exist "%BUNKER_DIR%" mkdir "%BUNKER_DIR%"
if not exist "%BUNKER_DIR%\images" mkdir "%BUNKER_DIR%\images"
if not exist "%BUNKER_DIR%\data" mkdir "%BUNKER_DIR%\data"

:: 2. Stop Services
echo [1/5] Stopping Core Services...
docker-compose stop
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to stop services. Aborting.
    pause
    exit /b %ERRORLEVEL%
)

:: 3. Export Docker Images
echo [2/5] Exporting Docker Images (This takes time)...
echo      - Exporting Server...
docker save -o "%BUNKER_DIR%\images\server.tar" claude-memory-mcp-server
echo      - Exporting Dashboard...
docker save -o "%BUNKER_DIR%\images\dashboard.tar" claude-memory-mcp-dashboard
echo      - Exporting Database...
docker save -o "%BUNKER_DIR%\images\falkordb.tar" falkordb/falkordb:latest

:: 4. Export Data Volume
echo [3/5] Exporting Neural Graph Data...
:: Use alpine to tar the volume content to host
docker run --rm -v claude-memory-mcp_falkordb_data:/data -v "%CD%\%BUNKER_DIR%\data:/backup" alpine tar cvf /backup/falkordb_data.tar /data

:: 5. Generate Restoration Instructions
echo [4/5] Etching Restoration Tablets...
(
    echo # RESTORE PROTOCOL
    echo.
    echo ## In case of Apocalypse:
    echo 1. Install Docker.
    echo 2. Load Images:
    echo    docker load -i images/server.tar
    echo    docker load -i images/dashboard.tar
    echo    docker load -i images/falkordb.tar
    echo.
    echo 3. Restore Data:
    echo    docker volume create claude-memory-mcp_falkordb_data
    echo    docker run --rm -v claude-memory-mcp_falkordb_data:/data -v "%%PWD%%/data:/backup" alpine tar xvf /backup/falkordb_data.tar
    echo.
    echo 4. Launch:
    echo    docker-compose up -d
) > "%BUNKER_DIR%\RESTORE.md"

:: 6. Restart Services
echo [5/5] Resuming Normal Operations...
docker-compose start

echo.
echo ========================================================
echo [SUCCESS] BUNKER SEALED.
echo Artifact location: .\%BUNKER_DIR%
echo.
echo Copy this folder to a secure location immediately.
echo ========================================================
pause
