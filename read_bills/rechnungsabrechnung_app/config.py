"""
Konfigurationsdatei für die Rechnungsabrechnung App
"""
import os
from pathlib import Path

# Verzeichnisse
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
PROCESSED_DIR = DATA_DIR / "processed"

# Stelle sicher, dass die Verzeichnisse existieren
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)

# API-Konfiguration (wird über UI eingegeben)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# OCR-Konfiguration
OCR_LANGUAGE = "deu+eng"  # Deutsch + Englisch

# App-Einstellungen
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
SUPPORTED_FORMATS = [".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"]

