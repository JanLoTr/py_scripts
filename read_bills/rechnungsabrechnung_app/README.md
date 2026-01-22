# 💰 Rechnungsabrechnung App

Eine intelligente Streamlit-App zur vereinfachten Rechnungsabrechnung mit Groq KI-Integration.

## Features

✨ **Intelligente OCR-Erkennung**
- Automatische Textextraktion aus PDF und Bildern
- Unterstützung für Deutsch und Englisch

🤖 **Groq KI-Integration**
- Intelligente Produktnamen-Korrektur (z.B. "Ap...El" → "Apfel")
- Automatische Aktions-Preis-Erkennung und Ignorierung
- Fehlertolerante Produkterkennung
- Markierung von nicht erkannten Produkten als "unerkenntlich"

📊 **Bearbeitbare Tabellen**
- Interaktive Datenbearbeitung
- Preise immer von der Rechnung übernommen
- Preis-Validierung

💾 **Verlaufsverwaltung**
- Speicherung verarbeiteter Rechnungen
- Übersicht aller Rechnungen

## Installation

### Voraussetzungen

- Python 3.8+
- Tesseract-OCR muss installiert sein

#### Tesseract installieren

**Windows:**
1. Lade den Installer herunter: https://github.com/UB-Mannheim/tesseract/wiki
2. Installiere mit Standard-Einstellungen
3. Pfad wird automatisch erkannt

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

### Setup

1. Clone das Repository oder lade die Dateien herunter

2. Erstelle ein virtuelles Environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Installiere Dependencies:
```bash
pip install -r requirements.txt
```

4. (Optional) Erstelle .env-Datei:
```bash
cp .env.example .env
# Füge deinen Groq API Key ein (oder nutze die Web-UI)
```

## Verwendung

### App starten

```bash
streamlit run app.py
```

Die App öffnet sich automatisch im Browser unter `http://localhost:8501`

### Workflow

1. **Seitenleiste**: Gib deinen Groq API Key ein (oder nutze Umgebungsvariable)

2. **Rechnung hochladen**: 
   - Klicke auf "Datei hochladen"
   - Wähle ein PDF oder Bild (PNG, JPG, JPEG, TIFF)
   - Die Vorschau wird angezeigt

3. **Verarbeiten**:
   - Klicke "Rechnung verarbeiten"
   - OCR extrahiert den Text
   - Groq KI analysiert und extrahiert Produkte
   - Die Tabelle wird angezeigt

4. **Überprüfung & Bearbeitung**:
   - Überprüfe die erkannten Produkte und Preise
   - Bearbeite bei Bedarf direkt in der Tabelle
   - Füge neue Zeilen hinzu oder lösche Fehler

5. **Speichern**:
   - Klicke "Speichern"
   - Die Rechnung wird im Verlauf gespeichert

6. **Verlauf anzeigen**:
   - Tab "Verlauf" zeigt alle gespeicherten Rechnungen
   - Übersicht über Gesamtbetrag und Produkte

## KI-Intelligenz

### Produktnamen-Korrektur

Die KI versucht intelligente Produktnamen-Ergänzung:

```
Eingabe: "Ap...el"
Ausgabe: "Apfel"

Eingabe: "M...lch"  
Ausgabe: "Milch"

Eingabe: "xyz???123"
Ausgabe: "unerkenntlich"
```

### Aktions-Preise

Aktionspreise werden automatisch erkannt und ignoriert:

```
Input:
  Apfel: 1,50€
  Aktion-Preis -0,50€
  
Output:
  Apfel: 1,00€
```

## Konfiguration

### Groq API Key

Es gibt zwei Möglichkeiten:

**Option 1: In der App eingeben**
- Starten Sie die App
- Geben Sie den Key in der Seitenleiste unter "Groq API Konfiguration" ein
- Der Key wird für die aktuelle Session verwendet

**Option 2: Umgebungsvariable**
- Erstellen Sie `.env` Datei oder setzen Sie Umgebungsvariable
- `GROQ_API_KEY=your_key_here`

## Troubleshooting

### "Tesseract nicht gefunden"
- Stelle sicher, dass Tesseract installiert ist
- Windows: Überprüfe den Installationspfad
- Linux/Mac: `which tesseract` sollte den Pfad zeigen

### "Invalid API Key"
- Überprüfe, dass der Key korrekt eingegeben ist
- Getestet mit Groq's "mixtral-8x7b-32768" Modell

### Schlechte OCR-Qualität
- Verwende hochauflösende Bilder
- Rechnungen sollten gut beleuchtet sein
- Probiere Graustufen-Konvertierung

## Struktur

```
rechnungsabrechnung_app/
├── app.py                      # Hauptanwendung
├── config.py                   # Konfiguration
├── requirements.txt            # Dependencies
├── utils/
│   ├── file_utils.py          # Dateioperationen
│   ├── ocr_utils.py           # OCR-Verarbeitung
│   ├── groq_utils.py          # KI-Integration (CORE)
│   └── text_processing.py     # Textbereinigung
└── data/
    ├── uploads/               # Hochgeladene Dateien
    └── processed/             # Verarbeitete Daten
```

## Lizenz

MIT

## Support

Bei Problemen oder Fragen: Kontaktiere den Entwickler
