@echo off
REM Docker-Container für PostgreSQL mit pgvector und pgAdmin4 starten

echo ===================================================
echo PostgreSQL mit pgvector und pgAdmin4 starten
echo ===================================================
echo.

REM Prüfe ob Docker läuft
docker version >nul 2>&1
if errorlevel 1 (
    echo FEHLER: Docker ist nicht gestartet!
    echo Bitte starten Sie Docker Desktop und versuchen Sie es erneut.
    pause
    exit /b 1
)

echo Docker ist bereit...
echo.

REM Zum Projektverzeichnis wechseln
cd /d "%~dp0"

echo Starte Container...
docker-compose up -d

if errorlevel 1 (
    echo.
    echo FEHLER beim Starten der Container!
    pause
    exit /b 1
)

echo.
echo ===================================================
echo ✓ Container erfolgreich gestartet!
echo ===================================================
echo.
echo PostgreSQL mit pgvector:
echo   Host: localhost
echo   Port: 5432
echo   User: postgres
echo   Password: bigdataconsulting
echo   Database: postgres
echo.
echo pgAdmin4:
echo   URL: http://localhost:5050
echo   Email: admin@admin.com
echo   Password: admin
echo.
echo Nützliche Befehle:
echo   docker-compose logs -f          - Logs anzeigen
echo   docker-compose stop             - Container stoppen
echo   docker-compose down             - Container stoppen und entfernen
echo   docker-compose restart          - Container neu starten
echo.
echo Warten auf Container-Initialisierung (15 Sekunden)...
timeout /t 15 /nobreak >nul

echo.
echo Teste PostgreSQL-Verbindung...
docker exec postgres_pgvector psql -U postgres -c "SELECT version();" >nul 2>&1
if errorlevel 1 (
    echo PostgreSQL startet noch... Bitte warten Sie einen Moment.
) else (
    echo ✓ PostgreSQL ist bereit!
    docker exec postgres_pgvector psql -U postgres -c "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
)

echo.
echo Sie können jetzt:
echo   1. pgAdmin4 öffnen: http://localhost:5050
echo   2. Python-Scripts ausführen: python "src\db communication\test_pgvector.py"
echo.
pause
