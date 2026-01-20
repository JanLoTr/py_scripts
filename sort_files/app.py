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
import re

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
    defaults = {
        'files_data': None,
        'categories': None,
        'processing_step': 1,
        'uploaded_files': [],
        'temp_dir': None,
        'renamed_files': [],
        'clean_filenames': True
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def create_temp_directory():
    """Temporäres Verzeichnis erstellen"""
    if st.session_state.temp_dir is None:
        temp_dir = tempfile.mkdtemp(prefix="ki_sort_")
        st.session_state.temp_dir = Path(temp_dir)
    return st.session_state.temp_dir

def cleanup_temp_directory():
    """Temporäres Verzeichnis aufräumen"""
    if st.session_state.temp_dir and st.session_state.temp_dir.exists():
        shutil.rmtree(st.session_state.temp_dir)
        st.session_state.temp_dir = None

def extract_zip(file_bytes, extract_to):
    """ZIP-Datei extrahieren"""
    with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as zip_ref:
        zip_ref.extractall(extract_to)

def clean_filename(filename):
    """Dateinamen bereinigen von Sonderzeichen"""
    if not st.session_state.clean_filenames:
        return filename
    
    # Entferne problematische Zeichen
    cleaned = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Ersetze Umlaute und Sonderzeichen
    replacements = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue',
        'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
        'ß': 'ss', 'é': 'e', 'è': 'e',
        'á': 'a', 'à': 'a', 'ó': 'o',
        'ò': 'o', 'ú': 'u', 'ù': 'u'
    }
    
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    
    # Mehrfache Unterstriche reduzieren
    cleaned = re.sub(r'_+', '_', cleaned)
    
    # Trimme führende/nachgestellte Punkte/Unterstriche
    cleaned = cleaned.strip('._')
    
    return cleaned if cleaned else filename

def rename_files_in_directory(directory):
    """Alle Dateien in einem Verzeichnis umbenennen"""
    renamed = []
    for file_path in Path(directory).rglob("*"):
        if file_path.is_file():
            old_name = file_path.name
            new_name = clean_filename(old_name)
            
            if old_name != new_name:
                new_path = file_path.parent / new_name
                counter = 1
                while new_path.exists():
                    name_parts = new_name.rsplit('.', 1)
                    if len(name_parts) == 2:
                        new_name_with_counter = f"{name_parts[0]}_{counter}.{name_parts[1]}"
                    else:
                        new_name_with_counter = f"{new_name}_{counter}"
                    new_path = file_path.parent / new_name_with_counter
                    counter += 1
                
                try:
                    file_path.rename(new_path)
                    renamed.append((old_name, new_path.name))
                except:
                    pass
    
    st.session_state.renamed_files = renamed
    return renamed

