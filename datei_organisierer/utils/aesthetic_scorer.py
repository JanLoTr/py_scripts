"""
Ästhetik-Bewertung für Bilder - Verbesserte Version
"""

import cv2
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Optional, TypedDict
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

# Logging konfigurieren
logger = logging.getLogger(__name__)


@dataclass
class ImageAnalysis:
    """Dataclass für Bildanalyse-Daten"""
    brightness: float
    contrast: float
    objects: List[str]
    faces: int
    colors: Dict[str, float]
    description: str = ""
    dominant_colors: Optional[List[Dict]] = None


class AestheticCategory(TypedDict):
    """TypedDict für Ästhetik-Kategorien"""
    name: str
    min_score: float
    max_score: float


class AestheticScorer:
    def __init__(self, config: Dict):
        self.config = config
        self.min_score = config.get('min_aesthetic_score', 0.7)
        self.categories = config.get('aesthetic_categories', [])
        self.thresholds = {
            'brightness_optimal_min': 0.4,
            'brightness_optimal_max': 0.7,
            'brightness_poor_min': 0.2,
            'brightness_poor_max': 0.9,
            'contrast_optimal_min': 0.3,
            'contrast_optimal_max': 0.7,
            'contrast_good_min': 0.8,
            'min_colors': 2,
            'max_colors': 5
        }
        
        # Thread Pool für parallele Verarbeitung
        self.executor = ThreadPoolExecutor(max_workers=4)
        
    def score_file(self, file_path: Path, file_info: Dict) -> float:
        """Bewertet die ästhetische Qualität einer Datei"""
        # Nur für Bilder
        valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.gif', '.tiff'}
        if file_info.get('extension', '').lower() not in valid_extensions:
            return 0.0
        
        try:
            # Nutze bereits vorhandene Bildanalyse
            if 'analysis' in file_info and 'image' in file_info['analysis']:
                img_analysis = file_info['analysis']['image']
                return self._calculate_aesthetic_score(img_analysis)
            
            # Fallback: Einfache Analyse
            return self._simple_image_analysis(file_path)
            
        except Exception as e:
            logger.warning(f"Fehler bei Ästhetik-Bewertung von {file_path}: {e}")
            return 0.0
    
    def _simple_image_analysis(self, file_path: Path) -> float:
        """Führt einfache Bildanalyse durch"""
        try:
            img = cv2.imread(str(file_path))
            if img is None:
                logger.warning(f"Bild konnte nicht geladen werden: {file_path}")
                return 0.0
            
            # Metriken berechnen
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            brightness = np.mean(gray) / 255.0
            contrast = gray.std() / 255.0
            
            # Qualitätsmetriken (Scharfheit/Blur Detection)
            sharpness = self._calculate_sharpness(gray)
            
            # Kombiniere Metriken mit Gewichtung
            weights = {
                'brightness': 0.25,
                'contrast': 0.35,
                'sharpness': 0.20,
                'color_variance': 0.20
            }
            
            # Farbvarianz berechnen
            color_variance = self._calculate_color_variance(img)
            
            # Gesamtscore berechnen
            score = (
                brightness * weights['brightness'] +
                contrast * weights['contrast'] +
                sharpness * weights['sharpness'] +
                color_variance * weights['color_variance']
            )
            
            # Normalisiere auf 0-1 Bereich
            return np.clip(score, 0.0, 1.0)
            
        except Exception as e:
            logger.error(f"Fehler bei einfacher Bildanalyse: {e}")
            return 0.0
    
    def _calculate_sharpness(self, gray_image: np.ndarray) -> float:
        """Berechnet die Schärfe des Bildes (Laplace Variance)"""
        try:
            laplacian = cv2.Laplacian(gray_image, cv2.CV_64F)
            sharpness = laplacian.var()
            # Normalisiere auf 0-1 Skala (empirische Werte)
            return np.clip(sharpness / 1000.0, 0.0, 1.0)
        except:
            return 0.5
    
    def _calculate_color_variance(self, img: np.ndarray) -> float:
        """Berechnet die Farbvarianz"""
        try:
            # In HSV konvertieren für bessere Farbanalyse
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            # Varianz im Hue-Kanal
            hue_variance = np.var(hsv[:,:,0])
            # Normalisiere (empirischer Wert)
            return np.clip(hue_variance / 10000.0, 0.0, 1.0)
        except:
            return 0.5
    
    def _calculate_aesthetic_score(self, img_analysis: Dict) -> float:
        """Berechnet ästhetischen Score aus Bildanalyse"""
        try:
            # Extrahiere Werte mit Defaults
            brightness = float(img_analysis.get('brightness', 0.5))
            contrast = float(img_analysis.get('contrast', 0.5))
            objects = img_analysis.get('objects', [])
            faces = int(img_analysis.get('faces', 0))
            colors = img_analysis.get('colors', {})
            
            score = 0.5  # Basis-Score
            
            # Helligkeits-Bewertung (kontinuierliche Funktion)
            brightness_score = self._rate_brightness(brightness)
            score += brightness_score
            
            # Kontrast-Bewertung
            contrast_score = self._rate_contrast(contrast)
            score += contrast_score
            
            # Objekte vorhanden (zeigt Komposition)
            if objects and len(objects) > 0:
                # Je mehr verschiedene Objekte, desto interessanter die Komposition
                unique_objects = len(set(objects[:5]))  # Max 5 Objekte betrachten
                object_score = min(0.15, unique_objects * 0.03)
                score += object_score
            
            # Gesichter (oft interessant)
            if faces > 0:
                # Mehr Gesichter = interessantere Szene
                face_score = min(0.1, faces * 0.05)
                score += face_score
            
            # Farbvielfalt (optimale Anzahl von Farben)
            color_count = len(colors)
            if self.thresholds['min_colors'] <= color_count <= self.thresholds['max_colors']:
                score += 0.1
            elif color_count > self.thresholds['max_colors']:
                # Zu viele Farben können unruhig wirken
                score -= 0.05
            
            # Bildbeschreibung berücksichtigen (falls vorhanden)
            if 'description' in img_analysis and img_analysis['description']:
                # Längere, detailliertere Beschreibung = bessere Qualität
                desc_length = len(img_analysis['description'].split())
                if desc_length >= 3:
                    score += 0.05
            
            # Normalisiere Score auf 0-1
            return np.clip(score, 0.0, 1.0)
            
        except Exception as e:
            logger.error(f"Fehler bei Ästhetik-Score-Berechnung: {e}")
            return 0.5
    
    def _rate_brightness(self, brightness: float) -> float:
        """Bewertet Helligkeit mit kontinuierlicher Funktion"""
        # Glockenförmige Kurve um optimalen Bereich (0.55)
        if 0.4 <= brightness <= 0.7:
            # Optimaler Bereich: maximale Punkte
            return 0.2
        elif 0.35 <= brightness < 0.4 or 0.7 < brightness <= 0.75:
            # Noch guter Bereich
            return 0.1
        elif 0.2 <= brightness < 0.35 or 0.75 < brightness <= 0.85:
            # Akzeptabler Bereich
            return 0.0
        else:
            # Zu dunkel oder zu hell
            return -0.1
    
    def _rate_contrast(self, contrast: float) -> float:
        """Bewertet Kontrast"""
        if 0.3 <= contrast <= 0.7:
            return 0.2
        elif 0.7 < contrast <= 0.85:
            return 0.1
        elif 0.15 <= contrast < 0.3:
            return 0.0
        else:
            return -0.05
    
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
                return 'interessant'
        return ''
    
    def find_aesthetic_files(self, results: List[Dict]) -> List[Dict]:
        """Findet alle ästhetisch interessanten Dateien (parallelisiert)"""
        aesthetic_files = []
        
        # Parallele Verarbeitung
        futures = []
        for file_info in results:
            future = self.executor.submit(self._process_file_for_aesthetics, file_info)
            futures.append((future, file_info))
        
        for future, file_info in futures:
            try:
                score = future.result(timeout=5.0)
                if score >= self.min_score:
                    file_info['aesthetic_score'] = score
                    file_info['aesthetic_category'] = self.get_aesthetic_category(score)
                    aesthetic_files.append(file_info)
            except Exception as e:
                logger.warning(f"Fehler bei paralleler Verarbeitung: {e}")
        
        # Sortiere nach Score (absteigend)
        aesthetic_files.sort(key=lambda x: x.get('aesthetic_score', 0), reverse=True)
        
        return aesthetic_files
    
    def _process_file_for_aesthetics(self, file_info: Dict) -> float:
        """Verarbeitet Datei für Ästhetik-Bewertung"""
        try:
            file_path = Path(file_info['path'])
            return self.score_file(file_path, file_info)
        except Exception as e:
            logger.warning(f"Fehler bei Verarbeitung von {file_info.get('filename')}: {e}")
            return 0.0
    
    def batch_score_files(self, files: List[Dict]) -> Dict[str, List[Dict]]:
        """Bewertet mehrere Dateien und gruppiert nach Kategorie"""
        categorized = {
            'inspiration': [],
            'kunst': [],
            'design': [],
            'schön': [],
            'interessant': [],
            'other': []
        }
        
        for file_info in files:
            try:
                file_path = Path(file_info['path'])
                score = self.score_file(file_path, file_info)
                
                if score >= self.min_score:
                    category = self.get_aesthetic_category(score)
                    file_info['aesthetic_score'] = score
                    file_info['aesthetic_category'] = category
                    
                    if category in categorized:
                        categorized[category].append(file_info)
                    else:
                        categorized['other'].append(file_info)
                        
            except Exception as e:
                logger.warning(f"Fehler bei Batch-Bewertung: {e}")
                continue
        
        return categorized
    
    def close(self):
        """Ressourcen freigeben"""
        self.executor.shutdown(wait=True)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
