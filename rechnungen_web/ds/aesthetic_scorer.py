"""
Bildanalyse ohne KI-API (lokal mit YOLO und OpenCV)
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PIL import Image
import torch
from ultralytics import YOLO
import colorsys
from collections import Counter

class ImageAnalyzer:
    def __init__(self, config: Dict):
        self.config = config
        self.yolo_model = None
        self.color_names = self.load_color_names()
        
        # YOLO Modell laden (falls aktiviert)
        if config.get('image_analysis', {}).get('use_yolo', True):
            self.load_yolo_model()
    
    def load_yolo_model(self):
        """Lädt YOLO-Modell für Objekterkennung"""
        try:
            model_path = self.config.get('image_analysis', {}).get('yolo_model', 'yolov8n.pt')
            self.yolo_model = YOLO(model_path)
            print(f"✅ YOLO Modell geladen: {model_path}")
        except Exception as e:
            print(f"⚠️ YOLO Modell konnte nicht geladen werden: {e}")
            print("   Verwende einfache Bildanalyse ohne Objekterkennung")
    
    def load_color_names(self) -> Dict:
        """Lädt Farbnamen für Beschreibung"""
        return {
            (255, 0, 0): "rot",
            (0, 255, 0): "grün",
            (0, 0, 255): "blau",
            (255, 255, 0): "gelb",
            (255, 0, 255): "magenta",
            (0, 255, 255): "cyan",
            (255, 255, 255): "weiß",
            (0, 0, 0): "schwarz",
            (128, 128, 128): "grau",
            (255, 165, 0): "orange",
            (128, 0, 128): "lila",
            (165, 42, 42): "braun",
            (255, 192, 203): "rosa"
        }
    
    def analyze_image(self, image_path: Path) -> Dict:
        """Analysiert ein Bild mit verschiedenen Methoden"""
        try:
            # Bild laden
            img = cv2.imread(str(image_path))
            if img is None:
                return {'error': 'Bild konnte nicht geladen werden'}
            
            # Grundlegende Informationen
            height, width, channels = img.shape
            analysis = {
                'dimensions': f"{width}x{height}",
                'size_kb': image_path.stat().st_size / 1024,
                'dominant_colors': self.get_dominant_colors(img),
                'brightness': self.get_brightness(img),
                'contrast': self.get_contrast(img),
                'colors': self.analyze_colors(img)
            }
            
            # Objekterkennung mit YOLO
            if self.yolo_model:
                objects = self.detect_objects(img)
                analysis['objects'] = objects
            
            # Gesichtserkennung (einfach mit OpenCV)
            if self.config.get('image_analysis', {}).get('detect_faces', True):
                faces = self.detect_faces(img)
                if faces:
                    analysis['faces'] = len(faces)
            
            # Szene beschreiben
            analysis['description'] = self.describe_scene(analysis)
            
            return analysis
            
        except Exception as e:
            return {'error': str(e)}
    
    def get_dominant_colors(self, img: np.ndarray, n_colors: int = 3) -> List[Dict]:
        """Ermittelt die dominanten Farben im Bild"""
        # Bild in RGB konvertieren
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Pixel umformen
        pixels = img_rgb.reshape(-1, 3)
        
        # K-Means für Farbclustering (vereinfacht)
        from sklearn.cluster import KMeans
        kmeans = KMeans(n_clusters=n_colors, random_state=42, n_init=10)
        kmeans.fit(pixels)
        
        # Farben und Anteile
        colors = kmeans.cluster_centers_.astype(int)
        counts = np.bincount(kmeans.labels_)
        percentages = (counts / len(pixels) * 100).round(2)
        
        dominant = []
        for color, percent in zip(colors, percentages):
            color_name = self.get_color_name(color)
            dominant.append({
                'rgb': color.tolist(),
                'name': color_name,
                'percentage': float(percent)
            })
        
        return dominant
    
    def get_color_name(self, rgb: np.ndarray) -> str:
        """Gibt den Namen der nächsten bekannten Farbe zurück"""
        min_dist = float('inf')
        closest_name = "unbekannt"
        
        for known_rgb, name in self.color_names.items():
            dist = np.linalg.norm(rgb - np.array(known_rgb))
            if dist < min_dist:
                min_dist = dist
                closest_name = name
        
        return closest_name
    
    def get_brightness(self, img: np.ndarray) -> float:
        """Berechnet die Helligkeit des Bildes"""
        # In Graustufen konvertieren
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return float(np.mean(gray) / 255.0)
    
    def get_contrast(self, img: np.ndarray) -> float:
        """Berechnet den Kontrast des Bildes"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return float(gray.std() / 255.0)
    
    def analyze_colors(self, img: np.ndarray) -> Dict:
        """Analysiert Farbverteilung"""
        img_hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # Farbbereiche definieren (HSV)
        color_ranges = {
            'rot': [(0, 50, 50), (10, 255, 255), (170, 50, 50), (180, 255, 255)],
            'grün': [(35, 50, 50), (85, 255, 255)],
            'blau': [(100, 50, 50), (130, 255, 255)],
            'gelb': [(20, 50, 50), (35, 255, 255)],
            'lila': [(130, 50, 50), (170, 255, 255)],
            'orange': [(10, 50, 50), (20, 255, 255)],
            'rosa': [(150, 30, 30), (170, 255, 255)]
        }
        
        total_pixels = img.shape[0] * img.shape[1]
        color_percentages = {}
        
        for color_name, ranges in color_ranges.items():
            mask = None
            if len(ranges) == 2:
                lower = np.array(ranges[0])
                upper = np.array(ranges[1])
                mask = cv2.inRange(img_hsv, lower, upper)
            elif len(ranges) == 4:
                # Zwei Bereiche für Rot
                lower1 = np.array(ranges[0])
                upper1 = np.array(ranges[1])
                lower2 = np.array(ranges[2])
                upper2 = np.array(ranges[3])
                mask1 = cv2.inRange(img_hsv, lower1, upper1)
                mask2 = cv2.inRange(img_hsv, lower2, upper2)
                mask = cv2.bitwise_or(mask1, mask2)
            
            if mask is not None:
                percentage = (np.sum(mask > 0) / total_pixels) * 100
                if percentage > 5:  # Nur signifikante Farben
                    color_percentages[color_name] = float(percentage.round(2))
        
        return color_percentages
    
    def detect_objects(self, img: np.ndarray) -> List[str]:
        """Erkennt Objekte im Bild mit YOLO"""
        if self.yolo_model is None:
            return []
        
        try:
            # YOLO ausführen
            results = self.yolo_model(img, verbose=False)
            
            # Extrahiere erkannte Objekte
            objects = []
            for result in results:
                if result.boxes is not None:
                    for box in result.boxes:
                        class_id = int(box.cls[0])
                        class_name = self.yolo_model.names[class_id]
                        confidence = float(box.conf[0])
                        
                        # Nur Objekte mit ausreichender Konfidenz
                        if confidence > 0.5:
                            objects.append(class_name)
            
            # Einzigartige Objekte, sortiert nach Häufigkeit
            from collections import Counter
            object_counts = Counter(objects)
            sorted_objects = [obj for obj, _ in object_counts.most_common(10)]
            
            return sorted_objects
            
        except Exception as e:
            print(f"⚠️ Objekterkennung fehlgeschlagen: {e}")
            return []
    
    def detect_faces(self, img: np.ndarray) -> List:
        """Erkennt Gesichter mit OpenCV Haarcascade"""
        try:
            # Lade Gesichtserkennungs-Klassifikator
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            face_cascade = cv2.CascadeClassifier(cascade_path)
            
            # In Graustufen konvertieren
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Gesichter erkennen
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30)
            )
            
            return faces.tolist() if len(faces) > 0 else []
            
        except Exception as e:
            print(f"⚠️ Gesichtserkennung fehlgeschlagen: {e}")
            return []
    
    def describe_scene(self, analysis: Dict) -> str:
        """Generiert eine Textbeschreibung der Szene"""
        parts = []
        
        # Größe und Qualität
        if 'dimensions' in analysis:
            parts.append(f"Bild mit {analysis['dimensions']} Pixeln")
        
        # Helligkeit
        brightness = analysis.get('brightness', 0.5)
        if brightness > 0.7:
            parts.append("helles")
        elif brightness < 0.3:
            parts.append("dunkles")
        
        # Kontrast
        contrast = analysis.get('contrast', 0.5)
        if contrast > 0.7:
            parts.append("kontrastreiches")
        elif contrast < 0.3:
            parts.append("kontrastarmes")
        
        # Farben
        colors = analysis.get('colors', {})
        if colors:
            dominant_color = max(colors.items(), key=lambda x: x[1])[0] if colors else None
            if dominant_color:
                parts.append(f"{dominant_color}es")
        
        # Objekte
        objects = analysis.get('objects', [])
        if objects:
            # Gruppiere ähnliche Objekte
            object_groups = {
                'person': ['person', 'man', 'woman', 'child'],
                'vehicle': ['car', 'truck', 'bus', 'motorcycle', 'bicycle'],
                'animal': ['dog', 'cat', 'bird', 'horse', 'sheep', 'cow'],
                'food': ['apple', 'banana', 'orange', 'pizza', 'sandwich'],
                'furniture': ['chair', 'table', 'couch', 'bed']
            }
            
            detected_groups = []
            for group_name, group_items in object_groups.items():
                if any(obj in objects for obj in group_items):
                    detected_groups.append(group_name)
            
            if detected_groups:
                parts.append(f"mit {', '.join(detected_groups[:2])}")
            elif len(objects) > 0:
                parts.append(f"mit {objects[0]}")
        
        # Gesichter
        faces = analysis.get('faces', 0)
        if faces == 1:
            parts.append("mit einer Person")
        elif faces > 1:
            parts.append(f"mit {faces} Personen")
        
        # Baue Beschreibung zusammen
        if len(parts) == 0:
            return "Fotografie"
        
        description = ' '.join(parts)
        return description.capitalize()
    
    def describe_image(self, analysis: Dict) -> str:
        """Generiert detaillierte Bildbeschreibung für Dateinamen"""
        description_parts = []
        
        # Objekte
        objects = analysis.get('objects', [])
        if objects:
            # Nehme die 2-3 häufigsten Objekte
            unique_objects = list(dict.fromkeys(objects))[:3]
            if unique_objects:
                description_parts.append('_'.join(unique_objects))
        
        # Farbe
        colors = analysis.get('dominant_colors', [])
        if colors:
            dominant = colors[0]['name'] if colors[0]['percentage'] > 30 else None
            if dominant:
                description_parts.append(dominant)
        
        # Szene-Typ basierend auf Objekten
        if objects:
            if any(obj in ['person', 'face'] for obj in objects):
                description_parts.append('person')
            elif any(obj in ['car', 'bicycle', 'motorcycle'] for obj in objects):
                description_parts.append('verkehr')
            elif any(obj in ['tree', 'flower', 'plant'] for obj in objects):
                description_parts.append('natur')
        
        # Helligkeit
        brightness = analysis.get('brightness', 0.5)
        if brightness > 0.8:
            description_parts.append('hell')
        elif brightness < 0.3:
            description_parts.append('dunkel')
        
        # Falls keine Beschreibung, generische
        if not description_parts:
            description_parts.append('bild')
        
        return '_'.join(description_parts)