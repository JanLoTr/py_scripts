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
import requests
from openai import OpenAI

# ============ KONFIGURATION ============
st.set_page_config(
    page_title="Rechnungsmanager mit KI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Tesseract OCR Pfad (Windows)
try:
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
except:
    # Für andere Betriebssysteme
    pass

# OpenAI/LLM Konfiguration
API_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
LLM_ENDPOINT = "https://api.openai.com/v1/chat/completions"
LLM_MODEL = "gpt-4-turbo-preview"

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
    if 'enhanced_data' not in st.session_state:
        st.session_state.enhanced_data = []
    if 'use_ki_enhancement' not in st.session_state:
        st.session_state.use_ki_enhancement = True

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

def enhance_with_llm(raw_data):
    """Verbessert die extrahierten Daten mit KI"""
    
    if not API_KEY:
        st.warning("Kein API-Key konfiguriert. Verwende Standard-Verarbeitung.")
        return raw_data
    
    prompt = """Du erhältst JSON-Daten, die aus Rechnungen, Belegen oder ähnlichen Dokumenten extrahiert wurden.
Deine Aufgabe ist es, diese Daten intelligent zu analysieren, zu korrigieren und zu strukturieren, sodass sie inhaltlich sinnvoll, konsistent und realitätsnah sind.

Verbesserungen und Anforderungen:

1. Rechnungsverständnis
- Erkenne, ob es sich tatsächlich um eine Rechnung oder einen Beleg handelt.
- Rekonstruiere die logisch richtige Struktur (Shop, Positionen, Preise, Summen).

2. Produkt- & Aktionslogik
- Aktionen wie „Rabatt“, „AKTION –0,50 €“, „Gutschrift“ oder ähnliche Einträge dürfen kein eigenes Produkt sein.
- Ordne Rabatte logisch bestehenden Produkten oder der Gesamtsumme zu.

3. Shop-Erkennung
- Erkenne den Shop / Händler zuverlässig aus Textfragmenten, Logos, Domains oder Kontext.
- Vereinheitliche Shop-Namen (z. B. keine Dubletten durch Schreibvarianten).

4. Preis- & Summenprüfung
- Prüfe, ob Einzelpreise, Mengen, Zwischensummen und Gesamtsumme mathematisch zusammenpassen.
- Falls Inkonsistenzen bestehen, korrigiere sie oder markiere sie nachvollziehbar.

5. Semantische Verbesserung
- Vereinfache kryptische Produktnamen, wenn möglich.
- Entferne irrelevante Zeilen (z. B. Werbetexte, rechtliche Hinweise).

6. Robustheit
- Gehe fehlertolerant mit unvollständigen oder chaotischen Daten um.
- Triff sinnvolle Annahmen, wenn Informationen fehlen, und markiere diese Annahmen.

7. Ziel
- Gib ein bereinigtes, konsistentes JSON zurück.
- Füge ein kurzes Feld "reasoning" hinzu, in dem du erklärst, welche Annahmen oder Korrekturen vorgenommen wurden.

Ziel ist nicht bloße Formatierung, sondern inhaltliches Verständnis der Rechnung.

Hier sind die extrahierten Daten:
"""

    try:
        client = OpenAI(api_key=API_KEY)
        
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "Du bist ein Experte für Rechnungsverarbeitung und Datenbereinigung."},
                {"role": "user", "content": prompt + json.dumps(raw_data, ensure_ascii=False, indent=2)}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        result_text = response.choices[0].message.content
        
        # Extrahiere JSON aus der Antwort
        json_match = re.search(r'```json\s*(.*?)\s*```', result_text, re.DOTALL)
        if json_match:
            result_text = json_match.group(1)
        
        enhanced_data = json.loads(result_text)
        return enhanced_data
        
    except Exception as e:
        st.error(f"Fehler bei KI-Verbesserung: {e}")
        return raw_data

