import os
import json
import re
from pathlib import Path
import pdfplumber
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
import openai
from datetime import datetime
import pandas as pd

# ============ KONFIGURATION ============
# Pfade
SCRIPT_DIR = Path(__file__).parent.absolute()
INPUT_DIR = SCRIPT_DIR / "rechnungen"  # Ordner mit Rechnungen
EXTRACTED_DATA_DIR = SCRIPT_DIR / "extracted_data"
EXTRACTED_DATA_DIR.mkdir(exist_ok=True)

# OpenAI API (falls Sie KI verwenden möchten)
USE_OPENAI = False  # Auf True setzen, wenn Sie OpenAI nutzen möchten
OPENAI_API_KEY = "Ihr_API_Key_Hier"

# Tesseract OCR
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ============ HILFSFUNKTIONEN ============
def extract_text_from_pdf(pdf_path, max_pages=5):
    """Extrahiert Text aus PDF, mit OCR-Fallback"""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i in range(min(len(pdf.pages), max_pages)):
                page = pdf.pages[i]
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    text += page_text + "\n"
                else:
                    # OCR für gescannte PDFs
                    images = convert_from_path(pdf_path, first_page=i+1, last_page=i+1)
                    for img in images:
                        text += pytesseract.image_to_string(img) + "\n"
    except Exception as e:
        print(f"Fehler bei PDF-Extraktion: {e}")
        text = pytesseract.image_to_string(Image.open(pdf_path))
    
    return text.strip()

def extract_text_from_image(image_path):
    """Extrahiert Text aus Bildern mit OCR"""
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang='deu+eng')
        return text.strip()
    except Exception as e:
        print(f"Fehler bei Bild-Extraktion: {e}")
        return ""