def extract_text_from_file(file_path):
    """Text aus verschiedenen Dateitypen extrahieren"""
    try:
        ext = file_path.suffix.lower()
        
        # Programmiersprachen
        if ext in [".py", ".java", ".cpp", ".c", ".h", ".hpp", ".js", 
                  ".ts", ".html", ".css", ".php", ".rb", ".go", ".rs", 
                  ".swift", ".kt", ".scala", ".sql", ".sh", ".bat", 
                  ".ps1", ".yaml", ".yml", ".json", ".xml", ".csv"]:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(10000)  # Erste 10.000 Zeichen
                return f"Code-Datei ({ext}):\n{content}"
        
        # PDF
        elif ext == ".pdf":
            text = ""
            try:
                with pdfplumber.open(file_path) as pdf:
                    for i, page in enumerate(pdf.pages[:3]):  # Nur erste 3 Seiten
                        page_text = page.extract_text()
                        if page_text:
                            text += f"\n--- Seite {i+1} ---\n{page_text}"
            except:
                text = "PDF konnte nicht gelesen werden"
            return text.strip()
        
        # Word
        elif ext == ".docx":
            try:
                doc = Document(file_path)
                paragraphs = [p.text for p in doc.paragraphs if p.text]
                return "\n".join(paragraphs[:50])  # Erste 50 Absätze
            except:
                return "Word-Dokument (Inhalt nicht lesbar)"
        
        # Textdateien
        elif ext in [".txt", ".md", ".rtf", ".log"]:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read(5000).strip()
        
        # Bilder (inkl. WebP)
        elif ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".gif", ".webp"]:
            try:
                img = Image.open(file_path)
                # Konvertiere WebP zu RGB für Tesseract
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                text = pytesseract.image_to_string(img)
                return text.strip() or f"Bilddatei: {file_path.name} (kein Text erkannt)"
            except Exception as e:
                return f"Bilddatei: {file_path.name} (OCR Fehler: {str(e)})"
        
        # PowerPoint
        elif ext in [".pptx", ".ppt"]:
            return f"Präsentation: {file_path.name}"
        
        # Excel
        elif ext in [".xlsx", ".xls", ".ods"]:
            return f"Tabelle: {file_path.name}"
        
        # Audio/Video (Metadaten)
        elif ext in [".mp3", ".wav", ".mp4", ".avi", ".mov", ".opus"]:
            return f"Media-Datei: {file_path.name}"
        
        # Archiv
        elif ext in [".zip", ".rar", ".7z", ".tar", ".gz"]:
            return f"Archiv: {file_path.name}"
        
        # Sonstige
        else:
            return f"Datei: {file_path.name} (Typ: {ext})"
            
    except Exception as e:
        return f"FEHLER beim Lesen: {str(e)}"

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
            status_text.text(f"Verarbeite: {file_path.name[:30]}... ({idx+1}/{min(len(all_files), max_files)})")
            
            # Text extrahieren
            text = extract_text_from_file(file_path)
            
            # Statistik
            ext = file_path.suffix.lower()
            file_types[ext] = file_types.get(ext, 0) + 1
            
            files_data.append({
                "filename": file_path.name,
                "clean_name": clean_filename(file_path.name),
                "path": str(file_path),
                "extension": ext,
                "text_preview": text[:1500] if isinstance(text, str) else str(text)[:1500]
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
        "wenig": "Kurze Analyse: 1-2 Wörter pro Kategorie. Schnelle Zuordnung.",
        "mittel": "Normale Analyse: Beschreibende Kategorien mit 2-3 Wörtern.",
        "viel": "Detaillierte Analyse: Spezifische Kategorien. Berücksichtige Dateiinhalt."
    }
    
    prompt = prompts.get(detail_level, prompts["mittel"])
    
    # Effizienterer Prompt für viele Dateien
    system_prompt = f"""Du bist ein Datei-Kategorisierungs-Assistent.

{prompt}

Regeln:
- Kategorisiere jede Datei basierend auf ihrem Inhalt
- Nutze das Format: "Hauptkategorie / Unterkategorie"
- Beispiele: "Finanzen / Rechnung", "Schule / Mathe-Aufgaben", "Code / Python-Skript"
- Antworte NUR im JSON-Format

Erwartetes JSON:
{{
  "results": [
    {{
      "filename": "dateiname.xyz",
      "category": "Kategorie / Unterkategorie",
      "confidence": 0.0-1.0
    }}
  ]
}}

Analysiere diese Dateien:"""
    
    # Begrenze die Anzahl der Dateien für den Prompt (Performance)
    max_files_for_prompt = 50 if detail_level == "viel" else 100
    files_for_prompt = files_data[:max_files_for_prompt]
    
    # Kürze die Vorschautexte für Tokens
    shortened_files = []
    for f in files_for_prompt:
        shortened = f.copy()
        if len(shortened['text_preview']) > 800:
            shortened['text_preview'] = shortened['text_preview'][:800] + "..."
        shortened_files.append(shortened)
    
    user_message = json.dumps({
        "instruction": f"Kategorisiere {len(files_data)} Dateien ({len(files_for_prompt)} im Detail)",
        "files": shortened_files
    }, ensure_ascii=False)
    
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.2,
            max_tokens=4000
        )
        
        content = response.choices[0].message.content.strip()
        
        # JSON extrahieren
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        result = json.loads(content)
        
        # Sicherstellen, dass alle Dateien eine Kategorie haben
        if "results" in result:
            # Fehlende Dateien ergänzen
            processed_filenames = {r["filename"] for r in result["results"]}
            for file_data in files_data:
                if file_data["filename"] not in processed_filenames:
                    # Einfache Kategorie basierend auf Dateityp
                    ext = file_data["extension"]
                    if ext in [".py", ".java", ".js"]:
                        category = "Programmierung / Code"
                    elif ext in [".jpg", ".png", ".webp"]:
                        category = "Bilder / Fotos"
                    elif ext == ".pdf":
                        category = "Dokumente / PDF"
                    else:
                        category = "Divers / Unsortiert"
                    
                    result["results"].append({
                        "filename": file_data["filename"],
                        "category": category,
                        "confidence": 0.6
                    })
            
            return result
        
    except Exception as e:
        st.error(f"KI-Analyse Fehler: {e}")
        return create_fallback_categories(files_data)

