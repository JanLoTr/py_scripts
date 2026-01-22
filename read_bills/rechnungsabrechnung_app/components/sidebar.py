"""
Seitenleisten-Komponente
"""
import streamlit as st

def render_sidebar():
    """
    Rendert die Seitenleiste
    """
    with st.sidebar:
        st.title("Einstellungen")
        
        # Navigation
        page = st.radio(
            "Wähle eine Seite:",
            ["Dashboard", "Rechnungen verarbeiten", "Verlauf", "Einstellungen"]
        )
        
        st.divider()
        
        # OCR-Einstellungen
        st.subheader("OCR-Einstellungen")
        language = st.multiselect(
            "OCR-Sprache",
            ["Deutsch", "Englisch", "Französisch"],
            default=["Deutsch", "Englisch"]
        )
        
        # Export-Optionen
        st.subheader("Export")
        export_format = st.selectbox(
            "Export-Format",
            ["CSV", "Excel", "PDF", "JSON"]
        )
        
        return page, language, export_format

def render_help():
    """
    Rendert Hilfe-Informationen
    """
    with st.sidebar:
        st.divider()
        st.subheader("Hilfe")
        if st.button("📖 Dokumentation"):
            st.info("Dokumentation wird hier angezeigt")
        if st.button("❓ FAQ"):
            st.info("FAQ wird hier angezeigt")
