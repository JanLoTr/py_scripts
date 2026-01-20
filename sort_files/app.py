# app.py - Hauptdatei der Streamlit App
import streamlit as st
from modules.ui import render_ui
from modules.state import init_session_state
from modules.file_handling import FileProcessor
import traceback

# -------------------- Hauptfunktion --------------------
def main():
    """Hauptfunktion der Streamlit App"""
    st.set_page_config(
        page_title="KI Dateisortierung",
        page_icon="📂",
        layout="wide"
    )
    
    # Session State initialisieren
    init_session_state()
    
    # Titel
    st.title("📂 KI-gestützte Dateisortierung")
    st.markdown("Sortiere Dateien automatisch mit KI-Kategorisierung")
    st.markdown("---")
    
    # FileProcessor initialisieren
    file_processor = FileProcessor()
    
    try:
        # UI rendern
        render_ui(file_processor)
        
    except Exception as e:
        st.error(f"Ein Fehler ist aufgetreten: {str(e)}")
        st.code(traceback.format_exc())
        st.info("Bitte starte die App neu oder kontaktiere den Support.")

# -------------------- Start --------------------
if __name__ == "__main__":
    main()