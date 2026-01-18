#!/bin/bash
echo "========================================"
echo " Datei-Organizer Setup für Mac/Linux"
echo "========================================"

# Virtual Environment erstellen
echo "1. Erstelle virtuelle Umgebung..."
python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "FEHLER: Virtual Environment konnte nicht erstellt werden"
    exit 1
fi

# Aktivieren
echo "2. Aktiviere virtuelle Umgebung..."
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "FEHLER: Virtual Environment konnte nicht aktiviert werden"
    exit 1
fi

# Upgrade pip
echo "3. Upgrading pip..."
pip install --upgrade pip

# Pakete installieren
echo "4. Installiere Abhängigkeiten..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "FEHLER: Pakete konnten nicht installiert werden"
    exit 1
fi

echo ""
echo "========================================"
echo " ✅ Setup abgeschlossen!"
echo "========================================"
echo ""
echo "Nächste Schritte:"
echo "1. Bearbeite config.json mit deinen Pfaden"
echo "2. Starte mit: python advanced_organizer.py"
echo ""
