# modules/ui/steps.py - Die 3 Hauptschritte
import streamlit as st
import tempfile
from pathlib import Path
import shutil
from modules.state import get_state, update_state
from modules.ai_analysis import analyze_with_groq, create_content_based_fallback_categories
from modules.file_handling import FileProcessor

def render_step1(file_processor):
    """Rendert Schritt 1: Dateien"""
    st.subheader("📥 1. Dateien")
    
    upload_option = st.radio(
        "Quelle",
        ["Hochladen", "Verzeichnis"],
        horizontal=True,
        label_visibility="collapsed",
        key="upload_option_radio"
    )
    
    uploaded_files = None
    input_dir = None
    
    if upload_option == "Hochladen":
        uploaded_files = st.file_uploader(
            "Dateien auswählen",
            accept_multiple_files=True,
            type=[
                "pdf", "docx", "txt", "md", "rtf",
                "jpg", "jpeg", "png", "webp", "gif", "bmp",
                "py", "java", "js", "html", "css", "cpp", "c",
                "xlsx", "csv", "json", "xml",
                "zip", "rar",
                "mp3", "mp4", "wav"
            ],
            label_visibility="collapsed",
            key="file_uploader"
        )
    else:
        input_dir = st.text_input(
            "Verzeichnispfad",
            value="",
            placeholder="C:\\Pfad\\zum\\Ordner",
            label_visibility="collapsed",
            key="directory_input"
        )
    
    if st.button("📥 Dateien extrahieren", type="primary", use_container_width=True, key="extract_files_button"):
        _handle_file_extraction(file_processor, uploaded_files, input_dir)

def _handle_file_extraction(file_processor, uploaded_files, input_dir):
    """Behandelt Dateiextraktion"""
    with st.spinner("Extrahiere Dateiinformationen..."):
        try:
            temp_dir = file_processor.create_temp_directory()
            
            if uploaded_files:
                # Hochgeladene Dateien speichern
                max_files = get_state('max_files', 100)
                for uploaded_file in uploaded_files[:max_files]:
                    file_path = temp_dir / uploaded_file.name
                    with open(file_path, 'wb') as f:
                        f.write(uploaded_file.getbuffer())
                
                source_dir = temp_dir
            elif input_dir:
                source_dir = Path(input_dir)
                if not source_dir.exists():
                    st.error("Verzeichnis existiert nicht!")
                    return
            else:
                st.warning("Bitte Dateien hochladen oder Verzeichnis angeben!")
                return
            
            # Dateien extrahieren
            files_data = file_processor.extract_all_files(source_dir, get_state('max_files', 100))
            
            # Gruppierte Statistik hinzufügen
            _add_file_type_statistics(files_data)
            
            update_state('files_data', files_data)
            update_state('processing_step', 2)
            st.success(f"✅ {files_data['metadata']['total_files']} Dateien verarbeitet")
            st.rerun()
            
        except Exception as e:
            st.error(f"Fehler bei Dateiextraktion: {str(e)[:200]}")

def _add_file_type_statistics(files_data):
    """Fügt gruppierte Dateitypen-Statistik hinzu"""
    individual_counts = files_data['metadata'].get('file_types', {})
    grouped_counts = {
        "PDFs": 0,
        "Word-Dokumente": 0,
        "Textdateien": 0,
        "Bilder": 0,
        "Code": 0,
        "Tabellen": 0,
        "Archive": 0,
        "Media": 0,
        "Ausführbare Dateien": 0,
        "Sonstige": 0
    }
    
    for ext, count in individual_counts.items():
        ext_lower = ext.lower()
        
        if ext_lower == ".pdf":
            grouped_counts["PDFs"] += count
        elif ext_lower in [".docx", ".doc"]:
            grouped_counts["Word-Dokumente"] += count
        elif ext_lower in [".txt", ".md", ".rtf"]:
            grouped_counts["Textdateien"] += count
        elif ext_lower in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"]:
            grouped_counts["Bilder"] += count
        elif ext_lower in [".py", ".java", ".js", ".html", ".css", ".cpp", ".c", ".php", ".rb", ".go", ".rs"]:
            grouped_counts["Code"] += count
        elif ext_lower in [".xlsx", ".xls", ".csv", ".ods"]:
            grouped_counts["Tabellen"] += count
        elif ext_lower in [".zip", ".rar", ".7z", ".tar", ".gz"]:
            grouped_counts["Archive"] += count
        elif ext_lower in [".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv"]:
            grouped_counts["Media"] += count
        elif ext_lower in [".exe", ".msi", ".dmg", ".app", ".bat", ".cmd"]:
            grouped_counts["Ausführbare Dateien"] += count
        else:
            grouped_counts["Sonstige"] += count
    
    # Entferne leere Kategorien
    grouped_counts = {k: v for k, v in grouped_counts.items() if v > 0}
    
    # Speichere in Metadaten
    if 'file_types' in files_data['metadata']:
        files_data['metadata']['gruppiert'] = grouped_counts
        files_data['metadata']['individuell'] = individual_counts

