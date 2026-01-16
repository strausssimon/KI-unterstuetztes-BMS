@echo off
REM Docker-Container stoppen

echo ===================================================
echo PostgreSQL und pgAdmin4 Container stoppen
echo ===================================================
echo.

cd /d "%~dp0"

echo Stoppe Container...
docker-compose stop

echo.
echo ✓ Container gestoppt!
echo.
echo Um die Container komplett zu entfernen (inkl. Daten):
echo   docker-compose down -v
echo.
echo Um die Container wieder zu starten:
echo   docker-compose up -d
echo.
pause