def create_fallback_categories(files_data):
    """Fallback-Kategorien basierend auf Dateityp"""
    results = []
    
    type_categories = {
        # Programmierung
        ".py": "Programmierung / Python",
        ".java": "Programmierung / Java", 
        ".js": "Programmierung / JavaScript",
        ".html": "Web / HTML",
        ".css": "Web / CSS",
        ".cpp": "Programmierung / C++",
        ".c": "Programmierung / C",
        
        # Dokumente
        ".pdf": "Dokumente / PDF",
        ".docx": "Dokumente / Word",
        ".txt": "Dokumente / Text",
        ".md": "Dokumente / Markdown",
        
        # Bilder
        ".jpg": "Bilder / Fotos",
        ".jpeg": "Bilder / Fotos",
        ".png": "Bilder / Grafiken",
        ".webp": "Bilder / Web",
        ".gif": "Bilder / Animation",
        
        # Tabellen
        ".xlsx": "Daten / Excel",
        ".csv": "Daten / CSV",
        ".json": "Daten / JSON",
        
        # Sonstige
        ".zip": "Archiv / ZIP",
        ".mp3": "Media / Audio",
        ".mp4": "Media / Video"
    }
    
    for file_data in files_data:
        ext = file_data["extension"].lower()
        category = type_categories.get(ext, "Divers / Unsortiert")
        
        results.append({
            "filename": file_data["filename"],
            "category": category,
            "confidence": 0.7
        })
    
    return {"results": results}

def organize_files(files_data, categories, source_dir, target_dir):
    """Dateien nach Kategorien organisieren"""
    stats = {
        'moved': 0,
        'not_found': 0,
        'errors': 0,
        'categories': {}
    }
    
    target_path = Path(target_dir)
    target_path.mkdir(parents=True, exist_ok=True)
    
    # Dateizuordnung erstellen
    file_map = {f["filename"]: f for f in files_data}
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, item in enumerate(categories["results"]):
        filename = item["filename"]
        category = item["category"].replace("/", "-").replace("\\", "-")
        
        progress = (i + 1) / len(categories["results"])
        progress_bar.progress(progress)
        status_text.text(f"Sortiere: {filename[:40]}...")
        
        if category not in stats['categories']:
            stats['categories'][category] = 0
        
        source_path = Path(source_dir) / filename
        
        try:
            if source_path.exists():
                target_category_dir = target_path / category
                target_category_dir.mkdir(parents=True, exist_ok=True)
                
                # Verwende bereinigten Namen falls vorhanden
                if filename in file_map and "clean_name" in file_map[filename]:
                    target_name = file_map[filename]["clean_name"]
                else:
                    target_name = filename
                
                target_file = target_category_dir / target_name
                
                # Konflikt vermeiden
                counter = 1
                while target_file.exists():
                    name_parts = target_name.rsplit('.', 1)
                    if len(name_parts) == 2:
                        target_name = f"{name_parts[0]}_{counter}.{name_parts[1]}"
                    else:
                        target_name = f"{target_name}_{counter}"
                    target_file = target_category_dir / target_name
                    counter += 1
                
                shutil.move(str(source_path), str(target_file))
                stats['moved'] += 1
                stats['categories'][category] += 1
            else:
                stats['not_found'] += 1
                
        except Exception as e:
            stats['errors'] += 1
    
    progress_bar.empty()
    status_text.empty()
    
    return stats

