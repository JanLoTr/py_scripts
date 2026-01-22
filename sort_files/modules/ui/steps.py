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
    with st.container():
        st.subheader("📥 1. Dateien hochladen")
        
        upload_option = st.radio(
            "Quelle wählen",
            ["📤 Dateien hochladen", "📁 Verzeichnis"],
            horizontal=True,
            label_visibility="visible",
            key="upload_option_radio"
        )
        
        uploaded_files = None
        input_dir = None
        
        if upload_option == "📤 Dateien hochladen":
            uploaded_files = st.file_uploader(
                "Dateien auswählen",
                accept_multiple_files=True,
                label_visibility="collapsed",
                key="file_uploader"
            )
        else:
            input_dir = st.text_input(
                "Verzeichnispfad eingeben",
                value="",
                placeholder="C:\\Pfad\\zum\\Ordner",
                label_visibility="visible",
                key="directory_input"
            )
        
        if st.button("🚀 Dateien extrahieren", type="primary", use_container_width=True, key="extract_files_button"):
            _handle_file_extraction(file_processor, uploaded_files, input_dir)

def _handle_file_extraction(file_processor, uploaded_files, input_dir):
    """Behandelt Dateiextraktion"""
    with st.spinner("⏳ Extrahiere Dateiinformationen..."):
        try:
            temp_dir = file_processor.create_temp_directory()
            
            if uploaded_files:
                # Hochgeladene Dateien speichern
                max_files = get_state('max_files', 100)
                for uploaded_file in uploaded_files:  # KEINE Begrenzung!
                    file_path = temp_dir / uploaded_file.name
                    with open(file_path, 'wb') as f:
                        f.write(uploaded_file.getbuffer())
                
                source_dir = temp_dir
            elif input_dir:
                source_dir = Path(input_dir)
                if not source_dir.exists():
                    st.error("❌ Verzeichnis existiert nicht!")
                    return
            else:
                st.warning("⚠️ Bitte Dateien hochladen oder Verzeichnis angeben!")
                return
            
            # Dateien extrahieren - KEINE max_files Limit hier!
            files_data = file_processor.extract_all_files(source_dir, max_files=10000)  # Sehr hoch
            
            # Gruppierte Statistik hinzufügen
            _add_file_type_statistics(files_data)
            
            update_state('files_data', files_data)
            update_state('processing_step', 2)
            
            # Bessere Anzeige
            total_files = files_data['metadata']['total_files']
            total_found = files_data['metadata'].get('total_found', total_files)
            not_processed = sum(1 for f in files_data['files'] if not f.get('is_processed', True))
            
            st.success(f"✅ {total_files} Dateien verarbeitet ({not_processed} nicht verarbeitbar → `_nicht_verarbeitet` Ordner)")
            
            if files_data['metadata'].get('skipped_files'):
                with st.expander(f"⚠️ Info: {len(files_data['metadata']['skipped_files'])} Dateien nicht verarbeitbar"):
                    for skipped in files_data['metadata']['skipped_files'][:10]:
                        st.write(f"• {skipped}")
                    if len(files_data['metadata']['skipped_files']) > 10:
                        st.write(f"... und {len(files_data['metadata']['skipped_files']) - 10} weitere")
            
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Fehler bei Dateiextraktion: {str(e)[:200]}")

def _add_file_type_statistics(files_data):
    """Fügt gruppierte Dateitypen-Statistik hinzu"""
    # Hole die Dateitypen-Zählungen
    file_types_data = files_data['metadata'].get('file_types', {})
    
    # Wenn file_types bereits das neue Format hat (mit gruppiert/individuell)
    if isinstance(file_types_data, dict) and "gruppiert" in file_types_data:
        # Neues Format - verwende die bereits gruppierte Statistik
        files_data['metadata']['gruppiert'] = file_types_data.get("gruppiert", {})
    else:
        # Altes Format oder Fallback: Zähle neu basierend auf individual_counts
        individual_counts = file_types_data.get("individuell", {}) if isinstance(file_types_data, dict) else file_types_data
        
        # Initialisiere gruppierte Zählungen
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
        
        # Zähle basierend auf individuellen Dateitypen
        for ext, count in individual_counts.items():
            if isinstance(count, dict):  # Falls count selbst ein Dictionary ist
                count_value = sum(count.values()) if isinstance(count, dict) else count
            else:
                count_value = count
                
            ext_lower = ext.lower()
            
            if ext_lower == ".pdf":
                grouped_counts["PDFs"] += count_value
            elif ext_lower in [".docx", ".doc"]:
                grouped_counts["Word-Dokumente"] += count_value
            elif ext_lower in [".txt", ".md", ".rtf"]:
                grouped_counts["Textdateien"] += count_value
            elif ext_lower in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"]:
                grouped_counts["Bilder"] += count_value
            elif ext_lower in [".py", ".java", ".js", ".html", ".css", ".cpp", ".c", ".php", ".rb", ".go", ".rs"]:
                grouped_counts["Code"] += count_value
            elif ext_lower in [".xlsx", ".xls", ".csv", ".ods"]:
                grouped_counts["Tabellen"] += count_value
            elif ext_lower in [".zip", ".rar", ".7z", ".tar", ".gz"]:
                grouped_counts["Archive"] += count_value
            elif ext_lower in [".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv"]:
                grouped_counts["Media"] += count_value
            elif ext_lower in [".exe", ".msi", ".dmg", ".app", ".bat", ".cmd"]:
                grouped_counts["Ausführbare Dateien"] += count_value
            else:
                grouped_counts["Sonstige"] += count_value
        
        # Entferne leere Kategorien
        grouped_counts = {k: v for k, v in grouped_counts.items() if v > 0}
        
        # Speichere in Metadaten - vereinfacht für die Anzeige
        files_data['metadata']['gruppiert'] = grouped_counts

