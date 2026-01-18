import os
import json
from pathlib import Path
import pdfplumber
import docx
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
import re

# Pfad zu Tesseract OCR auf Windows
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# INPUT_DIR = r"C:\Users\jan\Downloads\WA2"  # Wird jetzt als Argument oder Eingabe verwendet

# Bestimme das Verzeichnis, in dem dieses Skript liegt
SCRIPT_DIR = Path(__file__).parent.absolute()
# Ausgabedatei wird im gleichen Verzeichnis wie das Skript gespeichert
OUTPUT_FILE = SCRIPT_DIR / "datei_inhalte.json"

PDF_PAGE_LIMIT = 5

def get_input_directory():
    """
    Fragt den Benutzer nach dem Eingabeverzeichnis oder verwendet ein Standardverzeichnis
    """
    default_dir = r"C:\Users\jan\Downloads\WA2"
    
    print(f"Aktuelles Skript-Verzeichnis: {SCRIPT_DIR}")
    print(f"Standard-Eingabeverzeichnis: {default_dir}")
    print("\nBitte wählen Sie:")
    print("1. Standardverzeichnis verwenden")
    print("2. Eigenes Verzeichnis eingeben")
    print("3. Aktuelles Verzeichnis verwenden")
    
    choice = input("\nIhre Wahl (1/2/3): ").strip()
    
    if choice == "1":
        return Path(default_dir)
    elif choice == "2":
        user_dir = input("Bitte geben Sie den vollständigen Pfad zum Verzeichnis ein: ").strip()
        return Path(user_dir)
    elif choice == "3":
        return SCRIPT_DIR
    else:
        print(f"Ungültige Eingabe. Verwende Standardverzeichnis: {default_dir}")
        return Path(default_dir)

def clean_filename(filename):
    """
    Bereinigt Dateinamen von fehlerhaften Unicode-Zeichen
    """
    # Mapping für häufige fehlerhafte Zeichen
    replacements = {
        '├ƒ': 'ß',
        '├ä': 'ä',
        '├¤': 'ä',
        '├Â': 'ö',
        '├â': 'ö',
        '├¶': 'ö',
        '├£': 'ü',
        '├╝': 'ü',
        '├ô': 'ü',
        '├ü': 'ü',
        '├ƒÃ': 'Ä',
        '├û': 'Ö',
        '├£': 'Ü',
        '├ƒÅ¸': 'ß',
        '├č': 'ß',
        '┬À': '',
        '┬á': '',
        '┬â': '',
        '┬ã': '',
        '┬ä': '',
        '┬ø': '',
        '─ô': 'ü',
        'a╠ê' : 'ä',
    }
    
    new_name = filename
    for bad, good in replacements.items():
        new_name = new_name.replace(bad, good)
    
    # Entferne verbleibende problematische Zeichen
    new_name = re.sub(r'[^\w\s\-\.]', '_', new_name)
    
    # Mehrfache Unterstriche vermeiden
    new_name = re.sub(r'_+', '_', new_name)
    
    return new_name

def rename_files(directory):
    """
    Benennt alle Dateien im Verzeichnis um
    """
    renamed_count = 0
    
    for file_path in Path(directory).rglob("*"):
        if file_path.is_file():
            old_name = file_path.name
            new_name = clean_filename(old_name)
            
            if old_name != new_name:
                new_path = file_path.parent / new_name
                
                # Verhindere Überschreibungen
                counter = 1
                while new_path.exists():
                    name_parts = new_name.rsplit('.', 1)
                    if len(name_parts) == 2:
                        new_path = file_path.parent / f"{name_parts[0]}_{counter}.{name_parts[1]}"
                    else:
                        new_path = file_path.parent / f"{new_name}_{counter}"
                    counter += 1
                
                try:
                    file_path.rename(new_path)
                    print(f"Umbenannt: {old_name} → {new_path.name}")
                    renamed_count += 1
                except Exception as e:
                    print(f"Fehler beim Umbenennen von {old_name}: {e}")
    
    return renamed_count

