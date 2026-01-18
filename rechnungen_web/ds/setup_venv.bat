@echo off
echo ========================================
echo  Datei-Organizer Setup für Windows
echo ========================================

REM Virtual Environment erstellen
echo 1. Erstelle virtuelle Umgebung...
python -m venv venv
if %ERRORLEVEL% NEQ 0 (
    echo FEHLER: Virtual Environment konnte nicht erstellt werden
    pause
    exit /b 1
)

REM Aktivieren
echo 2. Aktiviere virtuelle Umgebung...
call venv\Scripts\activate.bat
if %ERRORLEVEL% NEQ 0 (
    echo FEHLER: Virtual Environment konnte nicht aktiviert werden
    pause
    exit /b 1
)

REM Upgrade pip
echo 3. Upgrading pip...
python -m pip install --upgrade pip

REM Pakete installieren
echo 4. Installiere Abhängigkeiten...
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo FEHLER: Pakete konnten nicht installiert werden
    pause
    exit /b 1
)

echo.
echo ========================================
echo  ✅ Setup abgeschlossen!
echo ========================================
echo.
echo Nächste Schritte:
echo 1. Bearbeite config.json mit deinen Pfaden
echo 2. Starte mit: python main.py
echo 3. Oder für alle Features: python advanced_organizer.py
echo.
pause