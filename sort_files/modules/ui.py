# modules/ui.py - Streamlit UI Komponenten
import streamlit as st
import json
from modules.state import get_state, update_state
from modules.ai_analysis import analyze_with_groq, create_fallback_categories

def render_ui(file_processor):
    """Rendert die gesamte UI"""
    
    # Sidebar
    _render_sidebar()
    
    # Hauptbereich
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        _render_step1(file_processor)
    
    with col2:
        _render_step2(file_processor)
    
    with col3:
        _render_step3(file_processor)
    
    st.markdown("---")
    
    # Vorschauen
    _render_previews()
    
    # Footer
    st.markdown("---")
    st.caption("📂 KI Dateisortierung v3.0 | Modulare Architektur")

def _render_sidebar():
    """Rendert die Sidebar"""
    with st.sidebar:
        st.header("⚙️ Einstellungen")
        
        # API Key
        api_key = st.text_input(
            "Groq API Key",
            type="password",
            value=get_state('api_key', ""),
            on_change=lambda: update_state('api_key', st.session_state.get('api_key_input', ""))
        )
        update_state('api_key_input', api_key)
        
        # Detaillevel
        detail_level = st.selectbox(
            "KI-Detailliertheit",
            ["wenig", "mittel", "viel"],
            index=["wenig", "mittel", "viel"].index(get_state('detail_level', "mittel"))
        )
        update_state('detail_level', detail_level)
        
        # Max Dateien
        max_files = st.slider(
            "Maximale Dateien",
            10, 200, get_state('max_files', 50)
        )
        update_state('max_files', max_files)
        
        # Optionen
        st.write("**Optionen:**")
        col_opt1, col_opt2 = st.columns(2)
        
        with col_opt1:
            clean_names = st.checkbox(
                "Namen bereinigen",
                value=get_state('clean_filenames', True)
            )
            update_state('clean_filenames', clean_names)
        
        with col_opt2:
            skip_zips = st.checkbox(
                "ZIPs überspringen",
                value=get_state('skip_encrypted_zips', True)
            )
            update_state('skip_encrypted_zips', skip_zips)
        
        # Ausführbare Dateien behandeln
        move_exec = st.checkbox(
            "Ausführbare Dateien in Extra-Ordner",
            value=get_state('move_executables', True)
        )
        update_state('move_executables', move_exec)
        
        st.markdown("---")
        st.info("""
        **Unterstützt:**
        • Code: .py, .java, .js
        • Dokumente: .pdf, .docx, .txt
        • Bilder: .jpg, .png, .webp
        • Nicht verarbeitet: .exe, große Dateien
        """)

def _render_step1(file_processor):
    """Rendert Schritt 1: Dateien"""
    st.subheader("📥 1. Dateien")
    
    upload_option = st.radio(
        "Quelle",
        ["Hochladen", "Verzeichnis"],
        horizontal=True,
        label_visibility="collapsed"
    )
    
    uploaded_files = None
    input_dir = None
    
    if upload_option == "Hochladen":
        uploaded_files = st.file_uploader(
            "Dateien auswählen",
            accept_multiple_files=True,
            type=["pdf", "docx", "txt", "jpg", "png", "py", "java", "zip"],
            label_visibility="collapsed"
        )
    else:
        input_dir = st.text_input(
            "Verzeichnispfad",
            value="",
            placeholder="C:\\Pfad\\zum\\Ordner",
            label_visibility="collapsed"
        )
    
    if st.button("📥 Dateien extrahieren", type="primary", use_container_width=True):
        _handle_file_extraction(file_processor, uploaded_files, input_dir)

def _handle_file_extraction(file_processor, uploaded_files, input_dir):
    """Behandelt Dateiextraktion"""
    if (not uploaded_files or len(uploaded_files) == 0) and not input_dir:
        st.warning("Bitte Dateien hochladen oder Verzeichnis angeben")
        return
    
    with st.spinner("Extrahiere Dateien..."):
        try:
            # Temporäres Verzeichnis
            temp_dir = file_processor.create_temp_directory()
            
            if uploaded_files:
                # Hochgeladene Dateien speichern
                for uploaded_file in uploaded_files:
                    file_path = temp_dir / uploaded_file.name
                    with open(file_path, 'wb') as f:
                        f.write(uploaded_file.getbuffer())
                
                # ZIPs extrahieren
                zip_files = [f for f in uploaded_files if f.name.lower().endswith('.zip')]
                for zip_file in zip_files:
                    extracted, skipped = file_processor.safe_extract_zip(
                        zip_file.getbuffer(), 
                        temp_dir
                    )
                    if skipped:
                        st.info(f"Übersprungen: {len(skipped)} Dateien")
                
                source_path = temp_dir
            else:
                source_path = Path(input_dir)
            
            # Prüfe Verzeichnis
            if not source_path.exists():
                st.error(f"Verzeichnis existiert nicht: {source_path}")
                return
            
            # Dateien umbenennen
            if get_state('clean_filenames'):
                renamed = file_processor.rename_files_in_directory(source_path)
            
            # Inhalte extrahieren
            max_files = get_state('max_files', 50)
            files_result = file_processor.extract_all_files(source_path, max_files)
            
            if files_result["metadata"]["total_files"] > 0:
                update_state('files_data', files_result)
                update_state('processing_step', 2)
                st.success(f"{files_result['metadata']['total_files']} Dateien verarbeitet")
                
                # Zeige nicht verarbeitete Dateien
                processed_count = sum(1 for f in files_result["files"] if f.get("is_processed", True))
                not_processed = len(files_result["files"]) - processed_count
                if not_processed > 0:
                    st.info(f"{not_processed} Dateien nicht verarbeitet (in Extra-Ordner)")
            else:
                st.warning("Keine Dateien gefunden")
                
        except Exception as e:
            st.error(f"Fehler: {str(e)}")
        
        st.rerun()

