# modules/ui.py - Streamlit UI Komponenten (mit persistierenden Downloads)
import streamlit as st
import json
import time
from pathlib import Path
from modules.state import get_state, update_state
from modules.ai_analysis import analyze_with_groq, create_content_based_fallback_categories

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
    _render_previews(file_processor)
    
    # PERSISTIERENDE DOWNLOAD-BUTTONS
    _render_persistent_downloads()
    
    # Footer
    st.markdown("---")
    st.caption("📂 KI Dateisortierung v3.1 | Verbesserte Namensbereinigung & Persistente Downloads")

def _render_sidebar():
    """Rendert die Sidebar"""
    with st.sidebar:
        st.header("⚙️ Einstellungen")
        
        # API Key
        api_key = st.text_input(
            "Groq API Key",
            type="password",
            value=get_state('api_key', ""),
            key="api_key_input"
        )
        update_state('api_key', api_key)
        
        # Detaillevel
        detail_level = st.selectbox(
            "KI-Detailliertheit",
            ["wenig", "mittel", "viel"],
            index=["wenig", "mittel", "viel"].index(get_state('detail_level', "mittel")),
            key="detail_level_select"
        )
        update_state('detail_level', detail_level)
        
        # Max Dateien
        max_files = st.slider(
            "Maximale Dateien",
            10, 200, get_state('max_files', 50),
            key="max_files_slider"
        )
        update_state('max_files', max_files)
        
        # Optionen
        st.write("**Dateinamen-Optionen:**")
        
        clean_names = st.checkbox(
            "Dateinamen bereinigen",
            value=get_state('clean_filenames', True),
            key="clean_names_checkbox",
            help="Entfernt Sonderzeichen aus Dateinamen"
        )
        update_state('clean_filenames', clean_names)
        
        if clean_names:
            replace_umlauts = st.checkbox(
                "Umlaute ersetzen (ä→ae, ö→oe, ü→ue, ß→ss)",
                value=get_state('replace_umlauts', False),
                key="replace_umlauts_checkbox",
                help="Ersetzt Umlaute durch ae/oe/ue für bessere Kompatibilität"
            )
            update_state('replace_umlauts', replace_umlauts)
        
        st.write("**Verarbeitungs-Optionen:**")
        col_opt1, col_opt2 = st.columns(2)
        
        with col_opt1:
            skip_zips = st.checkbox(
                "ZIPs überspringen",
                value=get_state('skip_encrypted_zips', True),
                key="skip_zips_checkbox"
            )
            update_state('skip_encrypted_zips', skip_zips)
        
        with col_opt2:
            move_exec = st.checkbox(
                "Ausführbare Dateien",
                value=get_state('move_executables', True),
                key="move_exec_checkbox"
            )
            update_state('move_executables', move_exec)
        
        st.markdown("---")
        st.info("""
        **Detaillevel erklärt:**
        • **Wenig**: 5-8 breite Kategorien
        • **Mittel**: 10-15 spezifischere Kategorien  
        • **Viel**: 20+ sehr spezifische Kategorien
        
        **KI analysiert DateiINHALT!**
        """)

# ... [restliche Funktionen bleiben gleich bis _handle_file_organization] ...

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
            
            # DOWNLOAD-DATEN VORBEREITEN UND SPEICHERN
            _prepare_and_store_download_data(categories, files_data)
            
            # Cleanup
            if st.button("🗑️ Temporäre Dateien löschen", key="cleanup_button_after_sort"):
                file_processor.cleanup_temp_directory()
                st.success("Aufgeräumt")
                st.rerun()

def _prepare_and_store_download_data(categories, files_data):
    """Bereitet Download-Daten vor und zeigt persistente Buttons"""
    if categories:
        # JSON für Download vorbereiten
        categories_json = json.dumps(categories, indent=2, ensure_ascii=False)
        categories_filename = f"kategorien_{time.strftime('%Y%m%d_%H%M%S')}.json"
        
        # Im Session State speichern
        update_state('download_categories_json', categories_json)
        update_state('download_categories_filename', categories_filename)
    
    if files_data:
        # JSON für Download vorbereiten
        files_json = json.dumps(files_data, indent=2, ensure_ascii=False)
        files_filename = f"dateiliste_{time.strftime('%Y%m%d_%H%M%S')}.json"
        
        # Im Session State speichern
        update_state('download_files_json', files_json)
        update_state('download_files_filename', files_filename)
    
    # Download-Buttons anzeigen
    update_state('show_download_buttons', True)

def _render_persistent_downloads():
    """Rendert persistente Download-Buttons (bleiben sichtbar)"""
    if not get_state('show_download_buttons', False):
        return
    
    st.markdown("---")
    st.subheader("💾 Ergebnisse herunterladen")
    
    # Download-Buttons in einer stabilen Container-Struktur
    col1, col2 = st.columns(2)
    
    with col1:
        categories_json = get_state('download_categories_json')
        categories_filename = get_state('download_categories_filename', "kategorien.json")
        
        if categories_json:
            st.download_button(
                label="📥 Kategorien als JSON",
                data=categories_json,
                file_name=categories_filename,
                mime="application/json",
                key="persistent_download_categories",
                use_container_width=True
            )
        else:
            st.button(
                "📥 Kategorien (nicht verfügbar)",
                disabled=True,
                use_container_width=True
            )
    
    with col2:
        files_json = get_state('download_files_json')
        files_filename = get_state('download_files_filename', "dateiliste.json")
        
        if files_json:
            st.download_button(
                label="📥 Dateiliste als JSON",
                data=files_json,
                file_name=files_filename,
                mime="application/json",
                key="persistent_download_files",
                use_container_width=True
            )
        else:
            st.button(
                "📥 Dateiliste (nicht verfügbar)",
                disabled=True,
                use_container_width=True
            )
    
    # Zusätzlich: Umgbenannte Dateien anzeigen
    renamed_files = get_state('renamed_files', [])
    if renamed_files:
        with st.expander(f"📝 Umbenannte Dateien ({len(renamed_files)})"):
            for old_name, new_name in renamed_files[:10]:  # Zeige nur erste 10
                st.write(f"• **{old_name}** → {new_name}")
            
            if len(renamed_files) > 10:
                st.info(f"Und {len(renamed_files) - 10} weitere...")
            
            # Download der Umbenennungsliste
            renamed_data = json.dumps(renamed_files, indent=2, ensure_ascii=False)
            st.download_button(
                label="📥 Umbenennungsliste",
                data=renamed_data,
                file_name=f"umbenennungen_{time.strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key="download_renamed",
                use_container_width=True
            )

# ... [restliche Funktionen bleiben gleich] ...