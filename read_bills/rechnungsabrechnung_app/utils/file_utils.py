"""
Hilfsfunktionen für Dateioperationen
"""
from pathlib import Path
from typing import Optional
import os

def save_uploaded_file(uploaded_file, target_dir: Path) -> Optional[Path]:
    """
    Speichert eine hochgeladene Datei
    
    Args:
        uploaded_file: Streamlit uploaded file object
        target_dir: Zielverzeichnis
        
    Returns:
        Pfad zur gespeicherten Datei oder None
    """
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / uploaded_file.name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return file_path
    except Exception as e:
        print(f"Fehler beim Speichern der Datei: {e}")
        return None

def delete_file(file_path: Path) -> bool:
    """
    Löscht eine Datei
    
    Args:
        file_path: Pfad zur zu löschenden Datei
        
    Returns:
        True wenn erfolgreich, False sonst
    """
    try:
        if file_path.exists():
            os.remove(file_path)
            return True
        return False
    except Exception as e:
        print(f"Fehler beim Löschen der Datei: {e}")
        return False

def get_file_size(file_path: Path) -> Optional[int]:
    """
    Gibt die Dateigröße in Bytes zurück
    
    Args:
        file_path: Pfad zur Datei
        
    Returns:
        Dateigröße oder None
    """
    try:
        return file_path.stat().st_size if file_path.exists() else None
    except Exception as e:
        print(f"Fehler beim Abrufen der Dateigröße: {e}")
        return None