def display_file_preview(files_data):
    """Verbesserte Dateivorschau anzeigen"""
    if not files_data:
        return
    
    with st.expander("📋 Dateivorschau (erste 10 Dateien)", expanded=True):
        for i, file_data in enumerate(files_data[:10]):
            with st.container():
                col1, col2 = st.columns([1, 3])
                
                with col1:
                    # Dateityp-Icon
                    ext = file_data["extension"]
                    icon = "📄"
                    if ext in [".jpg", ".png", ".webp"]:
                        icon = "🖼️"
                    elif ext in [".py", ".java", ".js"]:
                        icon = "💻"
                    elif ext == ".pdf":
                        icon = "📕"
                    elif ext == ".docx":
                        icon = "📘"
                    elif ext == ".zip":
                        icon = "📦"
                    
                    st.markdown(f"**{icon} {file_data['filename']}**")
                    st.caption(f"Typ: {ext}")
                    
                    if file_data.get('clean_name') != file_data['filename']:
                        st.caption(f"→ {file_data['clean_name']}")
                
                with col2:
                    # Textvorschau in Box
                    preview = file_data["text_preview"]
                    if preview:
                        if len(preview) > 300:
                            preview = preview[:300] + "..."
                        st.text_area(
                            "Inhalt",
                            preview,
                            height=100,
                            key=f"preview_{i}",
                            disabled=True,
                            label_visibility="collapsed"
                        )
        
        if len(files_data) > 10:
            st.info(f"Und {len(files_data) - 10} weitere Dateien...")

def display_categories_preview(categories):
    """Verbesserte Kategorienvorschau anzeigen"""
    if not categories or "results" not in categories:
        return
    
    with st.expander("📊 KI-Kategorisierung", expanded=True):
        # Kategorie-Statistik
        cat_stats = {}
        for item in categories["results"]:
            cat = item["category"]
            cat_stats[cat] = cat_stats.get(cat, 0) + 1
        
        # Als Tabelle anzeigen
        st.write("**Kategorien-Übersicht:**")
        
        data = []
        for cat, count in sorted(cat_stats.items()):
            confidence_avg = sum(
                item["confidence"] 
                for item in categories["results"] 
                if item["category"] == cat
            ) / count
            
            data.append({
                "Kategorie": cat,
                "Anzahl": count,
                "Confidence": f"{confidence_avg:.1%}"
            })
        
        st.dataframe(
            data,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Kategorie": st.column_config.TextColumn(width="large"),
                "Anzahl": st.column_config.NumberColumn(width="small"),
                "Confidence": st.column_config.TextColumn(width="small")
            }
        )
        
        # Beispiele pro Kategorie
        st.write("**Beispiele pro Kategorie:**")
        for cat in sorted(cat_stats.keys())[:5]:  # Erste 5 Kategorien
            examples = [
                item["filename"] 
                for item in categories["results"] 
                if item["category"] == cat
            ][:3]  # Erste 3 Beispiele
            
            with st.expander(f"{cat} ({cat_stats[cat]} Dateien)"):
                for ex in examples:
                    st.write(f"• {ex}")

