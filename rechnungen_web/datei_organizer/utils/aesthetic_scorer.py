"""
Ästhetik-Bewertung für Bilder
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List

class AestheticScorer:
    def __init__(self, config: Dict):
        self.config = config
        self.min_score = config.get('min_aesthetic_score', 0.7)
        self.categories = config.get('aesthetic_categories', [])
    
    def score_file(self, file_path: Path, file_info: Dict) -> float:
        """Bewertet die ästhetische Qualität einer Datei"""
        # Nur für Bilder
        if file_info['extension'] not in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
            return 0.0
        
        # Nutze bereits vorhandene Bildanalyse
        if 'analysis' in file_info and 'image' in file_info['analysis']:
            img_analysis = file_info['analysis']['image']
            return self._calculate_aesthetic_score(img_analysis)
        
        # Fallback: Einfache Analyse
        try:
            img = cv2.imread(str(file_path))
            if img is None:
                return 0.0
            
            # Einfache Metriken
            brightness = np.mean(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)) / 255.0
            contrast = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).std() / 255.0
            
            # Kombiniere Metriken
            score = (brightness * 0.3 + contrast * 0.4 + 0.3) / 1.0
            return min(1.0, max(0.0, score))
        except:
            return 0.0
    
    def _calculate_aesthetic_score(self, img_analysis: Dict) -> float:
        """Berechnet ästhetischen Score aus Bildanalyse"""
        score = 0.5  # Basis-Score
        
        # Helligkeit (optimal zwischen 0.4 und 0.7)
        brightness = img_analysis.get('brightness', 0.5)
        if 0.4 <= brightness <= 0.7:
            score += 0.2
        elif brightness < 0.2 or brightness > 0.9:
            score -= 0.1
        
        # Kontrast (höher ist besser, aber nicht zu extrem)
        contrast = img_analysis.get('contrast', 0.5)
        if 0.3 <= contrast <= 0.7:
            score += 0.2
        elif contrast > 0.8:
            score += 0.1
        
        # Objekte vorhanden (zeigt Komposition)
        if 'objects' in img_analysis and len(img_analysis['objects']) > 0:
            score += 0.1
        
        # Gesichter (oft interessant)
        if img_analysis.get('faces', 0) > 0:
            score += 0.1
        
        # Farbvielfalt (aber nicht zu bunt)
        colors = img_analysis.get('colors', {})
        if 2 <= len(colors) <= 5:
            score += 0.1
        
        return min(1.0, max(0.0, score))
    
    def get_aesthetic_category(self, score: float) -> str:
        """Gibt Kategorie basierend auf Score zurück"""
        if score >= self.min_score:
            # Wähle passende Kategorie
            if score >= 0.9:
                return 'inspiration'
            elif score >= 0.85:
                return 'kunst'
            elif score >= 0.8:
                return 'design'
            elif score >= 0.75:
                return 'schön'
            else:
                return 'inspiration'
        return ''
    
    def find_aesthetic_files(self, results: List[Dict]) -> List[Dict]:
        """Findet alle ästhetisch interessanten Dateien"""
        aesthetic_files = []
        
        for file_info in results:
            file_path = Path(file_info['path'])
            score = self.score_file(file_path, file_info)
            
            if score >= self.min_score:
                aesthetic_files.append(file_info)
        
        return aesthetic_files
