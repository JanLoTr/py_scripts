# 📄 Automatische Dateisortierung mit Python + KI

## 1️⃣ Voraussetzungen (Windows)

### 1. Python installieren

Download: https://www.python.org/downloads/

✅ **„Add Python to PATH" anhaken**

### 2. Python-Pakete installieren

Öffne CMD oder PowerShell:

```bash
pip install pdfplumber python-docx pillow pytesseract pdf2image
```

### 3. Tesseract OCR installieren

Download: https://github.com/tesseract-ocr/tesseract

Installationspfad merken, z. B.:

```
C:\Program Files\Tesseract-OCR
```

Optional: Pfad zu Windows PATH hinzufügen (damit Python ihn automatisch findet)

### 4. PDF2Image-Requirement

Für PDF-OCR: poppler für Windows: https://github.com/oschwartz10612/poppler-windows

Pfad merken → `convert_from_path(pdf_path, poppler_path="C:\\poppler\\bin")` falls nötig.

---

## 2️⃣ Python Script: script_extract.py

```python
import os
import json
from pathlib import Path
import pdfplumber
import docx
from PIL import Image
import pytesseract
from pdf2image import convert_from_path

# Pfad zu Tesseract OCR (anpassen!)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Ordner mit deinen Dateien
INPUT_DIR = r"C:\Users\jan\Downloads\WA"
OUTPUT_FILE = "datei_inhalte.json"
PDF_PAGE_LIMIT = 5  # nur die ersten 5 Seiten für Kontext

def extract_text(file_path):
    ext = file_path.suffix.lower()
    try:
        if ext == ".pdf":
            text = ""
            with pdfplumber.open(file_path) as pdf:
                max_pages = min(len(pdf.pages), PDF_PAGE_LIMIT)
                for i in range(max_pages):
                    page = pdf.pages[i]
                    txt = page.extract_text()
                    if txt and txt.strip():
                        text += txt
                    else:
                        # OCR, falls keine Textinhalte gefunden
                        pil_images = convert_from_path(file_path, first_page=i+1, last_page=i+1)
                        for img in pil_images:
                            text += pytesseract.image_to_string(img)
            return text.strip()
        
        elif ext == ".docx":
            doc = docx.Document(file_path)
            return "\n".join(p.text for p in doc.paragraphs).strip()
        
        elif ext in [".txt", ".md"]:
            return file_path.read_text(encoding="utf-8", errors="ignore").strip()
        
        elif ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
            img = Image.open(file_path)
            return pytesseract.image_to_string(img).strip()
        
        else:
            return f"UNBEKANNTER DATEITYP: {ext}"
    
    except Exception as e:
        return f"ERROR: {e}"

data = []
for file in Path(INPUT_DIR).rglob("*"):  # alle Dateien inkl. Unterordner
    if file.is_file():
        print(f"Verarbeite: {file.name}")
        text = extract_text(file)
        data.append({
            "filename": file.name,
            "path": str(file),
            "text_preview": text[:3000]  # nur die ersten 3000 Zeichen
        })

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Fertig. {len(data)} Dateien extrahiert → {OUTPUT_FILE}")
```

---

## 3️⃣ KI-Prompt: „Jede Datei einsortieren"

```
Du bist ein Dokumenten-Analysesystem.

Aufgabe:
- Jede Datei muss **einer Kategorie zugeordnet** werden.
- Es darf **keine Datei ausgelassen** werden.
- Kategorien sollen **kurz, klar und verständlich** sein.
- Wenn der Inhalt unklar ist, ordne die Datei in "Unklar / Sonstiges".

Antwortformat **exklusiv JSON**, Beispiel:

{
  "results": [
    {
      "filename": "datei1.pdf",
      "category": "Eisverkäufer / Sommergeschäft",
      "confidence": 0.87
    }
  ]
}

Wichtig:
- Verwende echte Kategorien, keine leeren Felder.
- Antworte **für jede einzelne Datei**, auch wenn sie leer ist.
- Priorisiere inhaltliche Relevanz.

Hier sind die Dateien:

<JSON HIER EINSETZEN>
```

---

## 4️⃣ Python Script: Dateien verschieben (script_sort.py)

```python
import json
import shutil
from pathlib import Path

INPUT_JSON = "ki_antwort.json"
BASE_DIR = r"C:\Users\jan\Downloads\WA"
TARGET_BASE = r"C:\Users\jan\Downloads\WA\_SORTIERT"

with open(INPUT_JSON, "r", encoding="utf-8") as f:
    data = json.load(f)["results"]

for item in data:
    filename = item["filename"]
    category = item["category"].replace("/", "-")  # keine Probleme mit Slash
    
    source = Path(BASE_DIR) / filename
    target_dir = Path(TARGET_BASE) / category
    target_dir.mkdir(parents=True, exist_ok=True)
    
    if source.exists():
        shutil.move(str(source), str(target_dir / filename))
        print(f"{filename} → {category}")
    else:
        print(f"NICHT GEFUNDEN: {filename}")
```

---

## 5️⃣ Anpassungen, damit es auf deinem System läuft

**Tesseract-Pfad anpassen:**

```python
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

**INPUT_DIR** → Ordner, in dem alle Dateien liegen

**PDF_PAGE_LIMIT** → wie viele Seiten pro PDF gelesen werden sollen (Standard 5)

**TARGET_BASE** → Ordner für sortierte Dateien

---

## 6️⃣ Ablauf

1. **script_extract.py** ausführen → `datei_inhalte.json` wird erstellt
2. JSON in deine KI schicken → mit obigem Prompt → `ki_antwort.json` speichern
3. **script_sort.py** ausführen → Dateien werden automatisch in Kategorien sortiert