def render_step2(file_processor):
    """Rendert Schritt 2: KI-Analyse"""
    with st.container():
        st.subheader("🤖 2. KI-Analyse")
        
        files_data = get_state('files_data')
        
        if files_data:
            files_count = files_data["metadata"]["total_files"]
            
            # Verbesserte Success-Anzeige mit Metrics
            col_stats1, col_stats2 = st.columns(2)
            
            with col_stats1:
                st.metric("📁 Dateien verarbeitet", files_count)
            
            # VERBESSERTE DATEITYPEN-ANZEIGE
            file_types_info = files_data["metadata"]
            
            # Zeige gruppierte Statistik in schönerem Format
            if "gruppiert" in file_types_info:
                groups = file_types_info["gruppiert"]
                total_typed = sum(groups.values())
                
                with col_stats2:
                    st.metric("📊 Kategorien erkannt", len(groups))
                
                st.write("**Dateitypen (gruppiert):**")
                
                # Erstelle Fortschrittsbalken für jeden Dateityp
                for group, count in sorted(groups.items(), key=lambda x: x[1], reverse=True):
                    percentage = (count / total_typed * 100) if total_typed > 0 else 0
                    st.write(f"**{group}**: {count} ({percentage:.0f}%)")
                    st.progress(percentage / 100, text=f"{count}")
        else:
            st.info("👈 Bitte laden Sie zuerst Dateien in Schritt 1 hoch")

def render_step3(file_processor):
    """Rendert Schritt 3: Dateiorganisation"""
    with st.container():
        st.subheader("📁 3. Dateien organisieren")
        
        files_data = get_state('files_data')
        categories = get_state('categories')
        
        if not files_data:
            st.info("👈 Bitte laden Sie zuerst Dateien in Schritt 1 hoch")
            return
        
        # Analyse-Buttons wenn noch keine Kategorien vorhanden
        if not categories or 'results' not in categories:
            st.write("**KI-Kategorisierung starten:**")
            
            col_api, col_detail = st.columns(2)
            
            with col_api:
                api_key = st.text_input(
                    "🔑 Groq API Key",
                    type="password",
                    value=get_state('api_key', ''),
                    key="api_key_step3"
                )
                if api_key:
                    update_state('api_key', api_key)
            
            with col_detail:
                detail_level = st.selectbox(
                    "📊 Detail-Level",
                    ["wenig", "mittel", "viel"],
                    index=["wenig", "mittel", "viel"].index(get_state('detail_level', 'mittel')),
                    key="detail_level_step3"
                )
                update_state('detail_level', detail_level)
            
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                if api_key:
                    if st.button("🤖 Mit KI analysieren", type="primary", use_container_width=True, key="analyze_ai_button"):
                        with st.spinner("⏳ KI analysiert deine Dateien..."):
                            categories = analyze_with_groq(
                                files_data["files"],
                                api_key,
                                detail_level
                            )
                            update_state('categories', categories)
                            update_state('processing_step', 3)
                            st.rerun()
                else:
                    st.button("🤖 API Key benötigt", type="primary", use_container_width=True, disabled=True)
            
            with col_btn2:
                if st.button("📊 Schnelle Kategorien", use_container_width=True, key="simple_categories_button"):
                    with st.spinner("Erstelle Kategorien..."):
                        categories = create_content_based_fallback_categories(files_data["files"], detail_level)
                        update_state('categories', categories)
                        update_state('processing_step', 3)
                        st.rerun()
        
        # Organisierungs-Interface wenn Kategorien vorhanden sind
        if categories and 'results' in categories:
            st.success(f"✅ {len(categories['results'])} Dateien kategorisiert")
            
            # Statistik
            category_counts = {}
            for cat in categories["results"]:
                cat_name = cat["category"]
                category_counts[cat_name] = category_counts.get(cat_name, 0) + 1
            
            st.metric("📂 Kategorien erstellt", len(category_counts))
            
            # Zielverzeichnis
            default_target = str(Path.home() / "Desktop" / "SortierteDateien")
            target_dir = st.text_input(
                "📁 Zielverzeichnis",
                value=default_target,
                placeholder="C:\\Users\\Name\\Desktop\\SortierteDateien",
                key="target_dir_input"
            )
            
            col_org1, col_org2 = st.columns([2, 1])
            
            with col_org1:
                if st.button("🚀 Dateien sortieren & organisieren", type="primary", use_container_width=True):
                    _handle_file_organization(file_processor, target_dir)
            
            with col_org2:
                if st.button("🔄 Neu analysieren", use_container_width=True):
                    update_state('categories', None)
                    update_state('processing_step', 2)
                    st.rerun()

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