def extract_metadata_enhanced(text):
    """Verbesserte Metadatenextraktion mit erweitertem Shop-Vokabular"""
    
    # Erweiterte Shop-Erkennung
    shop_patterns = {
        'SPAR': ['SPAR', 'EUROSPAR', 'INTERSPAR'],
        'HOFER': ['HOFER', 'ALDI SÜD', 'ALDI SUED'],
        'BILLA': ['BILLA', 'BILLA PLUS'],
        'MERKUR': ['MERKUR'],
        'LIDL': ['LIDL'],
        'PENNY': ['PENNY'],
        'DM': ['DM'],
        'ROSSMANN': ['ROSSMANN'],
        'TRANZGOURMET': ['TRANZGOURMET', 'TRANSGOURMET'],
        'TKMAXX': ['TK MAXX', 'TKMAXX', 'T.K. MAXX'],
        'DECATHLON': ['DECATHLON'],
        'BAUHAUS': ['BAUHAUS'],
        'HORNBACH': ['HORNBACH'],
        'MEDIA MARKT': ['MEDIA MARKT', 'MEDIAMARKT'],
        'SATURN': ['SATURN'],
        'IKEA': ['IKEA'],
        'ZARA': ['ZARA'],
        'H&M': ['H&M', 'H & M'],
        'C&A': ['C&A', 'C & A'],
        'THALIA': ['THALIA'],
        'MÜLLER': ['MÜLLER', 'MUELLER'],
        'TCHIBO': ['TCHIBO'],
        'EDEKA': ['EDEKA'],
        'REWE': ['REWE'],
        'KAUFLAND': ['KAUFLAND'],
        'ALDI': ['ALDI', 'ALDI NORD'],
        'NETTO': ['NETTO'],
        'NAH & GUT': ['NAH & GUT'],
        'NKD': ['NKD'],
        'WELTBILD': ['WELTBILD'],
        'HERVIS': ['HERVIS'],
        'SPORT 2000': ['SPORT 2000'],
        'INTERSPORT': ['INTERSPORT'],
        'BIKE': ['BIKE'],
        'MOBELIX': ['MOBELIX', 'MÖBELIX'],
        'KIKA': ['KIKA'],
        'LUTZ': ['LUTZ'],
        'LEINER': ['LEINER'],
        'SEGEL': ['SEGEL'],
        'TEDi': ['TEDi'],
        'WOOLWORTH': ['WOOLWORTH'],
        'DEPOT': ['DEPOT'],
        'BUTLERS': ['BUTLERS'],
        'MANOR': ['MANOR'],
        'GLOBUS': ['GLOBUS'],
        'COOP': ['COOP'],
        'MIGROS': ['MIGROS'],
        'DENNER': ['DENNER'],
        'VOLG': ['VOLG']
    }
    
    text_upper = text.upper()
    shop = "Unbekannt"
    detected_shop = ""
    
    for shop_name, patterns in shop_patterns.items():
        for pattern in patterns:
            if pattern.upper() in text_upper:
                shop = shop_name
                detected_shop = shop_name
                break
        if detected_shop:
            break
    
    # Falls kein Shop erkannt, suche nach generischen Mustern
    if shop == "Unbekannt":
        generic_patterns = [
            (r'(MARKT|SUPERMARKT|DISCOUNTER)\s+([A-Z]{2,})', 2),
            (r'([A-Z]{3,})\s+(MARKT|SUPERMARKT|DISCOUNTER)', 1),
            (r'([A-Z]{3,})\s+([A-Z]{2,})\s+GMBH', 1),
        ]
        
        for pattern, group_idx in generic_patterns:
            match = re.search(pattern, text_upper)
            if match:
                potential_shop = match.group(group_idx)
                if len(potential_shop) > 2:
                    shop = potential_shop
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
        r'BAR[:\s]*(\d+[,\.]\d{2})',
        r'ENDSUMME[:\s]*(\d+[,\.]\d{2})',
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
    
    # Rechnungsnummer erkennen
    invoice_number = ""
    inv_patterns = [
        r'Rechnung\s*Nr[\.:]?\s*([A-Z0-9\-]+)',
        r'Rechnungsnummer[:\s]*([A-Z0-9\-]+)',
        r'Belegnummer[:\s]*([A-Z0-9\-]+)',
        r'Nr[\.:]\s*([A-Z0-9\-]{6,})'
    ]
    
    for pattern in inv_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            invoice_number = match.group(1)
            break
    
    return {
        'shop': shop,
        'date': date_str,
        'total': total,
        'invoice_number': invoice_number,
        'all_amounts': amounts,
        'text_preview': text[:500] + "..." if len(text) > 500 else text
    }

