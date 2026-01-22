# modules/ui/sidebar.py
import streamlit as st
from modules.state import get_state, update_state

def render_sidebar():
    """Rendert die Sidebar mit besserer Organisation"""
    with st.sidebar:
        st.markdown("---")
        st.header("⚙️ Einstellungen & Konfiguration")
        st.markdown("---")
        
        # Section 1: API-Einstellungen
        st.write("### 🔐 API-Einstellungen")
        api_key = st.text_input(
            "Groq API Key",
            type="password",
            value=get_state('api_key', ""),
            key="api_key_input",
            help="Holen Sie einen kostenlosen API Key von https://groq.com"
        )
        update_state('api_key', api_key)
        
        if not api_key:
            st.info("🔑 **Hinweis:** Ohne API Key können nur schnelle Fallback-Kategorien verwendet werden.")
        
        st.markdown("---")
        
        # Section 2: KI-Parameter
        st.write("### 🤖 Ordner-Strukturierung")
        
        detail_level = st.selectbox(
            "Wieviele Ordner möchtest du?",
            ["wenig", "mittel", "viel"],
            index=["wenig", "mittel", "viel"].index(get_state('detail_level', "mittel")),
            key="detail_level_select",
            help="Wie viele spezifische Unterordner sollen erstellt werden?"
        )
        update_state('detail_level', detail_level)
        
        st.markdown("---")
        
        # Section 3: Dateinamen-Optionen
        st.write("### 📝 Dateinamen-Optionen")
        
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
                help="Ersetzt Umlaute für bessere Kompatibilität"
            )
            update_state('replace_umlauts', replace_umlauts)
        
        st.markdown("---")
        
        # Section 4: Verarbeitungs-Optionen
        st.write("### ⚙️ Verarbeitungs-Optionen")
        col_opt1, col_opt2 = st.columns(2)
        
        with col_opt1:
            skip_zips = st.checkbox(
                "ZIPs überspringen",
                value=get_state('skip_encrypted_zips', True),
                key="skip_zips_checkbox",
                help="Verschlüsselte ZIPs ignorieren"
            )
            update_state('skip_encrypted_zips', skip_zips)
        
        with col_opt2:
            move_exec = st.checkbox(
                "Ausführbare Dateien",
                value=get_state('move_executables', True),
                key="move_exec_checkbox",
                help="Verschiebe .exe/.msi Dateien separat"
            )
            update_state('move_executables', move_exec)
        
        st.markdown("---")
        
        # Section 5: Hilfe & Informationen
        st.write("### ℹ️ Hilfe & Infos")
        
        with st.expander("📚 Detaillevel erklärt", expanded=False):
            st.markdown("""
            **Wenig Ordner**: 5-8 breite Kategorien
            - Alles in wenigen Hauptordnern
            - Beispiel: "Dokumente", "Bilder", "Projekte"
            - Gut für schnelle Übersicht
            
            **Mittel**: 10-15 Unterordner
            - Balance zwischen Übersicht & Struktur
            - Beispiel: "Schule/Mathematik", "Arbeit/Projekte", "Finanzen/Steuern"
            - **Empfohlen für die meisten**
            
            **Viel Ordner**: 20+ spezifische Unterordner
            - Sehr detaillierte Ordnerstruktur
            - Beispiel: "FH/Diplomarbeit", "HTL/Betriebswirtschaft", "Finanzen/Stromrechnung"
            - Gut wenn du eine sehr spezifische Struktur haben möchtest
            """)
        
        with st.expander("🔑 API Key Setup", expanded=False):
            st.markdown("""
            1. Besuchen Sie https://console.groq.com
            2. Erstellen Sie einen kostenlosen Account
            3. Generieren Sie einen API Key
            4. Kopieren Sie den Key in das Feld oben
            
            **Kostenlos und schnell! 🚀**
            """)
        
        with st.expander("💡 Tipps & Tricks", expanded=False):
            st.markdown("""
            - **Standard:** 100 Dateien werden verarbeitet
            - **PDFs:** Bis zu 15 Seiten werden analysiert
            - **OCR:** Gescannte PDFs werden automatisch erkannt
            - **HTL/FH:** Intelligente Unterscheidung für Ihr Profil
            """)
        
        st.markdown("---")
        st.caption("📂 KI Dateisortierung v3.3 | Mit HTL/FH Intelligenz")