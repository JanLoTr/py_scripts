````md
# Empfohlene Vorgehensweise

## Schritt 1: Vorbereitung

### Ordnerstruktur erstellen

```text
Ihr_Projekt/
├── rechnungen/           # Hier kommen Ihre PDFs/Bilder
├── extracted_data/       # Automatisch erstellt
├── rechnungsberichte/   # Automatisch erstellt
├── skript1_extrahieren.py
└── skript2_verwalten.py
````

---

## Schritt 2: Daten extrahieren

1. Rechnungen in den Ordner `rechnungen/` kopieren
2. `skript1_extrahieren.py` ausführen
3. Extrahierte Daten im Ordner `extracted_data/` überprüfen

---

## Schritt 3: Aufteilung anpassen

1. `skript2_verwalten.py` ausführen
2. **Option 4** wählen
   *(Dateien umbenennen + Bericht erstellen)*
3. Die Datei `interaktive_aufteilung_*.csv` öffnen
4. Spalten `Anteil_Bruder` und `Anteil_Ich` anpassen

   * Beispiel:

     * `1.0 / 0.0` → vollständig **ich**
     * `0.5 / 0.5` → **hälftig**

---

## Schritt 4: Aufteilung aktualisieren

1. Bearbeitete CSV speichern
2. In `skript2_verwalten.py` **Option 3** wählen
3. CSV laden
4. Aktualisierte Aufteilung erhalten

---

## Vorteile dieser Lösung

* **Flexible Aufteilung**
  Jedes Produkt kann individuell aufgeteilt werden

* **Automatische Namensgebung**
  Dateien werden sinnvoll und konsistent umbenannt

* **Transparente Berechnung**
  Vollständige Nachvollziehbarkeit aller Beträge

* **KI-Unterstützung**
  Optionale Verbesserung der Texterkennung

* **Einfache Korrektur**
  Manuelle Anpassung der Produktnamen jederzeit möglich

---