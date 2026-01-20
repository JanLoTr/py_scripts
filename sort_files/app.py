# app.py
import streamlit as st
import os
import json
import shutil
import tempfile
from pathlib import Path
import time
import zipfile
import io

# Groq Import für KI-Analyse
from groq import Groq

# PDF und OCR Bibliotheken
import pdfplumber
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
from docx import Document

# -------------------- Konfiguration --------------------
st.set_page_config(
    page_title="KI Dateisortierung",
    page_icon="📂",
    layout="wide"
)

# -------------------- Hilfsfunktionen --------------------
def init_session_state():
    """Session State initialisieren"""
    if 'files_data' not in st.session_state:
        st.session_state.files_data = None
    if 'categories' not in st.session_state:
        st.session_state.categories = None
    if 'processing_step' not in st.session_state:
        st.session_state.processing_step = 1
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = []
    if 'temp_dir' not in st.session_state:
        st.session_state.temp_dir = None

def create_temp_directory():
    """Temporäres Verzeichnis erstellen"""
    if st.session_state.temp_dir is None:
        temp_dir = tempfile.mkdtemp(prefix="ki_sort_")
        st.session_state.temp_dir = Path(temp_dir)
    return st.session_state.temp_dir

def cleanup_temp_directory():
    """Temporäres Verzeichnis aufräumen"""
    if st.session_state.temp_dir and st.session_state.temp_dir.exists():
        import shutil
        shutil.rmtree(st.session_state.temp_dir)
        st.session_state.temp_dir = None

def extract_zip(file_bytes, extract_to):
    """ZIP-Datei extrahieren"""
    with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as zip_ref:
        zip_ref.extractall(extract_to)

def extract_text_from_file(file_path):
    """Text aus verschiedenen Dateitypen extrahieren"""
    try:
        ext = file_path.suffix.lower()
        
        # PDF
        if ext == ".pdf":
            text = ""
            try:
                with pdfplumber.open(file_path) as pdf:
                    for i, page in enumerate(pdf.pages[:5]):  # Nur erste 5 Seiten
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text
                        else:
                            # OCR für gescannte PDFs
                            try:
                                images = convert_from_path(file_path, first_page=i+1, last_page=i+1)
                                for img in images:
                                    text += pytesseract.image_to_string(img)
                            except:
                                pass
            except:
                # Fallback: OCR für gescannte PDFs
                try:
                    images = convert_from_path(file_path)
                    for img in images[:5]:
                        text += pytesseract.image_to_string(img)
                except Exception as e:
                    text = f"PDF-EXTRAKTION FEHLER: {str(e)}"
            return text.strip()
        
        # Word
        elif ext == ".docx":
            doc = Document(file_path)
            return "\n".join([p.text for p in doc.paragraphs if p.text]).strip()
        
        # Textdateien
        elif ext in [".txt", ".md", ".csv", ".json", ".xml"]:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read(5000).strip()  # Nur erste 5000 Zeichen
        
        # Bilder
        elif ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".gif"]:
            try:
                img = Image.open(file_path)
                return pytesseract.image_to_string(img).strip()
            except Exception as e:
                return f"OCR-FEHLER: {str(e)}"
        
        # PowerPoint (einfache Extraktion)
        elif ext in [".pptx", ".ppt"]:
            return f"Präsentationsdatei: {file_path.name}"
        
        # Excel (einfache Extraktion)
        elif ext in [".xlsx", ".xls"]:
            return f"Tabellendatei: {file_path.name}"
        
        # Andere Dateitypen
        else:
            return f"Unterstützter Dateityp: {ext}"
            
    except Exception as e:
        return f"EXTRACTION_ERROR: {str(e)}"

