import streamlit as st
import pandas as pd
import json
from pathlib import Path
import pdfplumber
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
import re
import os
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from io import BytesIO
import base64
import shutil

# ============ KONFIGURATION ============
st.set_page_config(
    page_title="Rechnungsmanager",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Tesseract OCR Pfad (Windows)
try:
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
except:
    # Für andere Betriebssysteme
    pass

# ============ HILFSFUNKTIONEN ============
def init_session_state():
    """Initialisiert Session State Variablen"""
    if 'invoices_data' not in st.session_state:
        st.session_state.invoices_data = []
    if 'processed_files' not in st.session_state:
        st.session_state.processed_files = []
    if 'products_df' not in st.session_state:
        st.session_state.products_df = pd.DataFrame()
    if 'invoice_df' not in st.session_state:
        st.session_state.invoice_df = pd.DataFrame()
    if 'summary_df' not in st.session_state:
        st.session_state.summary_df = pd.DataFrame()
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = []

def clean_ocr_text(text):
    """Bereinigt OCR-Fehler"""
    replacements = {
        '|': '1', 'O': '0', 'o': '0', 'I': '1', 'l': '1',
        'Z': '2', 'S': '5', 'B': '8', '€': 'EUR', '£': 'EUR',
        '$': 'EUR', ',,': ',', '..': '.'
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return text

def extract_text_from_pdf(pdf_path, max_pages=5):
    """Extrahiert Text aus PDF"""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i in range(min(len(pdf.pages), max_pages)):
                page = pdf.pages[i]
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    text += page_text + "\n"
                else:
                    try:
                        images = convert_from_path(pdf_path, first_page=i+1, last_page=i+1)
                        for img in images:
                            text += pytesseract.image_to_string(img, lang='deu+eng') + "\n"
                    except:
                        pass
    except Exception as e:
        st.warning(f"Fehler bei PDF: {e}")
    
    return clean_ocr_text(text.strip())

def extract_text_from_image(image_file):
    """Extrahiert Text aus Bild"""
    try:
        img = Image.open(image_file)
        text = pytesseract.image_to_string(img, lang='deu+eng')
        return clean_ocr_text(text.strip())
    except Exception as e:
        st.warning(f"Fehler bei Bild: {e}")
        return ""

def extract_metadata(text):
    """Extrahiert Metadaten aus Rechnungstext"""
    # Shop-Erkennung
    shops = {
        'REWE': 'REWE', 'EDEKA': 'EDEKA', 'ALDI': 'ALDI', 'LIDL': 'LIDL',
        'KAUFLAND': 'KAUFLAND', 'NETTO': 'NETTO', 'PENNY': 'PENNY',
        'DM': 'DM', 'ROSSMANN': 'ROSSMANN', 'TEGUT': 'TEGUT',
        'BAUHAUS': 'BAUHAUS', 'HORNBACH': 'HORNBACH', 'ALNATURA': 'ALNATURA'
    }
    
    text_upper = text.upper()
    shop = "Unbekannt"
    for keyword, name in shops.items():
        if keyword in text_upper:
            shop = name
            break
    
    # Datum-Erkennung
    date_patterns = [
        r'(\d{1,2})[\.\/](\d{1,2})[\.\/](\d{2,4})',
        r'(\d{1,2})\.\s*([A-Za-z]+)\s*\.?\s*(\d{2,4})',
        r'(\d{1,2})[\.\-](\d{1,2})[\.\-](\d{2,4})',
    ]
    
    date_str = datetime.now().strftime("%d.%m.%Y")
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            try:
                parts = match.groups()
                if len(parts) == 3:
                    day, month, year = parts
                    if len(year) == 2:
                        year = '20' + year
                    # Monatsnamen zu Zahlen
                    month_names = {
                        'JAN': '01', 'JANUAR': '01',
                        'FEB': '02', 'FEBRUAR': '02',
                        'MÄR': '03', 'MÄRZ': '03', 'MAR': '03',
                        'APR': '04', 'APRIL': '04',
                        'MAI': '05', 'MAY': '05',
                        'JUN': '06', 'JUNI': '06',
                        'JUL': '07', 'JULI': '07',
                        'AUG': '08', 'AUGUST': '08',
                        'SEP': '09', 'SEPTEMBER': '09',
                        'OKT': '10', 'OKTOBER': '10', 'OCT': '10',
                        'NOV': '11', 'NOVEMBER': '11',
                        'DEZ': '12', 'DEZEMBER': '12', 'DEC': '12'
                    }
                    if month.upper() in month_names:
                        month = month_names[month.upper()]
                    date_str = f"{day}.{month}.{year}"
                    break
            except:
                pass
    
    # Betrag-Erkennung
    amounts = []
    patterns = [
        r'(\d+[,\.]\d{2})\s*[€$£]?',
        r'[€$£]\s*(\d+[,\.]\d{2})',
        r'SUMME[:\s]*(\d+[,\.]\d{2})',
        r'TOTAL[:\s]*(\d+[,\.]\d{2})',
        r'ZUZAHLEN[:\s]*(\d+[,\.]\d{2})',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                amount = float(match.replace(',', '.'))
                if amount > 0 and amount < 10000:
                    amounts.append(amount)
            except:
                pass
    
    total = max(amounts) if amounts else 0
    
    return {
        'shop': shop,
        'date': date_str,
        'total': total,
        'all_amounts': amounts,
        'text_preview': text[:500] + "..." if len(text) > 500 else text
    }

def parse_products_simple(text):
    """Einfache Produktparsing ohne KI"""
    products = []
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Überspringen von Kopfzeilen
        if (len(line) < 3 or line.startswith(('Rechnung', 'Quittung', 'Kassenzettel', 
                                            'SUMME', 'TOTAL', 'EUR', '€', 'MwSt', 'UST'))):
            continue
        
        # Suche nach Preis
        price_match = re.search(r'(\d+[,\.]\d{2})\s*[A-Z]?$', line)
        if price_match:
            try:
                price = float(price_match.group(1).replace(',', '.'))
                
                # Produktname (alles vor dem Preis)
                product_name = line[:price_match.start()].strip()
                
                # Menge extrahieren
                quantity = 1
                qty_match = re.search(r'^(\d+[,\.]?\d*)\s*[xX\*]', product_name)
                if qty_match:
                    try:
                        quantity = float(qty_match.group(1).replace(',', '.'))
                        product_name = product_name[qty_match.end():].strip()
                    except:
                        pass
                
                # Bereinige Produktnamen
                product_name = re.sub(r'[\d.,]+\s*[€$£]?$', '', product_name).strip()
                
                if product_name and len(product_name) > 1:
                    products.append({
                        'name': product_name[:80],
                        'quantity': quantity,
                        'unit_price': price,
                        'total_price': round(quantity * price, 2) if quantity != 1 else price,
                        'line': i + 1,
                        'confidence': 'medium'
                    })
            except:
                pass
    
    return products

def enhance_product_guesses(products):
    """Verbessert Produktnamen durch intelligentes Raten"""
    product_dict = {
        'BANAN': 'Banane', 'BANANE': 'Banane', 'BANANEN': 'Banane',
        'APFEL': 'Apfel', 'ÄPFEL': 'Apfel', 'APPLE': 'Apfel',
        'BIRNE': 'Birne', 'BIRNEN': 'Birne',
        'ORANG': 'Orange', 'ORANGEN': 'Orange',
        'KIWI': 'Kiwi', 'KIWIS': 'Kiwi',
        'ERDBEER': 'Erdbeere', 'ERDBEEREN': 'Erdbeere',
        'HIMBEER': 'Himbeere', 'HIMBEEREN': 'Himbeere',
        'BROT': 'Brot', 'BROTE': 'Brot',
        'BRÖTCHEN': 'Brötchen',
        'MILCH': 'Milch',
        'KAESE': 'Käse', 'KÄSE': 'Käse',
        'BUTTER': 'Butter',
        'EI': 'Ei', 'EIER': 'Ei',
        'JOGHURT': 'Joghurt',
        'QUARK': 'Quark',
        'WURST': 'Wurst',
        'SCHINKEN': 'Schinken',
        'AUFSTRICH': 'Aufstrich',
        'TOMAT': 'Tomate', 'TOMATEN': 'Tomate',
        'GURK': 'Gurke', 'GURKEN': 'Gurke',
        'SALAT': 'Salat',
        'PAPRIK': 'Paprika',
        'ZUCCHIN': 'Zucchini',
        'KARTOFFEL': 'Kartoffel', 'KARTOFFELN': 'Kartoffel',
        'ZWIEBEL': 'Zwiebel', 'ZWIEBELN': 'Zwiebel',
        'KN OLA': 'Knoblauch',
        'INGWER': 'Ingwer',
        'REIS': 'Reis',
        'NUDELN': 'Nudeln', 'PASTA': 'Nudeln',
        'MEHL': 'Mehl',
        'ZUCKER': 'Zucker',
        'SALZ': 'Salz',
        'PFEFFER': 'Pfeffer',
        'ÖL': 'Öl',
        'ESSIG': 'Essig',
        'BIER': 'Bier',
        'WEIN': 'Wein',
        'WASSER': 'Wasser',
        'SAFT': 'Saft',
        'KAFFEE': 'Kaffee',
        'TEE': 'Tee',
        'BIO': 'Bio',
        'ORGANIC': 'Bio',
        'KASTAN': 'Kastanie', 'KASTANIEN': 'Kastanie',
    }
    
    for product in products:
        name_upper = product['name'].upper()
        
        # Versuche bekannte Produkte zu finden
        found = False
        for key, value in product_dict.items():
            if key in name_upper:
                product['name'] = value
                if '?' not in product['name']:
                    product['name'] += " (vermutet)"
                product['confidence'] = 'high'
                found = True
                break
        
        # Wenn nicht gefunden und Name unklar
        if not found and len(product['name']) < 4:
            product['name'] = f"Unklarer Artikel ({product['total_price']}€)"
            product['confidence'] = 'low'
    
    return products

def process_uploaded_files(uploaded_files):
    """Verarbeitet hochgeladene Dateien"""
    invoices = []
    
    for uploaded_file in uploaded_files:
        with st.spinner(f"Verarbeite {uploaded_file.name}..."):
            # Temporäre Datei speichern
            temp_path = f"temp_{uploaded_file.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Text extrahieren
            if uploaded_file.name.lower().endswith('.pdf'):
                text = extract_text_from_pdf(temp_path)
            else:
                text = extract_text_from_image(temp_path)
            
            # Metadaten extrahieren
            metadata = extract_metadata(text)
            
            # Produkte parsen
            products = parse_products_simple(text)
            products = enhance_product_guesses(products)
            
            # Rechnungsdaten speichern
            invoice_data = {
                'filename': uploaded_file.name,
                'shop': metadata['shop'],
                'date': metadata['date'],
                'total_amount': metadata['total'],
                'products': products,
                'text_preview': metadata['text_preview'],
                'product_count': len(products),
                'products_total': sum(p['total_price'] for p in products)
            }
            
            invoices.append(invoice_data)
            
            # Temporäre Datei löschen
            os.remove(temp_path)
    
    return invoices

def create_dataframes(invoices):
    """Erstellt DataFrames aus Rechnungsdaten"""
    if not invoices:
        return pd.DataFrame(), pd.DataFrame()
    
    # Rechnungsübersicht
    invoice_rows = []
    for inv in invoices:
        invoice_rows.append({
            'Dateiname': inv['filename'],
            'Shop': inv['shop'],
            'Datum': inv['date'],
            'Gesamtbetrag': inv['total_amount'],
            'Produktanzahl': inv['product_count'],
            'Produktsumme': inv['products_total'],
            'Differenz': round(inv['total_amount'] - inv['products_total'], 2)
        })
    
    invoice_df = pd.DataFrame(invoice_rows)
    
    # Produktliste
    product_rows = []
    for inv in invoices:
        for product in inv['products']:
            product_rows.append({
                'Rechnung': inv['filename'],
                'Shop': inv['shop'],
                'Datum': inv['date'],
                'Produkt': product['name'],
                'Menge': product['quantity'],
                'Einzelpreis': product['unit_price'],
                'Gesamtpreis': product['total_price'],
                'Vertrauen': product['confidence'],
                'Für mich allein': False,
                'Anteil Bruder': 0.5,
                'Anteil Ich': 0.5
            })
    
    product_df = pd.DataFrame(product_rows)
    
    return invoice_df, product_df

def calculate_split(product_df):
    """Berechnet die Aufteilung"""
    if product_df.empty:
        return 0, 0, 0
    
    product_df['Bruder Anteil'] = product_df['Gesamtpreis'] * product_df['Anteil Bruder']
    product_df['Mein Anteil'] = product_df['Gesamtpreis'] * product_df['Anteil Ich']
    
    total = product_df['Gesamtpreis'].sum()
    brother_share = product_df['Bruder Anteil'].sum()
    my_share = product_df['Mein Anteil'].sum()
    
    return total, brother_share, my_share

def create_download_link(df, filename, text):
    """Erstellt Download-Link für DataFrame"""
    csv = df.to_csv(index=False, encoding='utf-8-sig')
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">{text}</a>'
    return href

def create_excel_download(df_dict, filename):
    """Erstellt Excel-Datei mit mehreren Sheets"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in df_dict.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    output.seek(0)
    b64 = base64.b64encode(output.read()).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">📥 {filename} herunterladen</a>'
    return href

# ============ STREAMLIT APP ============
def main():
    st.title("🧾 Rechnungsmanager für Brüder")
    st.markdown("---")
    
    init_session_state()
    
    # Sidebar
    with st.sidebar:
        st.header("📁 Datei-Upload")
        
        uploaded_files = st.file_uploader(
            "Rechnungen hochladen (PDF, JPG, PNG)",
            type=['pdf', 'jpg', 'jpeg', 'png'],
            accept_multiple_files=True
        )
        
        if uploaded_files:
            if st.button("🔄 Rechnungen verarbeiten", type="primary", use_container_width=True):
                with st.spinner("Verarbeite Rechnungen..."):
                    st.session_state.invoices_data = process_uploaded_files(uploaded_files)
                    st.session_state.uploaded_files = uploaded_files
                    st.session_state.invoice_df, st.session_state.products_df = create_dataframes(
                        st.session_state.invoices_data
                    )
                st.success(f"{len(uploaded_files)} Rechnungen verarbeitet!")
        
        st.markdown("---")
        st.header("⚙️ Einstellungen")
        
        # Standard-Aufteilung
        default_split = st.slider(
            "Standard-Aufteilung Bruder/Ich (%)",
            min_value=0, max_value=100, value=50
        )
        
        if not st.session_state.products_df.empty:
            # Standard-Aufteilung anwenden
            if st.button("📊 Standard-Aufteilung anwenden", use_container_width=True):
                st.session_state.products_df['Anteil Bruder'] = default_split / 100
                st.session_state.products_df['Anteil Ich'] = (100 - default_split) / 100
                st.rerun()
        
        st.markdown("---")
        st.info(
            "**Tipps:**\n"
            "1. Laden Sie alle Rechnungen hoch\n"
            "2. Prüfen Sie die erkannten Produkte\n"
            "3. Passen Sie die Aufteilung an\n"
            "4. Laden Sie die Ergebnisse herunter"
        )
    
    # Hauptbereich
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Übersicht", "🛒 Produkte", "💰 Aufteilung", "📤 Export"])
    
    # Tab 1: Übersicht
    with tab1:
        # Prüfe ob invoice_df existiert und nicht leer ist
        has_invoice_data = hasattr(st.session_state, 'invoice_df') and not st.session_state.invoice_df.empty
        
        if has_invoice_data:
            col1, col2, col3, col4 = st.columns(4)
            
            total_invoices = len(st.session_state.invoice_df)
            total_amount = st.session_state.invoice_df['Gesamtbetrag'].sum()
            total_products = st.session_state.invoice_df['Produktanzahl'].sum()
            avg_amount = total_amount / total_invoices if total_invoices > 0 else 0
            
            with col1:
                st.metric("Rechnungen", total_invoices)
            with col2:
                st.metric("Gesamtbetrag", f"{total_amount:.2f} €")
            with col3:
                st.metric("Produkte", total_products)
            with col4:
                st.metric("⌀ pro Rechnung", f"{avg_amount:.2f} €")
            
            st.subheader("Rechnungsübersicht")
            st.dataframe(
                st.session_state.invoice_df,
                use_container_width=True,
                hide_index=True
            )
            
            # Diagramme
            col1, col2 = st.columns(2)
            
            with col1:
                # Shop-Verteilung
                shop_totals = st.session_state.invoice_df.groupby('Shop')['Gesamtbetrag'].sum().reset_index()
                if not shop_totals.empty:
                    fig1 = px.pie(
                        shop_totals,
                        values='Gesamtbetrag',
                        names='Shop',
                        title='Aufteilung nach Shop'
                    )
                    st.plotly_chart(fig1, use_container_width=True)
            
            with col2:
                # Zeitliche Verteilung
                try:
                    invoice_df_dates = st.session_state.invoice_df.copy()
                    invoice_df_dates['Datum'] = pd.to_datetime(
                        invoice_df_dates['Datum'], 
                        format='%d.%m.%Y',
                        errors='coerce'
                    )
                    if not invoice_df_dates['Datum'].isnull().all():
                        time_series = invoice_df_dates.groupby('Datum')['Gesamtbetrag'].sum().reset_index()
                        fig2 = px.line(
                            time_series,
                            x='Datum',
                            y='Gesamtbetrag',
                            title='Ausgaben über Zeit'
                        )
                        st.plotly_chart(fig2, use_container_width=True)
                except:
                    pass
        else:
            st.info("⏳ Bitte laden Sie zuerst Rechnungen hoch und verarbeiten Sie sie.")
    
    # Tab 2: Produkte
    with tab2:
        # Prüfe ob products_df existiert und nicht leer ist
        has_product_data = hasattr(st.session_state, 'products_df') and not st.session_state.products_df.empty
        
        if has_product_data:
            st.subheader("Produktliste")
            
            # Filter
            col1, col2, col3 = st.columns(3)
            with col1:
                shops = ['Alle'] + list(st.session_state.products_df['Shop'].unique())
                selected_shop = st.selectbox("Shop filtern", shops)
            with col2:
                products = ['Alle'] + list(st.session_state.products_df['Produkt'].unique())
                selected_product = st.selectbox("Produkt filtern", products)
            with col3:
                min_price, max_price = st.slider(
                    "Preisbereich",
                    min_value=0.0,
                    max_value=float(st.session_state.products_df['Gesamtpreis'].max()),
                    value=(0.0, float(st.session_state.products_df['Gesamtpreis'].max()))
                )
            
            # Filter anwenden
            filtered_df = st.session_state.products_df.copy()
            if selected_shop != 'Alle':
                filtered_df = filtered_df[filtered_df['Shop'] == selected_shop]
            if selected_product != 'Alle':
                filtered_df = filtered_df[filtered_df['Produkt'] == selected_product]
            filtered_df = filtered_df[
                (filtered_df['Gesamtpreis'] >= min_price) & 
                (filtered_df['Gesamtpreis'] <= max_price)
            ]
            
            st.dataframe(
                filtered_df,
                use_container_width=True,
                hide_index=True
            )
            
            # Produkt-Statistiken
            st.subheader("Produkt-Statistiken")
            
            product_stats = st.session_state.products_df.groupby('Produkt').agg({
                'Gesamtpreis': ['sum', 'count', 'mean'],
                'Menge': 'sum'
            }).round(2)
            
            product_stats.columns = ['Gesamtkosten', 'Anzahl', 'Durchschnittspreis', 'Gesamtmenge']
            product_stats = product_stats.sort_values('Gesamtkosten', ascending=False)
            
            st.dataframe(
                product_stats,
                use_container_width=True
            )
            
            # Top 10 Produkte
            top_products = product_stats.head(10).reset_index()
            fig = px.bar(
                top_products,
                x='Produkt',
                y='Gesamtkosten',
                title='Top 10 Produkte nach Kosten'
            )
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.info("⏳ Keine Produktdaten verfügbar. Bitte zuerst Rechnungen verarbeiten.")
    
    # Tab 3: Aufteilung
    with tab3:
        # Prüfe ob products_df existiert und nicht leer ist
        has_product_data = hasattr(st.session_state, 'products_df') and not st.session_state.products_df.empty
        
        if has_product_data:
            st.subheader("Aufteilung anpassen")
            
            # Bearbeitbare Tabelle
            st.info("🎯 Ändern Sie die Anteile für jedes Produkt (Bruder / Ich). Summe sollte 100% ergeben.")
            
            # Vorbereitung der bearbeitbaren Spalten
            edit_df = st.session_state.products_df.copy()
            
            # Spalten für Editiermodus
            columns_to_show = ['Rechnung', 'Produkt', 'Gesamtpreis', 'Anteil Bruder', 'Anteil Ich']
            
            # Daten-Editor
            edited_df = st.data_editor(
                edit_df[columns_to_show],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Anteil Bruder": st.column_config.NumberColumn(
                        "Anteil Bruder",
                        min_value=0.0,
                        max_value=1.0,
                        step=0.05,
                        format="%.2f"
                    ),
                    "Anteil Ich": st.column_config.NumberColumn(
                        "Anteil Ich",
                        min_value=0.0,
                        max_value=1.0,
                        step=0.05,
                        format="%.2f"
                    )
                }
            )
            
            # Validierung und Berechnung
            if st.button("✅ Aufteilung berechnen", type="primary"):
                # Überprüfe, ob Summe = 1 für jede Zeile
                edited_df['Summe'] = edited_df['Anteil Bruder'] + edited_df['Anteil Ich']
                invalid_rows = edited_df[abs(edited_df['Summe'] - 1.0) > 0.01]
                
                if not invalid_rows.empty:
                    st.error(f"⚠️ {len(invalid_rows)} Zeilen haben keine gültige Aufteilung (Summe ≠ 100%)")
                    st.dataframe(invalid_rows[['Rechnung', 'Produkt', 'Anteil Bruder', 'Anteil Ich', 'Summe']])
                else:
                    # Aktualisiere die Daten
                    st.session_state.products_df.update(edited_df)
                    
                    # Berechne Gesamtaufteilung
                    total, brother_share, my_share = calculate_split(st.session_state.products_df)
                    
                    # Anzeige der Ergebnisse
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Gesamtbetrag", f"{total:.2f} €")
                    with col2:
                        st.metric("Bruder Anteil", f"{brother_share:.2f} €", 
                                 f"{(brother_share/total*100 if total > 0 else 0):.1f}%")
                    with col3:
                        st.metric("Mein Anteil", f"{my_share:.2f} €",
                                 f"{(my_share/total*100 if total > 0 else 0):.1f}%")
                    
                    # Visualisierung
                    fig = go.Figure(data=[
                        go.Pie(
                            labels=['Bruder', 'Ich'],
                            values=[brother_share, my_share],
                            hole=.3
                        )
                    ])
                    fig.update_layout(title="Aufteilung der Kosten")
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.success("✅ Aufteilung erfolgreich berechnet!")
            
            # Schnell-Aufteilungen
            st.subheader("Schnell-Aufteilungen")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("50/50 Aufteilung", use_container_width=True):
                    st.session_state.products_df['Anteil Bruder'] = 0.5
                    st.session_state.products_df['Anteil Ich'] = 0.5
                    st.rerun()
            
            with col2:
                if st.button("Alles für Bruder", use_container_width=True):
                    st.session_state.products_df['Anteil Bruder'] = 1.0
                    st.session_state.products_df['Anteil Ich'] = 0.0
                    st.rerun()
            
            with col3:
                if st.button("Alles für mich", use_container_width=True):
                    st.session_state.products_df['Anteil Bruder'] = 0.0
                    st.session_state.products_df['Anteil Ich'] = 1.0
                    st.rerun()
            
        else:
            st.info("⏳ Keine Produktdaten verfügbar. Bitte zuerst Rechnungen verarbeiten.")
    
    # Tab 4: Export
    with tab4:
        # Prüfe ob DataFrames existieren und nicht leer sind
        has_invoice_data = hasattr(st.session_state, 'invoice_df') and not st.session_state.invoice_df.empty
        has_product_data = hasattr(st.session_state, 'products_df') and not st.session_state.products_df.empty
        
        if has_invoice_data and has_product_data:
            
            st.subheader("📤 Daten exportieren")
            
            # Berechne finale Aufteilung
            total, brother_share, my_share = calculate_split(st.session_state.products_df)
            
            # Export-Optionen
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📄 Excel-Export")
                
                # Vorbereitung der Excel-Datei
                excel_data = {
                    'Rechnungsübersicht': st.session_state.invoice_df,
                    'Produktliste': st.session_state.products_df,
                    'Zusammenfassung': pd.DataFrame({
                        'Metrik': ['Gesamtrechnungen', 'Gesamtbetrag', 'Bruder Anteil', 
                                  'Mein Anteil', 'Bruder %', 'Ich %'],
                        'Wert': [
                            len(st.session_state.invoice_df),
                            f"{total:.2f} €",
                            f"{brother_share:.2f} €",
                            f"{my_share:.2f} €",
                            f"{(brother_share/total*100 if total > 0 else 0):.1f}%",
                            f"{(my_share/total*100 if total > 0 else 0):.1f}%"
                        ]
                    })
                }
                
                # Produktstatistik
                product_stats = st.session_state.products_df.groupby('Produkt').agg({
                    'Gesamtpreis': ['sum', 'count', 'mean'],
                    'Menge': 'sum',
                    'Anteil Bruder': 'mean',
                    'Anteil Ich': 'mean'
                }).round(2)
                product_stats.columns = ['Gesamtkosten', 'Anzahl', '⌀ Preis', 'Gesamtmenge', '⌀ Bruder', '⌀ Ich']
                excel_data['Produktstatistik'] = product_stats.reset_index()
                
                # Download-Link
                excel_filename = f"rechnungsaufteilung_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                st.markdown(create_excel_download(excel_data, excel_filename), unsafe_allow_html=True)
            
            with col2:
                st.markdown("### 📊 CSV-Exporte")
                
                # Einzelne CSV-Dateien
                st.markdown(create_download_link(
                    st.session_state.invoice_df,
                    "rechnungsuebersicht.csv",
                    "📥 Rechnungsübersicht herunterladen"
                ), unsafe_allow_html=True)
                
                st.markdown(" ")
                
                st.markdown(create_download_link(
                    st.session_state.products_df,
                    "produktliste.csv",
                    "📥 Produktliste herunterladen"
                ), unsafe_allow_html=True)
                
                st.markdown(" ")
                
                # Zusammenfassung als CSV
                summary_df = pd.DataFrame({
                    'Kategorie': ['Gesamtbetrag', 'Bruder', 'Ich'],
                    'Betrag (€)': [total, brother_share, my_share],
                    'Anteil (%)': [
                        100,
                        brother_share/total*100 if total > 0 else 0,
                        my_share/total*100 if total > 0 else 0
                    ]
                })
                
                st.markdown(create_download_link(
                    summary_df,
                    "zusammenfassung.csv",
                    "📥 Zusammenfassung herunterladen"
                ), unsafe_allow_html=True)
            
            # JSON Export für Vollständigkeit
            st.markdown("---")
            st.markdown("### 🔧 JSON Export (für weitere Verarbeitung)")
            
            if st.button("JSON Daten anzeigen"):
                json_data = {
                    'metadata': {
                        'export_date': datetime.now().isoformat(),
                        'total_invoices': len(st.session_state.invoice_df),
                        'total_amount': total,
                        'split': {
                            'brother': brother_share,
                            'me': my_share
                        }
                    },
                    'invoices': st.session_state.invoice_df.to_dict('records'),
                    'products': st.session_state.products_df.to_dict('records')
                }
                
                st.json(json_data)
                
                # JSON Download
                json_str = json.dumps(json_data, indent=2, ensure_ascii=False)
                b64 = base64.b64encode(json_str.encode()).decode()
                href = f'<a href="data:application/json;base64,{b64}" download="rechnungsdaten_{datetime.now().strftime("%Y%m%d")}.json">📥 JSON herunterladen</a>'
                st.markdown(href, unsafe_allow_html=True)
            
            # Umbenennung der Dateien
            st.markdown("---")
            st.markdown("### 🏷️ Dateien umbenennen")
            
            if st.button("Dateien mit Metadaten umbenennen", type="secondary"):
                # Hier könnten Sie die ursprünglichen Dateien umbenennen
                # Für diese Demo zeigen wir nur Vorschläge an
                rename_suggestions = []
                for idx, invoice in enumerate(st.session_state.invoices_data):
                    new_name = f"{invoice['date']}_{invoice['shop']}_{invoice['total_amount']:.2f}EUR_{idx}.pdf"
                    rename_suggestions.append({
                        'Original': invoice['filename'],
                        'Vorschlag': new_name
                    })
                
                st.subheader("Vorschläge für neue Dateinamen")
                st.dataframe(pd.DataFrame(rename_suggestions), hide_index=True)
                
                st.info("ℹ️ In einer produktiven Version würden die Dateien automatisch umbenannt werden.")
        
        else:
            st.info("⏳ Keine Daten zum Export verfügbar. Bitte zuerst Rechnungen verarbeiten.")
    
    # Footer
    st.markdown("---")
    st.caption("Made with ❤️ für Brüder, die Rechnungen teilen | Powered by Streamlit")

if __name__ == "__main__":
    main()