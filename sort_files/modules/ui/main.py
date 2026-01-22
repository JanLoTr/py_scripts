# modules/ui/main.py - Haupt-UI
import streamlit as st
from modules.state import get_state
from .sidebar import render_sidebar
from .steps import render_step1, render_step2, render_step3
from .previews import render_previews
from .downloads import render_persistent_downloads

def render_ui(file_processor):
    """Rendert die gesamte UI"""
    
    # Page Config
    st.set_page_config(
        page_title="📂 KI Dateisortierung",
        page_icon="📂",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Sidebar
    render_sidebar()
    
    # Header mit besserer Visualisierung
    st.markdown("""
    <style>
    .main-header {
        text-align: center;
        padding: 20px 0;
        margin-bottom: 30px;
        border-bottom: 3px solid #1f77b4;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<div class='main-header'><h1>📂 KI-gestützte Dateisortierung</h1><p style='color: gray;'>Intelligente Kategorisierung mit Groq AI</p></div>", unsafe_allow_html=True)
    
    # Progress Indicator
    step = get_state('processing_step', 1)
    col_prog1, col_prog2, col_prog3, col_prog4 = st.columns(4)
    
    with col_prog1:
        icon = "✅" if step >= 1 else "⭕"
        color = "green" if step >= 1 else "gray"
        st.markdown(f"<h4 style='color: {color};'>{icon} Dateien</h4>", unsafe_allow_html=True)
    
    with col_prog2:
        icon = "✅" if step >= 2 else "⭕"
        color = "green" if step >= 2 else "gray"
        st.markdown(f"<h4 style='color: {color};'>{icon} Analyse</h4>", unsafe_allow_html=True)
    
    with col_prog3:
        icon = "✅" if step >= 3 else "⭕"
        color = "green" if step >= 3 else "gray"
        st.markdown(f"<h4 style='color: {color};'>{icon} Kategorien</h4>", unsafe_allow_html=True)
    
    with col_prog4:
        icon = "✅" if step >= 4 else "⭕"
        color = "green" if step >= 4 else "gray"
        st.markdown(f"<h4 style='color: {color};'>{icon} Download</h4>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Hauptbereich - verbesserte Columns
    col1, col2, col3 = st.columns([1, 1, 1], gap="medium")
    
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
    st.markdown("""
    <div style='text-align: center; color: gray; padding: 20px;'>
    📂 KI Dateisortierung v3.3 | Intelligente Sortierung mit HTL/FH Kontext<br>
    Powered by Groq AI | <small>Developed 2026</small>
    </div>
    """, unsafe_allow_html=True)