def parse_products_simple(text):
    """Einfache Produktparsing ohne KI"""
    products = []
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Überspringen von Kopfzeilen und nicht-Produktzeilen
        skip_patterns = [
            'Rechnung', 'Quittung', 'Kassenzettel', 'Beleg', 
            'SUMME', 'TOTAL', 'ENDSUMME', 'ZUZAHLEN',
            'EUR', '€', 'UST', 'MwSt', 'Mehrwertsteuer',
            'BAR', 'EC', 'Kreditkarte', 'VISA',
            'Danke', 'Vielen Dank', 'Besuchen Sie',
            '=====', '-----', '*****'
        ]
        
        if any(pattern.lower() in line.lower() for pattern in skip_patterns):
            continue
        
        if len(line) < 3:
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
                
                # Prüfe auf Rabatt/Aktion
                is_discount = any(word in product_name.upper() for word in ['RABATT', 'AKTION', 'GUTSCHRIFT', '-'])
                if is_discount and price < 0:
                    # Negative Beträge sind Rabatte
                    continue
                
                # Bereinige Produktnamen
                product_name = re.sub(r'[\d.,]+\s*[€$£]?$', '', product_name).strip()
                
                if product_name and len(product_name) > 1:
                    products.append({
                        'name': product_name[:80],
                        'quantity': quantity,
                        'unit_price': price,
                        'total_price': round(quantity * price, 2) if quantity != 1 else price,
                        'line': i + 1,
                        'confidence': 'medium',
                        'is_personal': False,
                        'notes': ''
                    })
            except:
                pass
    
    return products

def process_uploaded_files(uploaded_files, use_ki=True):
    """Verarbeitet hochgeladene Dateien mit optionaler KI-Verbesserung"""
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
            metadata = extract_metadata_enhanced(text)
            
            # Produkte parsen
            products = parse_products_simple(text)
            
            # Rohe Daten für KI
            raw_invoice_data = {
                'filename': uploaded_file.name,
                'raw_text': text[:2000],  # Begrenze für KI
                'metadata': metadata,
                'products': products
            }
            
            # KI-Verbesserung anwenden
            if use_ki and API_KEY:
                try:
                    with st.spinner(f"Verbessere Daten mit KI..."):
                        enhanced = enhance_with_llm(raw_invoice_data)
                        
                        # Verwende KI-verbesserte Daten
                        if 'metadata' in enhanced:
                            metadata = enhanced['metadata']
                        if 'products' in enhanced:
                            products = enhanced['products']
                        
                        # Füge KI-Flag hinzu
                        ki_enhanced = True
                except Exception as e:
                    st.warning(f"KI-Verbesserung fehlgeschlagen: {e}. Verwende Standarddaten.")
                    ki_enhanced = False
            else:
                ki_enhanced = False
            
            # Finale Rechnungsdaten
            invoice_data = {
                'filename': uploaded_file.name,
                'shop': metadata['shop'],
                'date': metadata['date'],
                'total_amount': metadata['total'],
                'invoice_number': metadata.get('invoice_number', ''),
                'products': products,
                'text_preview': metadata['text_preview'],
                'product_count': len(products),
                'products_total': sum(p.get('total_price', 0) for p in products),
                'ki_enhanced': ki_enhanced,
                'reasoning': enhanced.get('reasoning', '') if ki_enhanced else ''
            }
            
            invoices.append(invoice_data)
            
            # Temporäre Datei löschen
            try:
                os.remove(temp_path)
            except:
                pass
    
    return invoices

def create_dataframes(invoices):
    """Erstellt DataFrames aus Rechnungsdaten mit KI-Verbesserung"""
    if not invoices:
        return pd.DataFrame(), pd.DataFrame()
    
    # Rechnungsübersicht
    invoice_rows = []
    for inv in invoices:
        invoice_rows.append({
            'Dateiname': inv['filename'],
            'Shop': inv['shop'],
            'Datum': inv['date'],
            'Rechnungsnummer': inv.get('invoice_number', ''),
            'Gesamtbetrag': inv['total_amount'],
            'Produktanzahl': inv['product_count'],
            'Produktsumme': inv['products_total'],
            'Differenz': round(inv['total_amount'] - inv['products_total'], 2),
            'KI-verbessert': '✅' if inv.get('ki_enhanced', False) else '❌'
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
                'Produkt': product.get('name', 'Unbekannt'),
                'Menge': product.get('quantity', 1),
                'Einzelpreis': product.get('unit_price', 0),
                'Gesamtpreis': product.get('total_price', 0),
                'Vertrauen': product.get('confidence', 'medium'),
                'Notizen': product.get('notes', ''),
                'Für mich allein': product.get('is_personal', False),
                'Anteil Bruder': 0.5,
                'Anteil Ich': 0.5,
                'KI-verbessert': '✅' if inv.get('ki_enhanced', False) else '❌'
            })
    
    product_df = pd.DataFrame(product_rows)
    
    return invoice_df, product_df

