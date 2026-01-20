# modules/ui/main.py - Haupt-UI
import streamlit as st
from modules.state import get_state
from .sidebar import render_sidebar
from .steps import render_step1, render_step2, render_step3
from .previews import render_previews
from .downloads import render_persistent_downloads

def render_ui(file_processor):
    """Rendert die gesamte UI"""
    
    # Sidebar
    render_sidebar()
    
    # Hauptbereich
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        render_step1(file_processor)
    
    with col2:
        render_step2(file_processor)
    
    with col3:
        render_step3(file_processor)
    
    st.markdown("---")
    
    # Vorschauen
    render_previews(file_processor)
    
    # PERSISTIERENDE DOWNLOAD-BUTTONS
    render_persistent_downloads()
    
    # Footer
    st.markdown("---")
    st.caption("📂 KI Dateisortierung v3.2 | Verbesserte Dateitypen-Anzeige & Kompakte Vorschau")