def clean_ocr_text(text):
    """Bereinigt OCR-Fehler"""
    # Häufige OCR-Fehler korrigieren
    replacements = {
        '|': '1',
        'O': '0',
        'o': '0',
        'I': '1',
        'l': '1',
        'Z': '2',
        'S': '5',
        'B': '8',
        '€': 'EUR',
        '£': 'EUR',
        '$': 'EUR',
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return text

def parse_date(text):
    """Versucht Datum aus Text zu extrahieren"""
    date_patterns = [
        r'(\d{1,2})[\.\/](\d{1,2})[\.\/](\d{2,4})',
        r'(\d{1,2})[\.\s]+([A-Za-zäöüß]+)[\.\s]+(\d{2,4})',
        r'(\d{1,2})[\.\-](\d{1,2})[\.\-](\d{2,4})',
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            try:
                day, month, year = match.groups()
                if len(year) == 2:
                    year = '20' + year
                return f"{day}.{month}.{year}"
            except:
                pass
    
    # Heutiges Datum als Fallback
    return datetime.now().strftime("%d.%m.%Y")

def extract_shop_name(text):
    """Extrahiert Geschäftsnamen"""
    shop_keywords = {
        'REWE': 'REWE',
        'EDEKA': 'EDEKA',
        'ALDI': 'ALDI',
        'LIDL': 'LIDL',
        'KAUFLAND': 'KAUFLAND',
        'NETTO': 'NETTO',
        'PENNY': 'PENNY',
        'DM': 'DM',
        'ROSSMANN': 'ROSSMANN',
        'TEGUT': 'TEGUT',
        'BAUHAUS': 'BAUHAUS',
        'HORNBACH': 'HORNBACH',
        'OBIMARKT': 'OBIMARKT',
        'BIO COMPANY': 'BIO COMPANY',
        'DENNS': 'DENNS',
        'ALNATURA': 'ALNATURA',
    }
    
    text_upper = text.upper()
    for keyword, shop in shop_keywords.items():
        if keyword in text_upper:
            return shop
    
    # Versuche aus ersten Zeilen zu extrahieren
    lines = text.split('\n')[:5]
    for line in lines:
        if len(line) > 3 and len(line) < 50:
            clean_line = re.sub(r'[^\w\s]', '', line).strip()
            if clean_line and not clean_line.isdigit():
                return clean_line[:30]
    
    return "Unbekannt"

def extract_amounts(text):
    """Extrahiert Beträge aus Text"""
    # Suche nach Geldbeträgen (z.B. 12,99, 12.99, 12,99€, 12.99 EUR)
    amount_patterns = [
        r'(\d+[,\.]\d{2})\s*[€$£]?',
        r'[€$£]\s*(\d+[,\.]\d{2})',
        r'SUMME[:\s]*(\d+[,\.]\d{2})',
        r'TOTAL[:\s]*(\d+[,\.]\d{2})',
        r'ZUZAHLEN[:\s]*(\d+[,\.]\d{2})',
    ]
    
    amounts = []
    for pattern in amount_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            # Standardisiere Dezimaltrenner
            amount = match.replace(',', '.')
            try:
                amount_float = float(amount)
                if amount_float > 0:
                    amounts.append(amount_float)
            except:
                pass
    
    # Größter Betrag ist wahrscheinlich der Gesamtbetrag
    if amounts:
        return {
            'all_amounts': amounts,
            'total': max(amounts),
            'possible_total': sorted(amounts, reverse=True)[:3]
        }
    
    return {'all_amounts': [], 'total': 0, 'possible_total': []}

def parse_products_with_regex(text):
    """
    Versucht Produkte mit Regex zu parsen
    (Als Fallback wenn keine KI verfügbar ist)
    """
    products = []
    
    # Typische Produktmuster in deutschen Rechnungen
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        line_clean = line.strip()
        
        # Ignoriere offensichtliche Nicht-Produkt-Zeilen
        if (len(line_clean) < 3 or 
            line_clean.startswith(('Rechnung', 'Quittung', 'Kassenzettel', 'SUMME', 'TOTAL', 'EUR', '€')) or
            'MwSt' in line_clean or 'UST' in line_clean.upper()):
            continue
        
        # Suche nach Preis am Ende der Zeile
        price_match = re.search(r'(\d+[,\.]\d{2})\s*[A-Z]?$', line_clean)
        if price_match:
            price_str = price_match.group(1).replace(',', '.')
            try:
                price = float(price_str)
                # Produktname ist alles vor dem Preis
                product_name = line_clean[:price_match.start()].strip()
                
                # Versuche Menge zu finden
                quantity = 1
                qty_match = re.search(r'^(\d+[,\.]?\d*)\s*[xX]', product_name)
                if qty_match:
                    qty_str = qty_match.group(1).replace(',', '.')
                    try:
                        quantity = float(qty_str)
                        product_name = product_name[qty_match.end():].strip()
                    except:
                        pass
                
                if product_name and len(product_name) > 1:
                    products.append({
                        'name': product_name[:100],
                        'quantity': quantity,
                        'price': price,
                        'total': round(quantity * price, 2) if quantity != 1 else price,
                        'line_number': i + 1,
                        'confidence': 'medium'
                    })
            except:
                pass
    
    return products

def enhance_product_names(products, shop_name):
    """
    Verbessert Produktnamen basierend auf typischen Mustern
    """
    product_corrections = {
        'KASTANE': 'KASTANIEN',
        'KASTANIE': 'KASTANIEN',
        'TOMAT': 'TOMATEN',
        'GURK': 'GURKE',
        'PAPRIK': 'PAPRIKA',
        'ZUCCHIN': 'ZUCCHINI',
        'AVOCAD': 'AVOCADO',
        'BANAN': 'BANANE',
        'APFEL': 'ÄPFEL',
        'BROT': 'BROT',
        'MILCH': 'MILCH',
        'EIER': 'EIER',
        'KAESE': 'KÄSE',
        'BUTTER': 'BUTTER',
        'BIO': 'BIO',
        'ORGANIC': 'BIO',
        'FISCH': 'FISCH',
        'FLEISCH': 'FLEISCH',
        'WURST': 'WURST',
        'AUFSTRICH': 'AUFSTRICH',
    }
    
    for product in products:
        name_upper = product['name'].upper()
        
        # Korrektur bekannte Fehler
        for wrong, correct in product_corrections.items():
            if wrong in name_upper:
                # Ersetze nur den falschen Teil
                product['name'] = product['name'].replace(wrong, correct)
                product['confidence'] = 'high'
                break
        
        # Entferne Preiszeichen etc.
        product['name'] = re.sub(r'[\d.,]+\s*[€$£]?$', '', product['name']).strip()
        
        # Wenn Name sehr kurz, versuche zu erraten
        if len(product['name']) < 3 and product['price'] > 0:
            if product['price'] < 1:
                product['name'] = "Stückware (klein)"
            elif product['price'] < 3:
                product['name'] = "Obst/Gemüse"
            elif product['price'] < 10:
                product['name'] = "Lebensmittel"
            else:
                product['name'] = "Größerer Artikel"
            product['confidence'] = 'low'
    
    return products

def process_with_openai(text, shop_name):
    """
    Nutzt OpenAI API um Produkte zu extrahieren
    (Optional - erfordert API-Key)
    """
    if not USE_OPENAI or not OPENAI_API_KEY:
        return None
    
    try:
        openai.api_key = OPENAI_API_KEY
        
        prompt = f"""Extrahiere alle Einkaufsprodukte aus dieser Rechnung von {shop_name}.
        
Rechnungstext:
{text[:3000]}

Gib die Produkte als JSON-Array zurück mit folgenden Feldern für jedes Produkt:
- name: Produktname (deutsch, korrigiere OCR-Fehler)
- quantity: Menge (Zahl, z.B. 1, 2, 0.5 für halbe Kilo, etc.)
- price: Einzelpreis in EUR
- total: Gesamtpreis für diese Menge

Wenn du einen Produktnamen nicht entziffern kannst, aber eine Vermutung hast, 
schreibe die Vermutung mit Fragezeichen, z.B. "BIO KASTANIEN?".
Wenn du gar keine Idee hast, schreibe "nicht entzifferbar".

Beispielantwort:
[
  {{"name": "BIO BANANEN", "quantity": 1.2, "price": 2.99, "total": 3.59}},
  {{"name": "VOLLKORNBROT", "quantity": 1, "price": 3.49, "total": 3.49}},
  {{"name": "BIO KASTANIEN?", "quantity": 1, "price": 4.99, "total": 4.99}}
]"""
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Du bist ein hilfreicher Assistent, der Rechnungen analysiert und Produkte extrahiert. Antworte immer mit gültigem JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        result = response.choices[0].message.content
        
        # Extrahiere JSON aus der Antwort
        json_match = re.search(r'\[.*\]', result, re.DOTALL)
        if json_match:
            products = json.loads(json_match.group())
            for product in products:
                product['confidence'] = 'ai_high'
            return products
        
    except Exception as e:
        print(f"OpenAI Fehler: {e}")
    
    return None

def generate_filename(invoice_data):
    """Generiert einen aussagekräftigen Dateinamen"""
    date_str = invoice_data.get('date', 'unbekannt').replace('.', '-')
    shop = invoice_data.get('shop', 'Unbekannt').replace(' ', '_')
    total = invoice_data.get('total_amount', 0)
    
    # Kurzform für Dateinamen
    shop_short = shop[:15]
    
    filename = f"{date_str}_{shop_short}_{total:.2f}EUR"
    
    # Entferne ungültige Zeichen
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    return filename[:100] + invoice_data['original_extension']

# ============ HAUPTFUNKTION ============
def process_invoices():
    """Verarbeitet alle Rechnungen im Eingabeordner"""
    
    print("=== RECHNUNGSVERARBEITUNG ===")
    print(f"Eingabeverzeichnis: {INPUT_DIR}")
    print(f"Ausgabeverzeichnis: {EXTRACTED_DATA_DIR}")
    print("=" * 50)
    
    # Erstelle Eingabeordner falls nicht existent
    INPUT_DIR.mkdir(exist_ok=True)
    
    all_invoices = []
    processed_files = []
    
    # Unterstützte Dateiformate
    supported_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.bmp', '.tiff']
    
    for file_path in INPUT_DIR.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
            print(f"\nVerarbeite: {file_path.name}")
            
            # 1. Text extrahieren
            if file_path.suffix.lower() == '.pdf':
                text = extract_text_from_pdf(file_path)
            else:
                text = extract_text_from_image(file_path)
            
            text = clean_ocr_text(text)
            
            # 2. Metadaten extrahieren
            invoice_data = {
                'original_filename': file_path.name,
                'original_path': str(file_path),
                'original_extension': file_path.suffix,
                'extraction_date': datetime.now().isoformat(),
                'shop': extract_shop_name(text),
                'date': parse_date(text),
                'raw_text_preview': text[:1000],
                'total_text_length': len(text)
            }
            
            # 3. Beträge extrahieren
            amounts = extract_amounts(text)
            invoice_data.update(amounts)
            
            # 4. Produkte extrahieren (versuche zuerst mit KI)
            products = None
            if USE_OPENAI:
                products = process_with_openai(text, invoice_data['shop'])
            
            # Fallback: Regex-Parsing
            if not products:
                products = parse_products_with_regex(text)
                products = enhance_product_names(products, invoice_data['shop'])
            
            invoice_data['products'] = products
            
            # 5. Gesamt aus Produkten berechnen (wenn möglich)
            product_total = sum(p.get('total', 0) for p in products)
            if product_total > 0:
                invoice_data['product_total'] = round(product_total, 2)
                invoice_data['discrepancy'] = round(invoice_data.get('total', 0) - product_total, 2)
            
            # 6. Dateinamen für Umbenennung generieren
            invoice_data['suggested_filename'] = generate_filename(invoice_data)
            
            # 7. Speichern als JSON
            output_file = EXTRACTED_DATA_DIR / f"{file_path.stem}_data.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(invoice_data, f, ensure_ascii=False, indent=2)
            
            all_invoices.append(invoice_data)
            processed_files.append(file_path)
            
            print(f"  → Shop: {invoice_data['shop']}")
            print(f"  → Datum: {invoice_data['date']}")
            print(f"  → Gesamt: {invoice_data.get('total', 0):.2f} EUR")
            print(f"  → Produkte: {len(products)}")
            print(f"  → Gespeichert: {output_file.name}")
    
    # 8. Zusammenfassung aller Rechnungen erstellen
    if all_invoices:
        summary = {
            'processing_date': datetime.now().isoformat(),
            'total_invoices': len(all_invoices),
            'total_amount': sum(i.get('total', 0) for i in all_invoices),
            'invoices': all_invoices
        }
        
        summary_file = EXTRACTED_DATA_DIR / "alle_rechnungen_zusammenfassung.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        # CSV für einfache Analyse
        csv_data = []
        for inv in all_invoices:
            for product in inv.get('products', []):
                csv_data.append({
                    'Rechnung': inv['original_filename'],
                    'Datum': inv['date'],
                    'Shop': inv['shop'],
                    'Produkt': product.get('name', ''),
                    'Menge': product.get('quantity', 1),
                    'Einzelpreis': product.get('price', 0),
                    'Gesamt': product.get('total', 0),
                    'Vertrauen': product.get('confidence', 'unknown')
                })
        
        if csv_data:
            df = pd.DataFrame(csv_data)
            csv_file = EXTRACTED_DATA_DIR / "produkte_alle_rechnungen.csv"
            df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        
        print(f"\n{'='*50}")
        print(f"VERARBEITUNG ABGESCHLOSSEN")
        print(f"Gesamte Rechnungen: {len(all_invoices)}")
        print(f"Gesamtbetrag aller Rechnungen: {summary['total_amount']:.2f} EUR")
        print(f"Zusammenfassung: {summary_file}")
        print(f"CSV-Datei: {EXTRACTED_DATA_DIR / 'produkte_alle_rechnungen.csv'}")
        
        # Vorschlag für nächsten Schritt
        print(f"\nNächster Schritt:")
        print(f"1. Überprüfen Sie die extrahierten Daten in: {EXTRACTED_DATA_DIR}")
        print(f"2. Korrigieren Sie ggf. die Produktnamen in den JSON-Dateien")
        print(f"3. Führen Sie das Umbenennungsskript aus")
    
    return all_invoices

if __name__ == "__main__":
    process_invoices()