def _render_step2(file_processor):
    """Rendert Schritt 2: KI-Analyse"""
    st.subheader("🤖 2. KI-Analyse")
    
    files_data = get_state('files_data')
    
    if files_data:
        files_count = files_data["metadata"]["total_files"]
        st.success(f"✅ {files_count} Dateien")
        
        # Dateitypen
        file_types = files_data["metadata"]["file_types"]
        if file_types:
            st.write(f"**{len(file_types)} Dateitypen:**")
            for ext, count in list(sorted(file_types.items()))[:3]:
                st.write(f"  {ext or '(ohne)'}: {count}")
        
        # KI-Analyse Buttons
        api_key = get_state('api_key', "")
        detail_level = get_state('detail_level', "mittel")
        
        if api_key:
            if st.button("🤖 Mit KI analysieren", type="primary", use_container_width=True):
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
            
            if st.button("📊 Einfache Kategorien", use_container_width=True):
                with st.spinner("Erstelle Kategorien..."):
                    categories = create_fallback_categories(files_data["files"])
                    update_state('categories', categories)
                    update_state('processing_step', 3)
                    st.rerun()
    else:
        st.info("⏳ Dateien extrahieren")

def _render_step3(file_processor):
    """Rendert Schritt 3: Organisieren"""
    st.subheader("📁 3. Organisieren")
    
    categories = get_state('categories')
    
    if categories:
        cat_count = len(categories["results"])
        st.success(f"✅ {cat_count} Kategorien")
        
        # Zielverzeichnis
        import os
        from pathlib import Path
        default_target = str(Path.home() / "Desktop" / "Sortierte_Dateien")
        target_dir = st.text_input(
            "Zielordner",
            value=default_target,
            placeholder="Pfad für sortierte Dateien"
        )
        
        if st.button("📁 Dateien sortieren", type="primary", use_container_width=True):
            if not target_dir.strip():
                st.warning("Bitte Zielordner angeben")
            else:
                _handle_file_organization(file_processor, target_dir)
    else:
        st.info("⏳ KI-Analyse durchführen")

def _handle_file_organization(file_processor, target_dir):
    """Behandelt Dateiorganisation"""
    with st.spinner("Sortiere Dateien..."):
        # Quellverzeichnis bestimmen
        temp_dir = get_state('temp_dir')
        files_data = get_state('files_data')
        categories = get_state('categories')
        
        if temp_dir:
            source_dir = temp_dir
        else:
            source_dir = None
        
        if source_dir and files_data and categories:
            # Dateien sortieren
            stats = file_processor.organize_files(
                files_data["files"],
                categories,
                source_dir,
                target_dir
            )
            
            # Nicht verarbeitete Dateien kopieren
            not_processed_count = file_processor.copy_not_processed_files(target_dir)
            
            # Ergebnis
            st.success(f"✅ {stats['moved']} Dateien sortiert")
            
            if not_processed_count > 0:
                st.info(f"📁 {not_processed_count} nicht verarbeitete Dateien kopiert")
            
            if stats['errors'] > 0:
                st.warning(f"⚠ {stats['errors']} Fehler aufgetreten")
            
            # Download Optionen
            st.write("**Ergebnisse herunterladen:**")
            col_dl1, col_dl2 = st.columns(2)
            
            with col_dl1:
                cat_json = json.dumps(categories, indent=2)
                st.download_button("📥 Kategorien", cat_json, "kategorien.json")
            
            with col_dl2:
                files_json = json.dumps(files_data, indent=2)
                st.download_button("📥 Dateiliste", files_json, "dateiliste.json")
            
            # Cleanup
            if st.button("🗑️ Temporäre Dateien löschen"):
                file_processor.cleanup_temp_directory()
                st.success("Aufgeräumt")
                st.rerun()

def _render_previews():
    """Rendert Datei- und Kategorievorschauen"""
    files_data = get_state('files_data')
    categories = get_state('categories')
    
    if files_data:
        _render_file_preview(files_data["files"])
    
    if categories:
        _render_categories_preview(categories)

def _render_file_preview(files):
    """Rendert Dateivorschau"""
    if not files or len(files) == 0:
        return
    
    with st.expander(f"📋 Dateivorschau ({len(files)} Dateien)", expanded=False):
        # Statistik
        processed = sum(1 for f in files if f.get("is_processed", True))
        not_processed = len(files) - processed
        
        st.write(f"**Statistik:** {processed} verarbeitet, {not_processed} nicht verarbeitet")
        
        # Erste 5 Dateien anzeigen
        for i, file_data in enumerate(files[:5]):
            with st.container():
                col1, col2 = st.columns([1, 3])
                
                with col1:
                    ext = file_data["extension"]
                    icon = "📄"
                    if ext in [".py", ".java", ".js"]:
                        icon = "💻"
                    elif ext in [".jpg", ".png", ".webp"]:
                        icon = "🖼️"
                    elif ext == ".pdf":
                        icon = "📕"
                    
                    status = "✅" if file_data.get("is_processed", True) else "⏸️"
                    st.markdown(f"**{status} {icon} {file_data['filename'][:25]}**")
                    st.caption(f"Typ: {ext}")
                
                with col2:
                    preview = file_data["text_preview"]
                    if preview and len(preview) > 10:
                        if len(preview) > 150:
                            preview = preview[:150]