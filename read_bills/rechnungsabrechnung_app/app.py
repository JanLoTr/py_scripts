"""
Haupt-Streamlit-App für Rechnungsabrechnung mit Bruder
"""
import streamlit as st
import pandas as pd
from pathlib import Path
from PIL import Image
import pytesseract
from utils.file_utils import save_uploaded_file, delete_file
from utils.text_processing import clean_ocr_text, split_into_lines
from utils.groq_utils import initialize_groq_client, extract_invoice_products
from config import UPLOAD_DIR

# Seitenkonfiguration
st.set_page_config(
    page_title="Rechnungsabrechnung mit Bruder",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Session State initialisieren
if "api_key" not in st.session_state:
    st.session_state.api_key = ""
if "processed_invoices" not in st.session_state:
    st.session_state.processed_invoices = {}
if "current_invoice" not in st.session_state:
    st.session_state.current_invoice = None

def render_sidebar():
    """Rendert die Seitenleiste mit Einstellungen"""
    with st.sidebar:
        st.title("⚙️ Einstellungen")
        st.divider()
        
        # Groq API Key eingeben
        st.subheader("🤖 Groq API Konfiguration")
        api_key = st.text_input(
            "Groq API Key",
            type="password",
            value=st.session_state.api_key,
            help="Gib deinen Groq API Key ein"
        )
        
        if api_key:
            st.session_state.api_key = api_key
            st.success("✅ API Key eingegeben")
        else:
            st.warning("⚠️ Bitte API Key eingeben")
        
        st.divider()
        
        # Statistiken
        st.subheader("📊 Statistiken")
        total_invoices = len(st.session_state.processed_invoices)
        st.metric("Verarbeitete Rechnungen", total_invoices)
        
        if total_invoices > 0:
            total_amount = sum(inv.get("total_amount", 0) for inv in st.session_state.processed_invoices.values())
            st.metric("Gesamtumsatz", f"€ {total_amount:.2f}")
        
        st.divider()
        
        # Hilfe
        st.subheader("❓ Hilfe")
        with st.expander("Wie funktioniert die App?"):
            st.write("""
            1. **Rechnung hochladen**: Lade ein PDF oder Bild einer Rechnung hoch
            2. **Verarbeitung**: Die KI extrahiert automatisch die Produkte und Preise
            3. **Überprüfung**: Prüfe die erkannten Daten und korrigiere bei Bedarf
            4. **Export**: Exportiere die abgerechneten Daten
            
            **Hinweise:**
            - Aktionen-Preise werden automatisch ignoriert
            - Preise werden immer von der Rechnung übernommen
            - Unerkannte Produkte werden als "unerkenntlich" markiert
            """)

def extract_text_from_file(file_path):
    """Extrahiert Text aus einer Datei mittels OCR"""
    try:
        if file_path.suffix.lower() == '.pdf':
            # Hier würde PDF-Verarbeitung erfolgen (z.B. mit pdf2image)
            st.info("PDF-Verarbeitung wird noch implementiert. Bitte konvertiere zu PNG/JPG.")
            return None
        elif file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.tiff']:
            image = Image.open(file_path)
            # Bildvorverarbeitung
            text = pytesseract.image_to_string(image, lang="deu+eng")
            return text
        else:
            st.error("Nicht unterstütztes Dateiformat")
            return None
    except Exception as e:
        st.error(f"Fehler beim Extrahieren des Texts: {e}")
        return None

def process_invoice(file_path, raw_text, api_key):
    """Verarbeitet eine Rechnung mit Groq KI"""
    try:
        client = initialize_groq_client(api_key)
        if not client:
            st.error("Groq Client konnte nicht initialisiert werden")
            return None
        
        # Extrahiere Produkte
        products = extract_invoice_products(client, raw_text)
        return products
    except Exception as e:
        st.error(f"Fehler bei der Verarbeitung: {e}")
        return None

def main():
    st.title("💰 Rechnungsabrechnung mit Bruder")
    st.write("Lade Rechnungen hoch und lass die KI die Produkte und Preise intelligent erkennen.")
    
    # Seitenleiste rendern
    render_sidebar()
    
    # Hauptbereich
    st.divider()
    
    # Tab 1: Neue Rechnung verarbeiten
    tab1, tab2 = st.tabs(["📥 Neue Rechnung", "📋 Verlauf"])
    
    with tab1:
        st.subheader("Rechnung hochladen und verarbeiten")
        
        uploaded_file = st.file_uploader(
            "Wähle eine Rechnungsdatei",
            type=["pdf", "png", "jpg", "jpeg", "tiff"],
            help="Unterstützte Formate: PDF, PNG, JPG, JPEG, TIFF"
        )
        
        if uploaded_file is not None:
            # Speichere die hochgeladene Datei
            file_path = save_uploaded_file(uploaded_file, UPLOAD_DIR)
            
            if file_path:
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.subheader("📷 Rechnungsvorschau")
                    try:
                        if file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.tiff']:
                            image = Image.open(file_path)
                            st.image(image, use_container_width=True)
                    except Exception as e:
                        st.error(f"Fehler beim Anzeigen der Vorschau: {e}")
                
                with col2:
                    st.metric("Dateigröße", f"{len(uploaded_file.getbuffer()) / 1024:.2f} KB")
                    st.metric("Dateiformat", uploaded_file.type)
                
                st.divider()
                
                # Verarbeitungsschritt
                if st.button("🚀 Rechnung verarbeiten", use_container_width=True, type="primary"):
                    if not st.session_state.api_key:
                        st.error("❌ Bitte gib den Groq API Key in der Seitenleiste ein!")
                    else:
                        with st.spinner("Extrahiere Text aus Rechnung..."):
                            raw_text = extract_text_from_file(file_path)
                        
                        if raw_text:
                            st.success("✅ Text extrahiert")
                            
                            with st.spinner("Verarbeite mit KI..."):
                                products = process_invoice(file_path, raw_text, st.session_state.api_key)
                            
                            if products:
                                st.success("✅ Verarbeitung abgeschlossen")
                                st.session_state.current_invoice = {
                                    "filename": uploaded_file.name,
                                    "file_path": str(file_path),
                                    "raw_text": raw_text,
                                    "products": products
                                }
                
                # Zeige verarbeitete Daten an
                if st.session_state.current_invoice:
                    st.divider()
                    
                    # Button zum Öffnen der Rechnung
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.subheader("📊 Erkannte Produkte und Preise")
                    with col2:
                        if st.button("📂 Datei öffnen", use_container_width=True):
                            try:
                                file_path = Path(st.session_state.current_invoice["file_path"])
                                if file_path.exists():
                                    with open(file_path, "rb") as f:
                                        st.download_button(
                                            label="💾 Herunterladen",
                                            data=f.read(),
                                            file_name=file_path.name,
                                            mime="image/png" if file_path.suffix.lower() in ['.png', '.jpg', '.jpeg'] else "application/octet-stream",
                                            use_container_width=True
                                        )
                            except Exception as e:
                                st.error(f"Fehler beim Öffnen der Datei: {e}")
                    
                    if st.session_state.current_invoice.get("products"):
                        df = pd.DataFrame(st.session_state.current_invoice["products"])
                        
                        # Bearbeitbare Tabelle
                        edited_df = st.data_editor(
                            df,
                            use_container_width=True,
                            num_rows="dynamic",
                            key="products_editor"
                        )
                        
                        # Zusammenfassung
                        st.divider()
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric("Anzahl Produkte", len(edited_df))
                        
                        with col2:
                            total = edited_df["preis"].astype(float).sum()
                            st.metric("Gesamtbetrag", f"€ {total:.2f}")
                        
                        with col3:
                            st.metric("Gesamt", f"€ {total:.2f}")
                        
                        # Speichern mit Namensgebung
                        st.divider()
                        st.subheader("💾 Speichern")
                        
                        col_save1, col_save2 = st.columns(2)
                        
                        with col_save1:
                            # Auto-Generierung eines Namens vorschlagen
                            from datetime import datetime
                            default_name = f"{datetime.now().strftime('%Y-%m-%d')}_Supermarkt_{total:.2f}€"
                            invoice_name = st.text_input(
                                "Name für die Rechnung",
                                value=default_name,
                                help="Format: Datum_Supermarkt_Preis z.B. 2026-01-22_Edeka_45.50€"
                            )
                        
                        with col_save2:
                            if st.button("💾 Speichern", use_container_width=True, type="primary"):
                                try:
                                    # Speichere CSV mit Produkten
                                    csv_filename = f"{invoice_name}.csv"
                                    csv_path = PROCESSED_DIR / csv_filename
                                    edited_df.to_csv(csv_path, index=False, sep=";")
                                    
                                    # Speichere auch die Original-Scan-Datei
                                    original_file_path = Path(st.session_state.current_invoice["file_path"])
                                    if original_file_path.exists():
                                        scan_extension = original_file_path.suffix
                                        scan_filename = f"{invoice_name}_Scan{scan_extension}"
                                        scan_path = PROCESSED_DIR / scan_filename
                                        
                                        # Kopiere die Datei
                                        import shutil
                                        shutil.copy2(original_file_path, scan_path)
                                    
                                    # Speichere in Session State
                                    st.session_state.processed_invoices[invoice_name] = {
                                        "products": edited_df.to_dict("records"),
                                        "total_amount": total,
                                        "filename": invoice_name,
                                        "csv_path": str(csv_path),
                                        "scan_path": str(scan_path) if original_file_path.exists() else None
                                    }
                                    
                                    st.success(f"✅ Rechnung gespeichert als '{invoice_name}'!")
                                    st.info(f"📁 Speicherort: {PROCESSED_DIR}")
                                    
                                except Exception as e:
                                    st.error(f"❌ Fehler beim Speichern: {e}")
                    else:
                        st.warning("Keine Produkte erkannt. Bitte überprüfe die Eingabe.")
    
    with tab2:
        st.subheader("📋 Verlauf der Rechnungen")
        
        if st.session_state.processed_invoices:
            for filename, invoice_data in st.session_state.processed_invoices.items():
                with st.expander(f"📄 {filename}"):
                    col_info1, col_info2, col_info3 = st.columns(3)
                    
                    df = pd.DataFrame(invoice_data["products"])
                    
                    with col_info1:
                        st.metric("Produkte", len(df))
                    with col_info2:
                        st.metric("Summe", f"€ {invoice_data['total_amount']:.2f}")
                    with col_info3:
                        pass
                    
                    st.dataframe(df, use_container_width=True)
                    
                    # Download-Buttons
                    st.divider()
                    col_dl1, col_dl2, col_dl3 = st.columns(3)
                    
                    with col_dl1:
                        # CSV Download
                        csv_buffer = df.to_csv(index=False, sep=";")
                        st.download_button(
                            label="📥 CSV herunterladen",
                            data=csv_buffer,
                            file_name=f"{filename}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                    
                    with col_dl2:
                        # Scan-Datei Download (wenn vorhanden)
                        if invoice_data.get("scan_path") and Path(invoice_data["scan_path"]).exists():
                            scan_path = Path(invoice_data["scan_path"])
                            with open(scan_path, "rb") as f:
                                st.download_button(
                                    label="📷 Scan herunterladen",
                                    data=f.read(),
                                    file_name=scan_path.name,
                                    mime="image/png",
                                    use_container_width=True
                                )
                    
                    with col_dl3:
                        if st.button("🗑️ Löschen", use_container_width=True, key=f"delete_{filename}"):
                            # Lösche auch die Dateien
                            if invoice_data.get("csv_path"):
                                csv_path = Path(invoice_data["csv_path"])
                                if csv_path.exists():
                                    csv_path.unlink()
                            
                            if invoice_data.get("scan_path"):
                                scan_path = Path(invoice_data["scan_path"])
                                if scan_path.exists():
                                    scan_path.unlink()
                            
                            del st.session_state.processed_invoices[filename]
                            st.rerun()
        else:
            st.info("Keine verarbeiteten Rechnungen vorhanden")

if __name__ == "__main__":
    main()