# -------------------- Streamlit UI --------------------
def main():
    st.title("📂 KI-gestützte Dateisortierung")
    st.markdown("---")
    
    # Session State initialisieren
    init_session_state()
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Einstellungen")
        
        # Groq API Key
        api_key = st.text_input(
            "Groq API Key",
            type="password",
            help="Erstelle einen API Key unter https://console.groq.com"
        )
        
        # Detaillevel
        detail_level = st.selectbox(
            "KI-Detailliertheit",
            ["wenig", "mittel", "viel"],
            index=1
        )
        
        # Max Dateien
        max_files = st.slider(
            "Maximale Dateien",
            10, 500, 100
        )
        
        # Dateinamen bereinigen
        st.session_state.clean_filenames = st.checkbox(
            "Dateinamen bereinigen",
            value=True,
            help="Entfernt Sonderzeichen aus Dateinamen"
        )
        
        st.markdown("---")
        st.info("""
        **Unterstützte Dateitypen:**
        
        **Code:** .py, .java, .js, .html, .css, .cpp, .c
        **Dokumente:** .pdf, .docx, .txt, .md
        **Bilder:** .jpg, .png, .webp, .gif
        **Daten:** .xlsx, .csv, .json
        **Media:** .mp3, .mp4
        **Archiv:** .zip
        """)
    
    # Hauptbereich - Drei Spalten
    col1, col2, col3 = st.columns([1, 1, 1])
    
    # SCHRITT 1: Dateien hochladen
    with col1:
        st.subheader("📥 Schritt 1: Dateien")
        
        # Upload Optionen
        upload_option = st.radio(
            "Quelle wählen",
            ["Dateien hochladen", "Verzeichnis angeben"],
            horizontal=True
        )
        
        if upload_option == "Dateien hochladen":
            uploaded_files = st.file_uploader(
                "Dateien auswählen",
                accept_multiple_files=True,
                type=[
                    # Code
                    "py", "java", "js", "html", "css", "cpp", "c", "h",
                    # Dokumente
                    "pdf", "docx", "txt", "md", "rtf",
                    # Bilder
                    "jpg", "jpeg", "png", "webp", "gif", "bmp",
                    # Daten
                    "xlsx", "csv", "json", "xml",
                    # Media
                    "mp3", "mp4", "wav",
                    # Archiv
                    "zip"
                ]
            )
            input_dir = None
        else:
            input_dir = st.text_input(
                "Verzeichnispfad",
                value="C:\\Users\\Beispiel\\Downloads"
            )
            uploaded_files = None
        
        if st.button("📥 Dateien extrahieren", type="primary", use_container_width=True):
            if not uploaded_files and not input_dir:
                st.warning("Bitte Dateien oder Verzeichnis angeben")
            else:
                with st.spinner("Extrahiere Dateien..."):
                    temp_dir = create_temp_directory()
                    
                    if uploaded_files:
                        for uploaded_file in uploaded_files:
                            file_path = temp_dir / uploaded_file.name
                            with open(file_path, 'wb') as f:
                                f.write(uploaded_file.getbuffer())
                        
                        # ZIP extrahieren
                        for zip_file in [f for f in uploaded_files if f.name.endswith('.zip')]:
                            extract_zip(zip_file.getbuffer(), temp_dir)
                        
                        source_path = temp_dir
                    else:
                        source_path = Path(input_dir)
                    
                    # Dateien umbenennen
                    if st.session_state.clean_filenames:
                        renamed = rename_files_in_directory(source_path)
                        if renamed:
                            st.info(f"{len(renamed)} Dateien umbenannt")
                    
                    # Inhalte extrahieren
                    st.session_state.files_data = extract_all_files(source_path, max_files)
                    st.session_state.processing_step = 2
                    st.rerun()
    
    # SCHRITT 2: KI-Analyse
    with col2:
        st.subheader("🤖 Schritt 2: KI-Analyse")
        
        if st.session_state.files_data:
            files_count = len(st.session_state.files_data["files"])
            st.success(f"✅ {files_count} Dateien extrahiert")
            
            # Dateitypen-Statistik
            file_types = st.session_state.files_data["metadata"]["file_types"]
            st.write(f"**{len(file_types)} verschiedene Dateitypen:**")
            
            # Gruppierte Anzeige
            type_groups = {
                "Code": [".py", ".java", ".js", ".html", ".css", ".cpp", ".c", ".h"],
                "Dokumente": [".pdf", ".docx", ".txt", ".md", ".rtf"],
                "Bilder": [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"],
                "Daten": [".xlsx", ".csv", ".json", ".xml"],
                "Andere": []
            }
            
            for group, extensions in type_groups.items():
                count = sum(file_types.get(ext, 0) for ext in extensions)
                if count > 0:
                    st.write(f"  {group}: {count}")
            
            # KI-Analyse Button
            if api_key:
                if st.button("🤖 Mit KI analysieren", type="primary", use_container_width=True):
                    with st.spinner("KI analysiert..."):
                        st.session_state.categories = analyze_with_groq(
                            st.session_state.files_data["files"],
                            api_key,
                            detail_level
                        )
                        st.session_state.processing_step = 3
                        st.rerun()
            else:
                st.warning("API Key für KI benötigt")
                
                if st.button("📊 Einfache Kategorien", use_container_width=True):
                    with st.spinner("Erstelle Kategorien..."):
                        st.session_state.categories = create_fallback_categories(
                            st.session_state.files_data["files"]
                        )
                        st.session_state.processing_step = 3
                        st.rerun()
        else:
            st.info("⏳ Extrahiere zuerst Dateien")
    
    # SCHRITT 3: Organisieren
    with col3:
        st.subheader("📁 Schritt 3: Organisieren")
        
        if st.session_state.categories:
            cat_count = len(st.session_state.categories["results"])
            st.success(f"✅ {cat_count} Kategorien erstellt")
            
            # Zielverzeichnis
            target_dir = st.text_input(
                "Zielverzeichnis",
                value=str(Path.cwd() / "SORTIERTE_DATEIEN")
            )
            
            if st.button("📁 Dateien organisieren", type="primary", use_container_width=True):
                with st.spinner("Organisiere..."):
                    if st.session_state.temp_dir:
                        source_dir = st.session_state.temp_dir
                    elif input_dir:
                        source_dir = Path(input_dir)
                    else:
                        source_dir = st.session_state.temp_dir
                    
                    stats = organize_files(
                        st.session_state.files_data["files"],
                        st.session_state.categories,
                        source_dir,
                        target_dir
                    )
                    
                    # Ergebnis anzeigen
                    st.success(f"✅ {stats['moved']} Dateien sortiert!")
                    
                    if stats['errors'] > 0:
                        st.warning(f"{stats['errors']} Fehler")
                    
                    # Download Optionen
                    col_dl1, col_dl2 = st.columns(2)
                    
                    with col_dl1:
                        categories_json = json.dumps(st.session_state.categories, indent=2)
                        st.download_button(
                            "📥 Kategorien JSON",
                            categories_json,
                            "kategorien.json"
                        )
                    
                    with col_dl2:
                        files_json = json.dumps(st.session_state.files_data, indent=2)
                        st.download_button(
                            "📥 Dateiliste JSON",
                            files_json,
                            "dateien.json"
                        )
                    
                    # Cleanup
                    if st.button("🗑️ Aufräumen", type="secondary"):
                        cleanup_temp_directory()
                        st.success("Bereinigt")
        else:
            st.info("⏳ Führe zuerst KI-Analyse durch")
    
    st.markdown("---")
    
    # VERBESSERTE VORSCHAUEN
    if st.session_state.files_data:
        display_file_preview(st.session_state.files_data["files"])
    
    if st.session_state.categories:
        display_categories_preview(st.session_state.categories)
    
    # Footer
    st.markdown("---")
    st.caption("📂 KI Dateisortierung v2.0 | Unterstützt 30+ Dateitypen")

if __name__ == "__main__":
    main()