"""
Intelligente Generierung von Dateinamen
"""

import re
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

class FilenameGenerator:
    def __init__(self, config: Dict):
        self.config = config
        self.naming_scheme = config.get('naming_scheme', 'descriptive')
        
    def generate_filename(self, file_info: Dict, category: Optional[str] = None) -> str:
        """Generiert neuen Dateinamen basierend auf Schema"""
        original_name = Path(file_info['filename']).stem
        extension = file_info['extension']
        
        if self.naming_scheme == 'descriptive':
            return self.generate_descriptive_name(file_info, extension)
        elif self.naming_scheme == 'timestamp':
            return self.generate_timestamp_name(file_info, extension)
        elif self.naming_scheme == 'category_based':
            return self.generate_category_based_name(file_info, category, extension)
        else:
            return self.generate_hybrid_name(file_info, category, extension)
    
    def generate_image_name(self, description: str, extension: str) -> str:
        """Generiert Dateinamen für Bilder basierend auf Beschreibung"""
        # Bereinige Beschreibung
        clean_desc = self.clean_for_filename(description)
        
        # Kürze wenn nötig
        if len(clean_desc) > 50:
            clean_desc = clean_desc[:50]
        
        # Timestamp hinzufügen
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Stelle sicher, dass Extension mit Punkt beginnt
        if not extension.startswith('.'):
            extension = '.' + extension
        
        return f"{clean_desc}_{timestamp}{extension}"
    
    def generate_descriptive_name(self, file_info: Dict, extension: str) -> str:
        """Generiert beschreibenden Namen"""
        # Versuche aus Metadaten zu generieren
        description = self.extract_description(file_info)
        
        # Bereinige für Dateinamen
        clean_desc = self.clean_for_filename(description)
        
        # Füge Datum hinzu
        date_str = datetime.now().strftime("%Y%m%d")
        
        # Baue finalen Namen
        if len(clean_desc) > 0:
            filename = f"{clean_desc}_{date_str}{extension}"
        else:
            # Fallback: Originalname mit Datum
            original_stem = Path(file_info['filename']).stem
            filename = f"{original_stem}_{date_str}{extension}"
        
        return filename
    
    def extract_description(self, file_info: Dict) -> str:
        """Extrahiert Beschreibung aus Dateimetadaten"""
        ext = file_info['extension']
        
        # Für Bilder
        if ext in ['.jpg', '.jpeg', '.png', '.webp']:
            return self.extract_image_description(file_info)
        
        # Für Dokumente
        elif ext in ['.pdf', '.docx', '.txt']:
            return self.extract_document_description(file_info)
        
        # Für Code
        elif ext in ['.py', '.js', '.java', '.cpp']:
            return self.extract_code_description(file_info)
        
        # Generische Methode
        else:
            return self.extract_generic_description(file_info)
    
    def extract_image_description(self, file_info: Dict) -> str:
        """Extrahiert Bildbeschreibung"""
        if 'analysis' in file_info and 'image' in file_info['analysis']:
            img_info = file_info['analysis']['image']
            
            # Verwende vorhandene Beschreibung
            if 'description' in img_info:
                return img_info['description']
            
            # Baue aus Objekten
            if 'objects' in img_info and img_info['objects']:
                objects = img_info['objects'][:3]  # Max 3 Objekte
                return f"bild_mit_{'_'.join(objects)}"
            
            # Verwende dominante Farbe
            if 'dominant_colors' in img_info and img_info['dominant_colors']:
                color = img_info['dominant_colors'][0].get('name', '')
                return f"{color}es_bild"
        
        return "bild"
    
    def extract_document_description(self, file_info: Dict) -> str:
        """Extrahiert Dokumentbeschreibung"""
        content = file_info.get('content_preview', '')
        
        # Einfache Schlüsselwort-Extraktion
        keywords = self.extract_keywords(content, max_words=5)
        
        if keywords:
            return f"dokument_{'_'.join(keywords)}"
        
        # Fallback: Dateinamen analysieren
        name = file_info['filename'].lower()
        
        # Häufige Muster erkennen
        patterns = {
            'rechnung': 'rechnung',
            'vertrag': 'vertrag',
            'lebenslauf': 'lebenslauf',
            'bewerbung': 'bewerbung',
            'notizen': 'notizen',
            'protokoll': 'protokoll'
        }
        
        for pattern, description in patterns.items():
            if pattern in name:
                return description
        
        return "dokument"
    
    def extract_code_description(self, file_info: Dict) -> str:
        """Extrahiert Code-Beschreibung"""
        content = file_info.get('content_preview', '').lower()
        filename = file_info['filename'].lower()
        
        # Erkenne Code-Typ
        if 'import' in content or 'def ' in content or 'class ' in content:
            return f"python_skript"
        elif '#include' in content or 'int main' in content:
            return f"c_programm"
        elif 'function' in content or 'const ' in content:
            return f"javascript_datei"
        
        # Aus Dateinamen
        if 'test' in filename:
            return "test_datei"
        elif 'util' in filename or 'helper' in filename:
            return "hilfsfunktionen"
        elif 'config' in filename or 'settings' in filename:
            return "konfiguration"
        
        return "code_datei"
    
    def extract_generic_description(self, file_info: Dict) -> str:
        """Generische Beschreibung"""
        return Path(file_info['filename']).stem.lower()
    
    def extract_keywords(self, text: str, max_words: int = 5) -> List[str]:
        """Extrahiert Schlüsselwörter aus Text"""
        # Einfache Implementierung
        words = text.lower().split()
        
        # Entferne häufige Stoppwörter
        stopwords = {'der', 'die', 'das', 'und', 'oder', 'in', 'zu', 'von', 'mit', 'für', 'auf'}
        filtered = [w for w in words if w not in stopwords and len(w) > 3]
        
        # Nehme die häufigsten Wörter
        from collections import Counter
        common = Counter(filtered).most_common(max_words)
        
        return [word for word, _ in common]
    
    def clean_for_filename(self, text: str) -> str:
        """Bereinigt Text für Dateinamen"""
        # Entferne Sonderzeichen
        text = re.sub(r'[^\w\s-]', '', text)
        
        # Ersetze Leerzeichen mit Unterstrichen
        text = text.replace(' ', '_')
        
        # Entferne doppelte Unterstriche
        text = re.sub(r'_+', '_', text)
        
        # Kürze wenn nötig
        if len(text) > 40:
            text = text[:40]
        
        return text.strip('_').lower()
    
    def generate_timestamp_name(self, file_info: Dict, extension: str) -> str:
        """Generiert Namen mit Zeitstempel"""
        modified = file_info.get('modified', datetime.now().isoformat())
        
        try:
            dt = datetime.fromisoformat(modified.replace('Z', '+00:00'))
            timestamp = dt.strftime("%Y%m%d_%H%M%S")
        except:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        original_stem = Path(file_info['filename']).stem
        return f"{timestamp}_{original_stem[:20]}{extension}"
    
    def generate_category_based_name(self, file_info: Dict, category: str, extension: str) -> str:
        """Generiert Namen basierend auf Kategorie"""
        if not category:
            return self.generate_descriptive_name(file_info, extension)
        
        # Bereinige Kategorienamen
        clean_category = self.clean_for_filename(category)
        
        # Kürze Kategorie
        if len(clean_category) > 20:
            parts = clean_category.split('_')
            if len(parts) > 2:
                clean_category = '_'.join(parts[:2])
            else:
                clean_category = clean_category[:20]
        
        # Füge Datum hinzu
        date_str = datetime.now().strftime("%Y%m%d")
        
        return f"{clean_category}_{date_str}{extension}"
    
    def generate_hybrid_name(self, file_info: Dict, category: Optional[str], extension: str) -> str:
        """Kombiniert verschiedene Methoden"""
        descriptive = self.extract_description(file_info)
        clean_desc = self.clean_for_filename(descriptive)[:20]
        
        date_str = datetime.now().strftime("%Y%m%d")
        
        if category:
            clean_cat = self.clean_for_filename(category)[:15]
            return f"{clean_cat}_{clean_desc}_{date_str}{extension}"
        else:
            return f"{clean_desc}_{date_str}{extension}"