def render_step2(file_processor):
    """Rendert Schritt 2: KI-Analyse"""
    st.subheader("🤖 2. KI-Analyse")
    
    files_data = get_state('files_data')
    
    if files_data:
        files_count = files_data["metadata"]["total_files"]
        st.success(f"✅ {files_count} Dateien verarbeitet")
        
        # VERBESSERTE DATEITYPEN-ANZEIGE
        file_types_info = files_data["metadata"]
        
        # Zeige gruppierte Statistik
        if "gruppiert" in file_types_info:
            groups = file_types_info["gruppiert"]
            
            st.write("**Dateitypen (gruppiert):**")
            # In 2 Spalten anzeigen
            col_g1, col_g2 = st.columns(2)
            
            with col_g1:
                for i, (group, count) in enumerate(list(groups.items())[:len(groups)//2]):
                    st.write(f"• {group}: **{count}**")
            
            with col_g2:
                for i, (group, count) in enumerate(list(groups.items())[len(groups)//2:]):
                    st.write(f"• {group}: **{count}**")
        
        # KI-Analyse Buttons
        api_key = get_state('api_key', "")
        detail_level = get_state('detail_level', "mittel")
        
        if api_key:
            if st.button("🤖 Mit KI analysieren", type="primary", use_container_width=True, key="analyze_ai_button"):
                with st.spinner("KI analysiert..."):
                    categories = analyze_with_groq(
                        files_data["files"],
                        api_key,
                        detail_level
                    )
                    update_state('categories', categories)
                    update_state('processing_step', 3)
                    st.rerun()
        else:
            st.warning("API Key benötigt")
            
            if st.button("📊 Einfache Kategorien", use_container_width=True, key="simple_categories_button"):
                with st.spinner("Erstelle Kategorien..."):
                    categories = create_content_based_fallback_categories(files_data["files"], detail_level)
                    update_state('categories', categories)
                    update_state('processing_step', 3)
                    st.rerun()
    else:
        st.info("⏳ Dateien extrahieren")

def render_step3(file_processor):
    """Rendert Schritt 3: Dateiorganisation"""
    st.subheader("📁 3. Dateien organisieren")
    
    categories = get_state('categories')
    
    if categories and 'results' in categories:
        st.info(f"📂 {len(categories['results'])} Dateien kategorisiert")
        
        # Zielverzeichnis
        target_dir = st.text_input(
            "Zielverzeichnis",
            value=str(Path.home() / "Desktop" / "SortierteDateien"),
            placeholder="C:\\Users\\Name\\Desktop\\SortierteDateien",
            key="target_dir_input"
        )
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            if target_dir and st.button("📂 Dateien sortieren", type="primary", use_container_width=True):
                _handle_file_organization(file_processor, target_dir)
        
        with col2:
            if st.button("🔄 Zurücksetzen", use_container_width=True):
                update_state('categories', None)
                update_state('processing_step', 2)
                st.rerun()
    
    elif get_state('processing_step') >= 3:
        st.info("⏳ Warte auf KI-Analyse")
    else:
        st.info("⏳ Dateien extrahieren und analysieren")

def _handle_file_organization(file_processor, target_dir):
    """Behandelt Dateiorganisation"""
    with st.spinner("Sortiere Dateien..."):
        temp_dir = get_state('temp_dir')
        files_data = get_state('files_data')
        categories = get_state('categories')
        
        if not temp_dir or not files_data or not categories:
            st.error("Daten nicht verfügbar!")
            return
        
        # Zielverzeichnis erstellen
        target_path = Path(target_dir)
        try:
            target_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            st.error(f"Konnte Zielverzeichnis nicht erstellen: {str(e)}")
            return
        
        # Dateien organisieren
        stats = file_processor.organize_files(
            files_data["files"],
            categories,
            temp_dir,
            target_path
        )
        
        # Nicht verarbeitete Dateien kopieren
        not_processed_count = file_processor.copy_not_processed_files(target_path)
        
        # Ergebnis anzeigen
        st.success(f"✅ {stats['moved']} Dateien sortiert")
        
        if not_processed_count > 0:
            st.info(f"📁 {not_processed_count} nicht verarbeitete Dateien kopiert")
        
        if stats['errors'] > 0:
            st.warning(f"⚠ {stats['errors']} Fehler aufgetreten")
        
        # Download-Daten vorbereiten
        from .downloads import prepare_download_data
        prepare_download_data(categories, files_data)
        
        # Cleanup-Button
        if st.button("🗑️ Temporäre Dateien löschen", key="cleanup_button"):
            file_processor.cleanup_temp_directory()
            st.success("Aufgeräumt")
            st.rerun()