def calculate_split(product_df):
    """Berechnet die Aufteilung"""
    if product_df.empty:
        return 0, 0, 0
    
    # Produkte nur für mich
    my_only = product_df[product_df['Für mich allein'] == True]
    shared = product_df[product_df['Für mich allein'] == False]
    
    # Nur meine Produkte
    my_only_total = my_only['Gesamtpreis'].sum() if not my_only.empty else 0
    
    # Geteilte Produkte
    shared['Bruder Anteil'] = shared['Gesamtpreis'] * shared['Anteil Bruder']
    shared['Mein Anteil'] = shared['Gesamtpreis'] * shared['Anteil Ich']
    
    brother_share = shared['Bruder Anteil'].sum() if not shared.empty else 0
    my_share = shared['Mein Anteil'].sum() + my_only_total if not shared.empty else my_only_total
    
    total = product_df['Gesamtpreis'].sum()
    
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
    st.title("🤖 Rechnungsmanager mit KI-Verbesserung")
    st.markdown("---")
    
    init_session_state()
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ KI-Einstellungen")
        
        st.session_state.use_ki_enhancement = st.checkbox(
            "KI-Datenverbesserung verwenden",
            value=True,
            help="Verwendet KI, um Produktnamen, Preise und Struktur zu verbessern"
        )
        
        if st.session_state.use_ki_enhancement:
            if not API_KEY:
                st.error("⚠️ Kein API-Key konfiguriert. Bitte setzen Sie OPENAI_API_KEY in den Secrets.")
                st.info("Fügen Sie ihn hinzu über: `.streamlit/secrets.toml`")
                st.code("OPENAI_API_KEY = \"Ihr-Key-hier\"")
        
        st.markdown("---")
        st.header("📁 Datei-Upload")
        
        uploaded_files = st.file_uploader(
            "Rechnungen hochladen (PDF, JPG, PNG)",
            type=['pdf', 'jpg', 'jpeg', 'png'],
            accept_multiple_files=True
        )
        
        if uploaded_files:
            if st.button("🔄 Rechnungen verarbeiten", type="primary", use_container_width=True):
                with st.spinner("Verarbeite Rechnungen..."):
                    st.session_state.invoices_data = process_uploaded_files(
                        uploaded_files, 
                        use_ki=st.session_state.use_ki_enhancement
                    )
                    st.session_state.uploaded_files = uploaded_files
                    st.session_state.invoice_df, st.session_state.products_df = create_dataframes(
                        st.session_state.invoices_data
                    )
                st.success(f"{len(uploaded_files)} Rechnungen verarbeitet!")
        
        st.markdown("---")
        st.header("🎯 Aufteilungs-Einstellungen")
        
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
            "**💡 Tipps:**\n"
            "1. Laden Sie alle Rechnungen hoch\n"
            "2. KI verbessert automatisch die Erkennung\n"
            "3. Markieren Sie persönliche Produkte\n"
            "4. Passen Sie die Aufteilung an\n"
            "5. Exportieren Sie die Ergebnisse"
        )
    
    # Hauptbereich
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Übersicht", "🛒 Produkte", "🎯 Persönlich", "💰 Aufteilung", "📤 Export"])
    
    # Tab 1: Übersicht
    with tab1:
        has_invoice_data = hasattr(st.session_state, 'invoice_df') and not st.session_state.invoice_df.empty
        
        if has_invoice_data:
            col1, col2, col3, col4, col5 = st.columns(5)
            
            total_invoices = len(st.session_state.invoice_df)
            total_amount = st.session_state.invoice_df['Gesamtbetrag'].sum()
            total_products = st.session_state.invoice_df['Produktanzahl'].sum()
            avg_amount = total_amount / total_invoices if total_invoices > 0 else 0
            ki_enhanced_count = (st.session_state.invoice_df['KI-verbessert'] == '✅').sum()
            
            with col1:
                st.metric("Rechnungen", total_invoices)
            with col2:
                st.metric("Gesamtbetrag", f"{total_amount:.2f} €")
            with col3:
                st.metric("Produkte", total_products)
            with col4:
                st.metric("⌀ pro Rechnung", f"{avg_amount:.2f} €")
            with col5:
                st.metric("KI-verbessert", f"{ki_enhanced_count}/{total_invoices}")
            
            st.subheader("Rechnungsübersicht")
            st.dataframe(
                st.session_state.invoice_df,
                use_container_width=True,
                hide_index=True
            )
            
            # KI-Erklärungen anzeigen
            if st.session_state.use_ki_enhancement:
                with st.expander("🔍 KI-Verbesserungsdetails anzeigen"):
                    for inv in st.session_state.invoices_data:
                        if inv.get('ki_enhanced') and inv.get('reasoning'):
                            st.markdown(f"**{inv['filename']}**")
                            st.info(inv['reasoning'])
                            st.markdown("---")
            
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
        has_product_data = hasattr(st.session_state, 'products_df') and not st.session_state.products_df.empty
        
        if has_product_data:
            st.subheader("Produktliste")
            
            # Filter
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                shops = ['Alle'] + list(st.session_state.products_df['Shop'].unique())
                selected_shop = st.selectbox("Shop filtern", shops, key="shop_filter")
            with col2:
                products = ['Alle'] + list(st.session_state.products_df['Produkt'].unique())
                selected_product = st.selectbox("Produkt filtern", products, key="product_filter")
            with col3:
                ki_status = ['Alle', 'KI-verbessert ✅', 'Nicht verbessert ❌']
                selected_ki = st.selectbox("KI-Status", ki_status, key="ki_filter")
            with col4:
                min_price, max_price = st.slider(
                    "Preisbereich",
                    min_value=0.0,
                    max_value=float(st.session_state.products_df['Gesamtpreis'].max()),
                    value=(0.0, float(st.session_state.products_df['Gesamtpreis'].max())),
                    key="price_filter"
                )
            
            # Filter anwenden
            filtered_df = st.session_state.products_df.copy()
            if selected_shop != 'Alle':
                filtered_df = filtered_df[filtered_df['Shop'] == selected_shop]
            if selected_product != 'Alle':
                filtered_df = filtered_df[filtered_df['Produkt'] == selected_product]
            if selected_ki == 'KI-verbessert ✅':
                filtered_df = filtered_df[filtered_df['KI-verbessert'] == '✅']
            elif selected_ki == 'Nicht verbessert ❌':
                filtered_df = filtered_df[filtered_df['KI-verbessert'] == '❌']
            
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
                title='Top 10 Produkte nach Kosten',
                color='Gesamtkosten'
            )
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.info("⏳ Keine Produktdaten verfügbar. Bitte zuerst Rechnungen verarbeiten.")
    
    # Tab 3: Persönliche Produkte
    with tab3:
        has_product_data = hasattr(st.session_state, 'products_df') and not st.session_state.products_df.empty
        
        if has_product_data:
            st.subheader("🎯 Persönliche Produkte markieren")
            st.info("Markieren Sie hier Produkte, die nur Sie bezahlen (nicht Ihr Bruder).")
            
            # Filter für einfache Auswahl
            col1, col2 = st.columns(2)
            with col1:
                shop_filter = st.selectbox(
                    "Shop für Filter",
                    ['Alle'] + list(st.session_state.products_df['Shop'].unique()),
                    key="personal_shop_filter"
                )
            
            with col2:
                product_filter = st.selectbox(
                    "Produkt suchen",
                    ['Alle'] + list(st.session_state.products_df['Produkt'].unique()),
                    key="personal_product_filter"
                )
            
            # Vorbereitung der bearbeitbaren Tabelle
            personal_df = st.session_state.products_df.copy()
            
            if shop_filter != 'Alle':
                personal_df = personal_df[personal_df['Shop'] == shop_filter]
            if product_filter != 'Alle':
                personal_df = personal_df[personal_df['Produkt'] == product_filter]
            
            # Bearbeitbare Spalten
            columns_to_show = ['Rechnung', 'Shop', 'Produkt', 'Gesamtpreis', 'Für mich allein', 'Notizen']
            
            # Daten-Editor
            st.markdown("**🎯 Produkte bearbeiten**")
            edited_personal_df = st.data_editor(
                personal_df[columns_to_show],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Für mich allein": st.column_config.CheckboxColumn(
                        "Nur für mich",
                        help="Markieren, wenn nur Sie dieses Produkt bezahlen"
                    ),
                    "Notizen": st.column_config.TextColumn(
                        "Notizen",
                        help="Fügen Sie Notizen hinzu (z.B. warum nur für Sie)"
                    )
                },
                num_rows="dynamic"
            )
            
            if st.button("✅ Persönliche Auswahl speichern", type="primary"):
                # Update der Hauptdaten
                for idx, row in edited_personal_df.iterrows():
                    mask = (
                        (st.session_state.products_df['Rechnung'] == row['Rechnung']) &
                        (st.session_state.products_df['Produkt'] == row['Produkt']) &
                        (st.session_state.products_df['Shop'] == row['Shop'])
                    )
                    st.session_state.products_df.loc[mask, 'Für mich allein'] = row['Für mich allein']
                    st.session_state.products_df.loc[mask, 'Notizen'] = row['Notizen']
                
                st.success("✅ Persönliche Auswahl gespeichert!")
                
                # Statistik anzeigen
                personal_count = edited_personal_df['Für mich allein'].sum()
                personal_total = edited_personal_df[edited_personal_df['Für mich allein']]['Gesamtpreis'].sum()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Persönliche Produkte", int(personal_count))
                with col2:
                    st.metric("Gesamtbetrag persönlich", f"{personal_total:.2f} €")
            
            # Schnell-Markierungen
            st.subheader("⚡ Schnell-Markierungen")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🛒 Ganzen Einkauf für mich", use_container_width=True):
                    if shop_filter != 'Alle':
                        mask = st.session_state.products_df['Shop'] == shop_filter
                        st.session_state.products_df.loc[mask, 'Für mich allein'] = True
                        st.rerun()
            
            with col2:
                if st.button("📋 Ausgewählte Produkte für mich", use_container_width=True):
                    if not personal_df.empty:
                        for _, row in personal_df.iterrows():
                            mask = (
                                (st.session_state.products_df['Rechnung'] == row['Rechnung']) &
                                (st.session_state.products_df['Produkt'] == row['Produkt'])
                            )
                            st.session_state.products_df.loc[mask, 'Für mich allein'] = True
                        st.rerun()
            
            with col3:
                if st.button("🔄 Alle zurücksetzen", use_container_width=True):
                    st.session_state.products_df['Für mich allein'] = False
                    st.rerun()
            
        else:
            st.info("⏳ Keine Produktdaten verfügbar. Bitte zuerst Rechnungen verarbeiten.")
    
    # Tab 4: Aufteilung
    with tab4:
        has_product_data = hasattr(st.session_state, 'products_df') and not st.session_state.products_df.empty
        
        if has_product_data:
            st.subheader("💰 Kostenaufteilung anpassen")
            
            # Vorbereitung der bearbeitbaren Tabelle
            st.info("🎯 **Hinweis**: Produkte die als 'Für mich allein' markiert sind, werden automatisch 100% Ihnen zugeordnet.")
            
            # Filter für nur geteilte Produkte
            shared_df = st.session_state.products_df[st.session_state.products_df['Für mich allein'] == False].copy()
            
            if not shared_df.empty:
                # Daten-Editor für geteilte Produkte
                columns_to_show = ['Rechnung', 'Produkt', 'Gesamtpreis', 'Anteil Bruder', 'Anteil Ich']
                
                edited_shared_df = st.data_editor(
                    shared_df[columns_to_show],
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
                if st.button("✅ Aufteilung berechnen und speichern", type="primary"):
                    # Überprüfe, ob Summe = 1 für jede Zeile
                    edited_shared_df['Summe'] = edited_shared_df['Anteil Bruder'] + edited_shared_df['Anteil Ich']
                    invalid_rows = edited_shared_df[abs(edited_shared_df['Summe'] - 1.0) > 0.01]
                    
                    if not invalid_rows.empty:
                        st.error(f"⚠️ {len(invalid_rows)} Zeilen haben keine gültige Aufteilung (Summe ≠ 100%)")
                        st.dataframe(invalid_rows[['Rechnung', 'Produkt', 'Anteil Bruder', 'Anteil Ich', 'Summe']])
                    else:
                        # Aktualisiere die Daten
                        for idx, row in edited_shared_df.iterrows():
                            mask = (
                                (st.session_state.products_df['Rechnung'] == row['Rechnung']) &
                                (st.session_state.products_df['Produkt'] == row['Produkt']) &
                                (st.session_state.products_df['Für mich allein'] == False)
                            )
                            st.session_state.products_df.loc[mask, 'Anteil Bruder'] = row['Anteil Bruder']
                            st.session_state.products_df.loc[mask, 'Anteil Ich'] = row['Anteil Ich']
                        
                        # Berechne Gesamtaufteilung
                        total, brother_share, my_share = calculate_split(st.session_state.products_df)
                        
                        # Anzeige der Ergebnisse
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("Gesamtbetrag", f"{total:.2f} €")
                        with col2:
                            st.metric("Bruder Anteil", f"{brother_share:.2f} €", 
                                     f"{(brother_share/total*100 if total > 0 else 0):.1f}%")
                        with col3:
                            st.metric("Mein Anteil", f"{my_share:.2f} €",
                                     f"{(my_share/total*100 if total > 0 else 0):.1f}%")
                        with col4:
                            personal_total = st.session_state.products_df[
                                st.session_state.products_df['Für mich allein']
                            ]['Gesamtpreis'].sum()
                            st.metric("Nur ich", f"{personal_total:.2f} €")
                        
                        # Visualisierung
                        fig = go.Figure(data=[
                            go.Pie(
                                labels=['Bruder', 'Ich (geteilt)', 'Ich (allein)'],
                                values=[brother_share, my_share - personal_total, personal_total],
                                hole=.3,
                                marker=dict(colors=['#FF6B6B', '#4ECDC4', '#45B7D1'])
                            )
                        ])
                        fig.update_layout(title="Detailierte Kostenaufteilung")
                        st.plotly_chart(fig, use_container_width=True)
                        
                        st.success("✅ Aufteilung erfolgreich berechnet und gespeichert!")
            
            # Schnell-Aufteilungen
            st.subheader("⚡ Schnell-Aufteilungen")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("50/50 Aufteilung", use_container_width=True):
                    st.session_state.products_df.loc[
                        st.session_state.products_df['Für mich allein'] == False,
                        ['Anteil Bruder', 'Anteil Ich']
                    ] = [0.5, 0.5]
                    st.rerun()
            
            with col2:
                if st.button("70/30 (Bruder/Ich)", use_container_width=True):
                    st.session_state.products_df.loc[
                        st.session_state.products_df['Für mich allein'] == False,
                        ['Anteil Bruder', 'Anteil Ich']
                    ] = [0.7, 0.3]
                    st.rerun()
            
            with col3:
                if st.button("30/70 (Bruder/Ich)", use_container_width=True):
                    st.session_state.products_df.loc[
                        st.session_state.products_df['Für mich allein'] == False,
                        ['Anteil Bruder', 'Anteil Ich']
                    ] = [0.3, 0.7]
                    st.rerun()
            
            # Aufteilung nach Shop
            st.subheader("🏪 Aufteilung nach Shop")
            
            if not st.session_state.products_df.empty:
                shop_split = []
                for shop in st.session_state.products_df['Shop'].unique():
                    shop_df = st.session_state.products_df[st.session_state.products_df['Shop'] == shop]
                    shop_total, shop_brother, shop_me = calculate_split(shop_df)
                    
                    if shop_total > 0:
                        shop_split.append({
                            'Shop': shop,
                            'Gesamt': shop_total,
                            'Bruder': shop_brother,
                            'Ich': shop_me,
                            'Bruder %': (shop_brother / shop_total * 100) if shop_total > 0 else 0,
                            'Ich %': (shop_me / shop_total * 100) if shop_total > 0 else 0
                        })
                
                if shop_split:
                    shop_split_df = pd.DataFrame(shop_split)
                    st.dataframe(shop_split_df, use_container_width=True, hide_index=True)
            
        else:
            st.info("⏳ Keine Produktdaten verfügbar. Bitte zuerst Rechnungen verarbeiten.")
    
    # Tab 5: Export
    with tab5:
        has_invoice_data = hasattr(st.session_state, 'invoice_df') and not st.session_state.invoice_df.empty
        has_product_data = hasattr(st.session_state, 'products_df') and not st.session_state.products_df.empty
        
        if has_invoice_data and has_product_data:
            
            st.subheader("📤 Daten exportieren")
            
            # Berechne finale Aufteilung
            total, brother_share, my_share = calculate_split(st.session_state.products_df)
            personal_total = st.session_state.products_df[
                st.session_state.products_df['Für mich allein']
            ]['Gesamtpreis'].sum()
            shared_my_share = my_share - personal_total
            
            # Export-Optionen
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📄 Excel-Export (empfohlen)")
                
                # Vorbereitung der Excel-Datei
                excel_data = {
                    'Rechnungsübersicht': st.session_state.invoice_df,
                    'Produktliste': st.session_state.products_df,
                    'Zusammenfassung': pd.DataFrame({
                        'Metrik': [
                            'Gesamtrechnungen', 
                            'Gesamtbetrag', 
                            'Bruder Anteil (gesamt)',
                            'Ich Anteil (gesamt)',
                            'Davon nur ich',
                            'Davon geteilt (mein Anteil)',
                            'Bruder %',
                            'Ich %'
                        ],
                        'Wert': [
                            len(st.session_state.invoice_df),
                            f"{total:.2f} €",
                            f"{brother_share:.2f} €",
                            f"{my_share:.2f} €",
                            f"{personal_total:.2f} €",
                            f"{shared_my_share:.2f} €",
                            f"{(brother_share/total*100 if total > 0 else 0):.1f}%",
                            f"{(my_share/total*100 if total > 0 else 0):.1f}%"
                        ]
                    }),
                    'Shop_Aufteilung': pd.DataFrame([
                        {
                            'Shop': shop,
                            'Gesamt': shop_total,
                            'Bruder': shop_brother,
                            'Ich': shop_me,
                            'Bruder_%': (shop_brother / shop_total * 100) if shop_total > 0 else 0,
                            'Ich_%': (shop_me / shop_total * 100) if shop_total > 0 else 0
                        }
                        for shop in st.session_state.products_df['Shop'].unique()
                        for shop_df in [st.session_state.products_df[st.session_state.products_df['Shop'] == shop]]
                        for shop_total, shop_brother, shop_me in [calculate_split(shop_df)]
                        if shop_total > 0
                    ])
                }
                
                # Produktstatistik
                product_stats = st.session_state.products_df.groupby('Produkt').agg({
                    'Gesamtpreis': ['sum', 'count', 'mean'],
                    'Menge': 'sum',
                    'Anteil Bruder': 'mean',
                    'Anteil Ich': 'mean',
                    'Für mich allein': 'sum'
                }).round(2)
                product_stats.columns = [
                    'Gesamtkosten', 'Anzahl', '⌀ Preis', 'Gesamtmenge', 
                    '⌀ Bruder', '⌀ Ich', 'Nur_ich_Anzahl'
                ]
                excel_data['Produktstatistik'] = product_stats.reset_index()
                
                # Download-Link
                excel_filename = f"rechnungsaufteilung_ki_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
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
                    'Kategorie': [
                        'Gesamtbetrag', 
                        'Bruder (gesamt)', 
                        'Ich (gesamt)',
                        'Davon nur ich',
                        'Davon geteilt (mein Anteil)'
                    ],
                    'Betrag (€)': [
                        total, 
                        brother_share, 
                        my_share,
                        personal_total,
                        shared_my_share
                    ],
                    'Anteil (%)': [
                        100,
                        brother_share/total*100 if total > 0 else 0,
                        my_share/total*100 if total > 0 else 0,
                        personal_total/total*100 if total > 0 else 0,
                        shared_my_share/total*100 if total > 0 else 0
                    ]
                })
                
                st.markdown(create_download_link(
                    summary_df,
                    "zusammenfassung.csv",
                    "📥 Detailierte Zusammenfassung"
                ), unsafe_allow_html=True)
            
            # JSON Export mit KI-Daten
            st.markdown("---")
            st.markdown("### 🔧 JSON Export (inkl. KI-Daten)")
            
            if st.button("JSON Daten mit KI-Verbesserung anzeigen"):
                json_data = {
                    'metadata': {
                        'export_date': datetime.now().isoformat(),
                        'total_invoices': len(st.session_state.invoice_df),
                        'total_amount': total,
                        'split': {
                            'brother_total': brother_share,
                            'me_total': my_share,
                            'me_personal_only': personal_total,
                            'me_shared': shared_my_share,
                            'brother_percentage': brother_share/total*100 if total > 0 else 0,
                            'me_percentage': my_share/total*100 if total > 0 else 0
                        },
                        'ki_enhancement_used': st.session_state.use_ki_enhancement,
                        'api_key_configured': bool(API_KEY)
                    },
                    'invoices': st.session_state.invoice_df.to_dict('records'),
                    'products': st.session_state.products_df.to_dict('records'),
                    'ki_enhanced_invoices': [
                        {
                            'filename': inv['filename'],
                            'shop': inv['shop'],
                            'ki_enhanced': inv.get('ki_enhanced', False),
                            'reasoning': inv.get('reasoning', '')
                        }
                        for inv in st.session_state.invoices_data
                        if inv.get('ki_enhanced', False)
                    ]
                }
                
                st.json(json_data)
                
                # JSON Download
                json_str = json.dumps(json_data, indent=2, ensure_ascii=False)
                b64 = base64.b64encode(json_str.encode()).decode()
                href = f'<a href="data:application/json;base64,{b64}" download="rechnungsdaten_ki_{datetime.now().strftime("%Y%m%d")}.json">📥 JSON mit KI-Daten herunterladen</a>'
                st.markdown(href, unsafe_allow_html=True)
            
        else:
            st.info("⏳ Keine Daten zum Export verfügbar. Bitte zuerst Rechnungen verarbeiten.")
    
    # Footer
    st.markdown("---")
    st.caption("🤖 Mit KI-Verbesserung | Made with ❤️ für Brüder, die Rechnungen teilen | Powered by Streamlit & OpenAI")

if __name__ == "__main__":
    main()