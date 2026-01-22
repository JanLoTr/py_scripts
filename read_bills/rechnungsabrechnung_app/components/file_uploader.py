"""
Dateiupload-Komponente
"""
import streamlit as st
from pathlib import Path
from utils.file_utils import save_uploaded_file
from config import UPLOAD_DIR

def render_file_uploader():
    """
    Rendert die Dateiupload-Komponente
    """
    st.subheader("📄 Rechnungsdatei hochladen")
    
    uploaded_file = st.file_uploader(
        "Wähle eine Rechnungsdatei",
        type=["pdf", "png", "jpg", "jpeg", "tiff"],
        help="Unterstützte Formate: PDF, PNG, JPG, JPEG, TIFF"
    )
    
    if uploaded_file is not None:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Dateigröße", f"{len(uploaded_file.getbuffer()) / 1024:.2f} KB")
        
        with col2:
            st.metric("Dateityp", uploaded_file.type)
        
        with col3:
            if st.button("✅ Verarbeiten", key="process_button"):
                with st.spinner("Datei wird verarbeitet..."):
                    file_path = save_uploaded_file(uploaded_file, UPLOAD_DIR)
                    if file_path:
                        st.success(f"Datei gespeichert: {file_path.name}")
                        return file_path
    
    return None