def extract_all_files(input_dir, max_files=100):
    """Alle Dateien im Verzeichnis extrahieren"""
    files_data = []
    file_types = {}
    
    input_path = Path(input_dir)
    all_files = list(input_path.rglob("*"))
    
    # Fortschrittsanzeige
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, file_path in enumerate(all_files[:max_files]):
        if file_path.is_file():
            # Fortschritt aktualisieren
            progress = (idx + 1) / min(len(all_files), max_files)
            progress_bar.progress(progress)
            status_text.text(f"Verarbeite: {file_path.name} ({idx+1}/{min(len(all_files), max_files)})")
            
            # Text extrahieren
            text = extract_text_from_file(file_path)
            
            # Statistik
            ext = file_path.suffix.lower()
            file_types[ext] = file_types.get(ext, 0) + 1
            
            files_data.append({
                "filename": file_path.name,
                "path": str(file_path),
                "extension": ext,
                "text_preview": text[:2000] if isinstance(text, str) else str(text)[:2000]
            })
    
    progress_bar.empty()
    status_text.empty()
    
    return {
        "metadata": {
            "total_files": len(files_data),
            "file_types": file_types,
            "processed_date": time.strftime("%Y-%m-%d %H:%M:%S")
        },
        "files": files_data
    }

def analyze_with_groq(files_data, api_key, detail_level="mittel"):
    """Dateien mit Groq KI analysieren"""
    client = Groq(api_key=api_key)
    
    # Je nach Detaillevel unterschiedliche Prompt-Komplexität
    prompts = {
        "wenig": "Analysiere kurz diese Dateien und gib Kategorien. Sehr kurze Kategorien.",
        "mittel": "Analysiere diese Dateien sorgfältig. Gib sinnvolle, beschreibende Kategorien.",
        "viel": "Tiefgehende Analyse jeder Datei. Detaillierte, spezifische Kategorien."
    }
    
    prompt = prompts.get(detail_level, prompts["mittel"])
    
    # JSON-Format für Prompt
    system_prompt = f"""Du bist ein Dokumenten-Analysesystem.

{prompt}

Regeln:
- Eine Kategorie pro Datei
- Maximal 2-3 Wörter pro Kategorie
- Antworte AUSSCHLIESSLICH im JSON-Format

Beispiel:
{{
  "results": [
    {{
      "filename": "rechnung.pdf",
      "category": "Finanzen / Rechnung",
      "confidence": 0.9
    }}
  ]
}}

Hier sind {len(files_data)} Dateien:"""
    
    # Dateien für Prompt vorbereiten (nur erste 30 für Token-Limit)
    files_for_prompt = files_data[:30]
    
    user_message = json.dumps({
        "file_count": len(files_data),
        "files": files_for_prompt
    }, ensure_ascii=False, indent=2)
    
    try:
        # Groq API aufrufen
        response = client.chat.completions.create(
            model="llama3-8b-8192",  # Kosten-effizientes Modell
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        # JSON aus Antwort extrahieren
        content = response.choices[0].message.content
        content = content.strip()
        
        # JSON finden (kann mit Markdown-Codeblöcken kommen)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        # JSON parsen
        result = json.loads(content)
        
        # Sicherstellen, dass alle Dateien eine Kategorie haben
        if "results" in result:
            # Wenn weniger Kategorien als Dateien, ergänzen
            if len(result["results"]) < len(files_data):
                for i, file_data in enumerate(files_data):
                    if i >= len(result["results"]):
                        result["results"].append({
                            "filename": file_data["filename"],
                            "category": "Divers / Unsortiert",
                            "confidence": 0.5
                        })
            return result
        
    except Exception as e:
        st.error(f"KI-Analyse Fehler: {str(e)}")
        # Fallback: Einfache Kategorien basierend auf Dateiendung
        return create_fallback_categories(files_data)

def create_fallback_categories(files_data):
    """Fallback-Kategorien erstellen"""
    results = []
    
    extension_categories = {
        ".pdf": "PDF Dokument",
        ".docx": "Word Dokument",
        ".txt": "Textdatei",
        ".jpg": "Bild",
        ".png": "Bild",
        ".xlsx": "Excel Tabelle",
        ".pptx": "Präsentation",
        ".zip": "Archiv"
    }
    
    for file_data in files_data:
        ext = file_data["extension"].lower()
        category = extension_categories.get(ext, "Sonstiges")
        
        results.append({
            "filename": file_data["filename"],
            "category": category,
            "confidence": 0.7
        })
    
    return {"results": results}

def organize_files(files_data, categories, base_dir, target_base):
    """Dateien nach Kategorien organisieren"""
    stats = {
        'moved': 0,
        'not_found': 0,
        'errors': 0,
        'categories': {}
    }
    
    target_path = Path(target_base)
    target_path.mkdir(parents=True, exist_ok=True)
    
    # Fortschrittsanzeige
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, item in enumerate(categories["results"]):
        filename = item["filename"]
        category = item["category"].replace("/", "-").replace("\\", "-")
        
        # Fortschritt
        progress = (i + 1) / len(categories["results"])
        progress_bar.progress(progress)
        status_text.text(f"Sortiere: {filename}")
        
        # Statistik
        if category not in stats['categories']:
            stats['categories'][category] = 0
        
        source = Path(base_dir) / filename
        
        try:
            if source.exists():
                target_dir = target_path / category
                target_dir.mkdir(parents=True, exist_ok=True)
                
                # Datei verschieben
                shutil.move(str(source), str(target_dir / filename))
                
                stats['moved'] += 1
                stats['categories'][category] += 1
            else:
                stats['not_found'] += 1
                
        except Exception as e:
            stats['errors'] += 1
    
    progress_bar.empty()
    status_text.empty()
    
    return stats

# -------------------- Streamlit UI --------------------
def main():
    st.title("📂 KI-gestützte Dateisortierung")
    st.markdown("---")
    
    # Session State initialisieren
    init_session_state()
    
    # Sidebar für Einstellungen
    with st.sidebar:
        st.header("⚙️ Einstellungen")
        
        # Groq API Key
        api_key = st.text_input(
            "Groq API Key",
            type="password",
            help="Erstelle einen API Key unter https://console.groq.com"
        )
        
        # Detaillevel für KI-Analyse
        detail_level = st.selectbox(
            "Detailliertheit der KI-Analyse",
            ["wenig", "mittel", "viel"],
            index=1,
            help="Bestimmt, wie detailliert die KI die Dateien analysiert"
        )
        
        # Maximale Anzahl Dateien
        max_files = st.slider(
            "Maximale Anzahl Dateien",
            min_value=10,
            max_value=500,
            value=100,
            help="Limit für die Anzahl der zu verarbeitenden Dateien"
        )
        
        st.markdown("---")
        st.info(
            "**Unterstützte Dateitypen:**\n"
            "PDF, DOCX, TXT, JPG, PNG, PPTX, XLSX, ZIP"
        )
    
    # Hauptbereich
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        st.subheader("Schritt 1: Dateien hochladen")
        
        # Datei-Upload
        uploaded_files = st.file_uploader(
            "Wähle Dateien aus",
            type=["pdf", "docx", "txt", "jpg", "png", "zip", "pptx", "xlsx"],
            accept_multiple_files=True
        )
        
        # Oder Verzeichnis wählen
        use_directory = st.checkbox("Stattdessen Verzeichnis verwenden")
        
        if use_directory:
            input_dir = st.text_input(
                "Pfad zum Verzeichnis",
                value="C:\\Users\\Beispiel\\Downloads\\WA"
            )
        else:
            input_dir = None
        
        if st.button("📥 Dateien extrahieren", type="primary", use_container_width=True):
            if not uploaded_files and not use_directory:
                st.warning("Bitte Dateien hochladen oder ein Verzeichnis angeben")
            else:
                with st.spinner("Extrahiere Dateien..."):
                    # Temporäres Verzeichnis erstellen
                    temp_dir = create_temp_directory()
                    
                    if uploaded_files:
                        # Hochgeladene Dateien speichern
                        for uploaded_file in uploaded_files:
                            file_path = temp_dir / uploaded_file.name
                            with open(file_path, 'wb') as f:
                                f.write(uploaded_file.getbuffer())
                        
                        # ZIP-Dateien extrahieren
                        zip_files = [f for f in uploaded_files if f.name.endswith('.zip')]
                        for zip_file in zip_files:
                            extract_zip(zip_file.getbuffer(), temp_dir)
                        
                        input_path = temp_dir
                    else:
                        input_path = Path(input_dir)
                    
                    # Dateien extrahieren
                    st.session_state.files_data = extract_all_files(input_path, max_files)
                    st.session_state.processing_step = 2
                    st.success(f"{len(st.session_state.files_data['files'])} Dateien extrahiert")
                    st.rerun()
    
    with col2:
        st.subheader("Schritt 2: KI-Analyse")
        
        if st.session_state.files_data:
            st.info(f"✅ {len(st.session_state.files_data['files'])} Dateien bereit")
            
            # Dateitypen anzeigen
            file_types = st.session_state.files_data['metadata']['file_types']
            st.write("**Dateitypen:**")
            for ext, count in file_types.items():
                st.write(f"  {ext}: {count}")
            
            if api_key:
                if st.button("🤖 Mit KI analysieren", type="primary", use_container_width=True):
                    with st.spinner("KI analysiert Dateien..."):
                        categories = analyze_with_groq(
                            st.session_state.files_data['files'],
                            api_key,
                            detail_level
                        )
                        st.session_state.categories = categories
                        st.session_state.processing_step = 3
                        st.success("KI-Analyse abgeschlossen")
                        st.rerun()
            else:
                st.warning("Gib einen API Key ein für KI-Analyse")
                
                # Fallback: Einfache Kategorien
                if st.button("📊 Einfache Kategorien (ohne KI)", use_container_width=True):
                    with st.spinner("Erstelle Kategorien..."):
                        categories = create_fallback_categories(st.session_state.files_data['files'])
                        st.session_state.categories = categories
                        st.session_state.processing_step = 3
                        st.success("Kategorien erstellt")
                        st.rerun()
        else:
            st.info("⏳ Extrahiere zuerst Dateien")
    
    with col3:
        st.subheader("Schritt 3: Organisieren")
        
        if st.session_state.categories:
            st.info(f"✅ {len(st.session_state.categories['results'])} Kategorien erstellt")
            
            # Kategorien anzeigen
            category_counts = {}
            for item in st.session_state.categories['results']:
                cat = item['category']
                category_counts[cat] = category_counts.get(cat, 0) + 1
            
            st.write("**Erkannte Kategorien:**")
            for cat, count in sorted(category_counts.items()):
                st.write(f"  {cat}: {count} Dateien")
            
            # Zielverzeichnis
            target_dir = st.text_input(
                "Zielverzeichnis für sortierte Dateien",
                value=str(Path.cwd() / "SORTIERTE_DATEIEN")
            )
            
            if st.button("📁 Dateien organisieren", type="primary", use_container_width=True):
                with st.spinner("Organisiere Dateien..."):
                    # Quellverzeichnis bestimmen
                    if st.session_state.temp_dir:
                        source_dir = st.session_state.temp_dir
                    elif use_directory and input_dir:
                        source_dir = Path(input_dir)
                    else:
                        source_dir = st.session_state.temp_dir
                    
                    # Dateien organisieren
                    stats = organize_files(
                        st.session_state.files_data['files'],
                        st.session_state.categories,
                        source_dir,
                        target_dir
                    )
                    
                    # Statistik anzeigen
                    st.success(f"{stats['moved']} Dateien erfolgreich sortiert!")
                    
                    if stats['errors'] > 0:
                        st.warning(f"{stats['errors']} Fehler aufgetreten")
                    
                    # Download-Link für Kategorien-Liste
                    categories_json = json.dumps(st.session_state.categories, indent=2, ensure_ascii=False)
                    st.download_button(
                        "📥 Kategorien als JSON speichern",
                        data=categories_json,
                        file_name="datei_kategorien.json",
                        mime="application/json"
                    )
                    
                    # Cleanup Button
                    if st.button("🗑️ Temporäre Dateien löschen", type="secondary"):
                        cleanup_temp_directory()
                        st.success("Temporäre Dateien gelöscht")
        else:
            st.info("⏳ Führe zuerst KI-Analyse durch")
    
    st.markdown("---")
    
    # Vorschau der Daten
    if st.session_state.files_data and st.expander("📋 Extraktionsdetails anzeigen"):
        st.json(st.session_state.files_data, expanded=False)
    
    if st.session_state.categories and st.expander("📋 KI-Analyse-Ergebnisse anzeigen"):
        st.json(st.session_state.categories, expanded=False)
    
    # Footer
    st.markdown("---")
    st.caption("Made with Streamlit & Groq AI | 📂 KI Dateisortierung v1.0")

if __name__ == "__main__":
    main()