@echo off
REM Installationsskript für pgvector
REM Dieses Skript muss in "x64 Native Tools Command Prompt for VS" als Administrator ausgeführt werden

echo ===================================================
echo pgvector Installation für PostgreSQL 18
echo ===================================================
echo.
echo WICHTIG: Führen Sie dieses Skript in der
echo "x64 Native Tools Command Prompt for VS" als Administrator aus!
echo.
echo Drücken Sie eine Taste zum Fortfahren...
pause >nul

REM PostgreSQL 18 Root-Verzeichnis setzen
set "PGROOT=C:\Program Files\PostgreSQL\18"

echo.
echo 1. PostgreSQL-Version prüfen...
"%PGROOT%\bin\pg_config.exe" --version
if errorlevel 1 (
    echo FEHLER: PostgreSQL nicht gefunden in %PGROOT%
    echo Bitte prüfen Sie den Pfad!
    pause
    exit /b 1
)

echo.
echo 2. Zum pgvector-Verzeichnis wechseln...
cd /d "%~dp0pgvector"
if errorlevel 1 (
    echo FEHLER: pgvector-Verzeichnis nicht gefunden!
    pause
    exit /b 1
)

echo.
echo 3. Alte Builds bereinigen...
nmake /F Makefile.win clean

echo.
echo 4. pgvector kompilieren...
nmake /F Makefile.win
if errorlevel 1 (
    echo.
    echo FEHLER beim Kompilieren!
    echo.
    echo Mögliche Ursachen:
    echo - Nicht in "x64 Native Tools Command Prompt" ausgeführt
    echo - C++ Build Tools nicht installiert
    echo - PostgreSQL-Entwicklungsdateien fehlen
    echo.
    pause
    exit /b 1
)

echo.
echo 5. pgvector installieren...
nmake /F Makefile.win install
if errorlevel 1 (
    echo.
    echo FEHLER bei der Installation!
    echo Führen Sie das Skript als Administrator aus!
    echo.
    pause
    exit /b 1
)

echo.
echo ===================================================
echo ✓ pgvector erfolgreich installiert!
echo ===================================================
echo.
echo Nächste Schritte:
echo 1. Öffnen Sie PowerShell
echo 2. Führen Sie aus:
echo    python "src\db communication\test_pgvector.py"
echo.
echo Das Skript wird pgvector automatisch aktivieren und testen.
echo.
pause
