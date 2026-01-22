"""
Textverarbeitungsfunktionen
"""
from typing import List, Dict, Optional
import re

def clean_ocr_text(text: str) -> str:
    """
    Bereinigt OCR-erkannten Text
    
    Args:
        text: Roher OCR-Text
        
    Returns:
        Bereinigter Text
    """
    # Entferne extra Whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Entferne seltsame Zeichen aber behalte Währungen und Punkte
    text = re.sub(r'[^\w\s\.,;:€$\-()ÄÖÜäöüß]', '', text)
    return text

def extract_numbers(text: str) -> List[float]:
    """
    Extrahiert Zahlen aus Text
    
    Args:
        text: Eingangstext
        
    Returns:
        Liste von gefundenen Zahlen
    """
    pattern = r'\d+(?:[.,]\d{1,2})?'
    matches = re.findall(pattern, text)
    numbers = []
    for match in matches:
        try:
            # Konvertiere Deutsche Notation (comma) zu Standard (dot)
            num = float(match.replace(',', '.'))
            numbers.append(num)
        except ValueError:
            continue
    return numbers

def extract_currency_amounts(text: str) -> List[Dict[str, any]]:
    """
    Extrahiert Währungsbeträge aus Text
    
    Args:
        text: Eingangstext
        
    Returns:
        Liste von Währungsbeträgen mit Währung
    """
    pattern = r'(€|\$|EUR|USD)?\s*(\d+(?:[.,]\d{1,2})?)'
    matches = re.findall(pattern, text)
    amounts = []
    for currency, amount in matches:
        try:
            num = float(amount.replace(',', '.'))
            amounts.append({
                'currency': currency or 'EUR',
                'amount': num
            })
        except ValueError:
            continue
    return amounts

def split_into_lines(text: str) -> List[str]:
    """
    Teilt Text in Zeilen auf und bereinigt diese
    
    Args:
        text: Eingangstext
        
    Returns:
        Liste von bereinigte Zeilen
    """
    lines = text.split('\n')
    cleaned_lines = [line.strip() for line in lines if line.strip()]
    return cleaned_lines

def remove_actions_and_discounts(text: str) -> str:
    """
    Entfernt Aktions- und Rabatt-Zeilen aus Text
    
    Args:
        text: Eingangstext
        
    Returns:
        Text ohne Aktionen/Rabatte
    """
    lines = split_into_lines(text)
    filtered_lines = []
    
    skip_patterns = [
        r'(?i)aktion',
        r'(?i)rabatt',
        r'(?i)discount',
        r'(?i)preis\s*-',
        r'(?i)reduziert',
        r'(?i)angebot',
        r'(?i)ersparnis',
    ]
    
    for line in lines:
        skip = False
        for pattern in skip_patterns:
            if re.search(pattern, line):
                skip = True
                break
        if not skip:
            filtered_lines.append(line)
    
    return '\n'.join(filtered_lines)

def extract_product_price_pairs(text: str) -> List[Dict[str, str]]:
    """
    Extrahiert Produkt-Preis-Paare aus Text
    
    Args:
        text: Rechnungstext
        
    Returns:
        Liste von Produkten und Preisen
    """
    lines = split_into_lines(text)
    pairs = []
    
    for line in lines:
        # Suche nach Muster: Text ... Preis
        match = re.search(r'(.+?)\s+(\d+[.,]\d{1,2})\s*€?$', line.strip())
        if match:
            product = match.group(1).strip()
            price = match.group(2).strip()
            pairs.append({
                'product': product,
                'price': price
            })
    
    return pairs

