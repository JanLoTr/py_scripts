"""
Rechnungsanzeige-Komponente
"""
import streamlit as st
from pathlib import Path
from PIL import Image

def render_invoice_viewer(file_path: Path):
    """
    Rendert die Rechnungsanzeige
    
    Args:
        file_path: Pfad zur Rechnungsdatei
    """
    st.subheader("👁️ Rechnungsvorschau")
    
    try:
        # Überprüfe Dateityp
        if file_path.suffix.lower() in ['.pdf']:
            st.info("PDF-Vorschau wird hier angezeigt")
        elif file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.tiff']:
            image = Image.open(file_path)
            st.image(image, use_container_width=True, caption=file_path.name)
        else:
            st.warning("Dateityp wird nicht unterstützt")
    except Exception as e:
        st.error(f"Fehler beim Anzeigen der Datei: {e}")

def render_invoice_info(invoice_data: dict):
    """
    Rendert Rechnungsinformationen
    
    Args:
        invoice_data: Rechnungsdaten als Dictionary
    """
    st.subheader("ℹ️ Rechnungsinformationen")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Rechnungsnummer:**", invoice_data.get("number", "N/A"))
        st.write("**Datum:**", invoice_data.get("date", "N/A"))
        st.write("**Lieferant:**", invoice_data.get("vendor", "N/A"))
    
    with col2:
        st.write("**Betrag:**", invoice_data.get("amount", "N/A"))
        st.write("**Zahlungsbedingungen:**", invoice_data.get("terms", "N/A"))
        st.write("**Status:**", invoice_data.get("status", "N/A"))
