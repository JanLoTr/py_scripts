"""
OCR-Funktionen für Rechnungsverarbeitung
"""
from pathlib import Path
from typing import Optional
import pytesseract
from PIL import Image
from config import OCR_LANGUAGE

def extract_text_from_image(image_path: Path) -> Optional[str]:
    """
    Extrahiert Text aus einem Bild mittels OCR
    
    Args:
        image_path: Pfad zum Bild
        
    Returns:
        Extrahierter Text oder None
    """
    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image, lang=OCR_LANGUAGE)
        return text
    except Exception as e:
        print(f"Fehler bei der OCR-Verarbeitung: {e}")
        return None

def preprocess_image(image_path: Path, output_path: Path) -> bool:
    """
    Führt eine Bildvorverarbeitung durch
    
    Args:
        image_path: Eingabe-Bildpfad
        output_path: Ausgabe-Bildpfad
        
    Returns:
        True wenn erfolgreich, False sonst
    """
    try:
        image = Image.open(image_path)
        # Konvertiere zu Graustufen für bessere OCR-Ergebnisse
        gray_image = image.convert('L')
        gray_image.save(output_path)
        return True
    except Exception as e:
        print(f"Fehler bei der Bildvorverarbeitung: {e}")
        return False
