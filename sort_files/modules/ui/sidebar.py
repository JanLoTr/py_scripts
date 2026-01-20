# modules/ui/sidebar.py
import streamlit as st
from modules.state import get_state, update_state

def render_sidebar():
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
        
        # Max Dateien - STANDARD AUF 100
        max_files = st.slider(
            "Maximale Dateien",
            10, 300, get_state('max_files', 100),
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
        
        **Standard:** 100 Dateien werden verarbeitet
        **PDFs:** Bis zu 10 Seiten werden analysiert
        """)