def extract_text(file_path):
    ext = file_path.suffix.lower()
    try:
        # PDF
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

        # Word
        elif ext == ".docx":
            doc = docx.Document(file_path)
            return "\n".join(p.text for p in doc.paragraphs).strip()

        # Text / Markdown
        elif ext in [".txt", ".md"]:
            return file_path.read_text(encoding="utf-8", errors="ignore").strip()

        # Bilder
        elif ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
            img = Image.open(file_path)
            return pytesseract.image_to_string(img).strip()

        else:
            return f"UNBEKANNTER DATEITYP: {ext}"

    except Exception as e:
        return f"ERROR: {e}"

def main():
    print("=== DATEIINHALTE EXTRACTOR ===")
    print(f"Skript-Verzeichnis: {SCRIPT_DIR}")
    print(f"Ausgabedatei wird gespeichert in: {OUTPUT_FILE}")
    print("=" * 50)
    
    # Benutzer nach Eingabeverzeichnis fragen
    INPUT_DIR = get_input_directory()
    
    if not INPUT_DIR.exists():
        print(f"\nFEHLER: Das Verzeichnis existiert nicht: {INPUT_DIR}")
        print("Das Skript wird beendet.")
        return
    
    print(f"\nEingabeverzeichnis: {INPUT_DIR}")
    
    # SCHRITT 1: Dateinamen bereinigen
    print("\n=== SCHRITT 1: Dateinamen bereinigen ===")
    renamed = rename_files(INPUT_DIR)
    print(f"\n{renamed} Dateien umbenannt.\n")
    
    # SCHRITT 2: Dateien extrahieren
    print("=== SCHRITT 2: Dateiinhalte extrahieren ===")
    data = []
    
    # Dateitypen zählen
    file_types = {}
    processed_count = 0
    
    for file in Path(INPUT_DIR).rglob("*"):
        if file.is_file():
            processed_count += 1
            file_ext = file.suffix.lower()
            file_types[file_ext] = file_types.get(file_ext, 0) + 1
            
            print(f"Verarbeite ({processed_count}): {file.name}")
            text = extract_text(file)
            data.append({
                "filename": file.name,
                "path": str(file),
                "extension": file_ext,
                "text_preview": text[:3000] if isinstance(text, str) else str(text)[:3000]
            })
    
    # Ergebnis speichern
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "metadata": {
                    "input_directory": str(INPUT_DIR),
                    "script_directory": str(SCRIPT_DIR),
                    "total_files": len(data),
                    "file_types": file_types,
                    "processed_date": str(Path(__file__).stat().st_mtime)
                },
                "files": data
            }, f, ensure_ascii=False, indent=2)
        
        print(f"\n" + "=" * 50)
        print(f"FERTIG!")
        print(f"{len(data)} Dateien extrahiert")
        print(f"Ausgabedatei: {OUTPUT_FILE}")
        
        # Zusammenfassung anzeigen
        print("\nZusammenfassung der Dateitypen:")
        for ext, count in file_types.items():
            print(f"  {ext if ext else '(keine Endung)'}: {count} Dateien")
            
        # Dateigröße anzeigen
        output_size = OUTPUT_FILE.stat().st_size / 1024  # Größe in KB
        print(f"\nJSON-Dateigröße: {output_size:.2f} KB")
        
    except Exception as e:
        print(f"\nFEHLER beim Speichern der Ausgabedatei: {e}")
        # Alternative: In Skript-Verzeichnis speichern
        alt_output = SCRIPT_DIR / "datei_inhalte_fallback.json"
        try:
            with open(alt_output, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Daten wurden stattdessen gespeichert in: {alt_output}")
        except Exception as e2:
            print(f"Kritischer Fehler: Konnte Daten nicht speichern: {e2}")

if __name__ == "__main__":
    main()