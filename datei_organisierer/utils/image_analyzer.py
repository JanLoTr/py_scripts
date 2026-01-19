"""
Bildanalyse ohne KI-API (lokal mit YOLO und OpenCV) - Verbesserte Version
"""

import cv2
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, TypedDict
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import colorsys
from collections import Counter
import time

try:
    from PIL import Image, UnidentifiedImageError, ImageOps
    from ultralytics import YOLO
    import torch
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    YOLO = None
    torch = None

# Logging konfigurieren
logger = logging.getLogger(__name__)


@dataclass
class ImageAnalysisResult:
    """Ergebnis der Bildanalyse"""
    success: bool
    dimensions: Optional[Tuple[int, int]] = None
    size_kb: float = 0.0
    dominant_colors: List[Dict] = field(default_factory=list)
    brightness: float = 0.0
    contrast: float = 0.0
    colors: Dict[str, float] = field(default_factory=dict)
    objects: List[str] = field(default_factory=list)
    faces: int = 0
    sharpness: float = 0.0
    description: str = ""
    processing_time: float = 0.0
    error: Optional[str] = None


class ImageAnalyzer:
    def __init__(self, config: Dict):
        self.config = config.get('image_analysis', {})
        
        # YOLO Modell laden (falls aktiviert und verfügbar)
        self.yolo_model = None
        self.yolo_classes = {}
        
        if self.config.get('use_yolo', True) and YOLO_AVAILABLE:
            self._load_yolo_model()
        else:
            logger.warning("YOLO nicht verfügbar oder deaktiviert. Verwende einfache Bildanalyse.")
        
        # Farberkennung
        self.color_names = self._load_color_names()
        self.color_thresholds = self._load_color_thresholds()
        
        # Performance-Optimierung
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.image_cache = {}
        self.cache_size = self.config.get('cache_size', 100)
        
        # Gesichtserkennung
        self.face_cascade = None
        if self.config.get('detect_faces', True):
            self._load_face_cascade()
        
        logger.info(f"ImageAnalyzer initialisiert (YOLO: {self.yolo_model is not None})")
    
    def _load_yolo_model(self):
        """Lädt YOLO-Modell für Objekterkennung"""
        try:
            model_path = self.config.get('yolo_model', 'yolov8n.pt')
            
            # Prüfe ob Modell existiert
            if not Path(model_path).exists():
                logger.warning(f"YOLO Modell nicht gefunden: {model_path}")
                return
            
            # Lade Modell mit Progress-Anzeige
            logger.info(f"Lade YOLO Modell: {model_path}")
            self.yolo_model = YOLO(model_path)
            
            # Teste Modell
            test_input = torch.zeros((1, 3, 640, 640))
            with torch.no_grad():
                _ = self.yolo_model(test_input)
            
            # Lade Klassen-Namen
            if hasattr(self.yolo_model, 'names'):
                self.yolo_classes = self.yolo_model.names
                logger.info(f"✅ YOLO Modell geladen mit {len(self.yolo_classes)} Klassen")
            else:
                logger.warning("YOLO Modell hat keine Klasseninformationen")
                self.yolo_model = None
                
        except Exception as e:
            logger.error(f"YOLO Modell konnte nicht geladen werden: {e}")
            self.yolo_model = None
    
    def _load_color_names(self) -> Dict:
        """Lädt Farbnamen für Beschreibung (erweitert)"""
        return {
            (255, 0, 0): "rot",
            (200, 0, 0): "dunkelrot",
            (255, 100, 100): "hellrot",
            (0, 255, 0): "grün",
            (0, 200, 0): "dunkelgrün",
            (100, 255, 100): "hellgrün",
            (0, 0, 255): "blau",
            (0, 0, 200): "dunkelblau",
            (100, 100, 255): "hellblau",
            (255, 255, 0): "gelb",
            (255, 200, 0): "orangegelb",
            (255, 255, 100): "hellgelb",
            (255, 0, 255): "magenta",
            (200, 0, 200): "dunkelmagenta",
            (255, 100, 255): "hellmagenta",
            (0, 255, 255): "cyan",
            (0, 200, 200): "dunkelcyan",
            (100, 255, 255): "hellcyan",
            (255, 255, 255): "weiß",
            (200, 200, 200): "hellgrau",
            (128, 128, 128): "grau",
            (50, 50, 50): "dunkelgrau",
            (0, 0, 0): "schwarz",
            (255, 165, 0): "orange",
            (255, 140, 0): "dunkelorange",
            (255, 200, 100): "hellorange",
            (128, 0, 128): "lila",
            (160, 0, 160): "dunkellila",
            (200, 100, 200): "helllila",
            (165, 42, 42): "braun",
            (139, 69, 19): "dunkelbraun",
            (210, 105, 30): "hellbraun",
            (255, 192, 203): "rosa",
            (255, 182, 193): "hellrosa",
            (219, 112, 147): "dunkelrosa",
            (144, 238, 144): "hellgrün",
            (60, 179, 113): "mittelgrün",
            (34, 139, 34): "waldgrün"
        }
    
    def _load_color_thresholds(self) -> Dict:
        """Lädt Farb-Schwellwerte für HSV-Erkennung"""
        return {
            'rot': [(0, 50, 50), (10, 255, 255), (170, 50, 50), (180, 255, 255)],
            'orange': [(10, 50, 50), (20, 255, 255)],
            'gelb': [(20, 50, 50), (35, 255, 255)],
            'grün': [(35, 50, 50), (85, 255, 255)],
            'cyan': [(85, 50, 50), (100, 255, 255)],
            'blau': [(100, 50, 50), (130, 255, 255)],
            'lila': [(130, 50, 50), (170, 255, 255)],
            'rosa': [(150, 30, 100), (170, 255, 255)],
            'braun': [(0, 50, 20), (20, 255, 200)],
            'grau': [(0, 0, 20), (180, 50, 200)]
        }
    
    def _load_face_cascade(self):
        """Lädt Gesichtserkennungs-Klassifikator"""
        try:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
            
            if self.face_cascade.empty():
                logger.warning("Gesichtserkennung-Klassifikator konnte nicht geladen werden")
                self.face_cascade = None
            else:
                logger.info("✅ Gesichtserkennung initialisiert")
        except Exception as e:
            logger.warning(f"Gesichtserkennung konnte nicht initialisiert werden: {e}")
            self.face_cascade = None
    
    def analyze_image(self, image_path: Path) -> ImageAnalysisResult:
        """Analysiert ein Bild mit verschiedenen Methoden"""
        start_time = time.time()
        result = ImageAnalysisResult(success=False)
        
        try:
            # Prüfe Cache
            cache_key = str(image_path)
            if cache_key in self.image_cache:
                cached_result = self.image_cache[cache_key]
                cached_result.processing_time = time.time() - start_time
                return cached_result
            
            # Lade Bild
            img = self._load_image(image_path)
            if img is None:
                result.error = "Bild konnte nicht geladen werden"
                return result
            
            # Grundlegende Informationen
            height, width, channels = img.shape
            result.dimensions = (width, height)
            result.size_kb = image_path.stat().st_size / 1024
            
            # Parallele Analyse
            analysis_futures = {}
            
            # Farbanalyse
            analysis_futures['colors'] = self.executor.submit(self._analyze_colors_parallel, img)
            analysis_futures['dominant'] = self.executor.submit(self._get_dominant_colors_parallel, img)
            
            # Qualitätsmetriken
            analysis_futures['brightness'] = self.executor.submit(self._get_brightness, img)
            analysis_futures['contrast'] = self.executor.submit(self._get_contrast, img)
            analysis_futures['sharpness'] = self.executor.submit(self._calculate_sharpness, img)
            
            # Objekterkennung (falls aktiviert)
            if self.yolo_model:
                analysis_futures['objects'] = self.executor.submit(self._detect_objects_parallel, img)
            
            # Gesichtserkennung (falls aktiviert)
            if self.face_cascade:
                analysis_futures['faces'] = self.executor.submit(self._detect_faces_parallel, img)
            
            # Warte auf Ergebnisse
            for key, future in analysis_futures.items():
                try:
                    value = future.result(timeout=5.0)
                    setattr(result, key, value)
                except Exception as e:
                    logger.warning(f"Analyse {key} fehlgeschlagen: {e}")
                    if key == 'objects':
                        result.objects = []
                    elif key == 'faces':
                        result.faces = 0
                    else:
                        setattr(result, key, 0.0 if key in ['brightness', 'contrast', 'sharpness'] else {})
            
            # Generiere Beschreibung
            result.description = self._generate_description(result)
            
            # Erfolg
            result.success = True
            result.processing_time = time.time() - start_time
            
            # Cache Ergebnis
            self._cache_result(cache_key, result)
            
            logger.debug(f"Bildanalyse abgeschlossen: {image_path.name} ({result.processing_time:.2f}s)")
            
            return result
            
        except Exception as e:
            logger.error(f"Fehler bei Bildanalyse von {image_path}: {e}")
            result.error = str(e)
            result.processing_time = time.time() - start_time
            return result
    
    def _load_image(self, image_path: Path) -> Optional[np.ndarray]:
        """Lädt Bild mit Fehlerbehandlung"""
        try:
            # Versuche mit PIL zuerst (besser für EXIF)
            from PIL import Image as PILImage
            with PILImage.open(image_path) as pil_img:
                # Korrigiere Ausrichtung basierend auf EXIF
                pil_img = ImageOps.exif_transpose(pil_img)
                
                # Konvertiere zu RGB falls nötig
                if pil_img.mode != 'RGB':
                    pil_img = pil_img.convert('RGB')
                
                # Konvertiere zu numpy array
                img_array = np.array(pil_img)
                
                # Konvertiere RGB zu BGR für OpenCV
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                
                return img_array
                
        except UnidentifiedImageError:
            logger.warning(f"Ungültiges Bildformat: {image_path}")
            return None
        except Exception as e:
            logger.warning(f"PIL-Ladefehler, versuche OpenCV: {e}")
            
            # Fallback zu OpenCV
            try:
                img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
                if img is None:
                    logger.warning(f"OpenCV konnte Bild nicht laden: {image_path}")
                    return None
                
                # Stelle sicher, dass Bild korrekt geladen wurde
                if img.size == 0:
                    logger.warning(f"Leeres Bild geladen: {image_path}")
                    return None
                
                return img
                
            except Exception as cv2_error:
                logger.error(f"OpenCV-Ladefehler: {cv2_error}")
                return None
    
    def _analyze_colors_parallel(self, img: np.ndarray) -> Dict[str, float]:
        """Analysiert Farbverteilung (parallel)"""
        try:
            img_hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            total_pixels = img.shape[0] * img.shape[1]
            
            color_percentages = {}
            
            for color_name, ranges in self.color_thresholds.items():
                mask = None
                
                if len(ranges) == 2:
                    lower = np.array(ranges[0])
                    upper = np.array(ranges[1])
                    mask = cv2.inRange(img_hsv, lower, upper)
                elif len(ranges) == 4:
                    # Zwei Bereiche (für Rot)
                    lower1 = np.array(ranges[0])
                    upper1 = np.array(ranges[1])
                    lower2 = np.array(ranges[2])
                    upper2 = np.array(ranges[3])
                    
                    mask1 = cv2.inRange(img_hsv, lower1, upper1)
                    mask2 = cv2.inRange(img_hsv, lower2, upper2)
                    mask = cv2.bitwise_or(mask1, mask2)
                
                if mask is not None:
                    percentage = (np.sum(mask > 0) / total_pixels) * 100
                    if percentage > 2.0:  # Nur signifikante Farben (>2%)
                        color_percentages[color_name] = float(percentage.round(2))
            
            return color_percentages
            
        except Exception as e:
            logger.warning(f"Farbanalyse fehlgeschlagen: {e}")
            return {}
    
    def _get_dominant_colors_parallel(self, img: np.ndarray, n_colors: int = 3) -> List[Dict]:
        """Ermittelt die dominanten Farben im Bild (optimiert)"""
        try:
            # Reduziere Bildgröße für Performance
            max_size = 300
            height, width = img.shape[:2]
            
            if height > max_size or width > max_size:
                scale = max_size / max(height, width)
                new_height = int(height * scale)
                new_width = int(width * scale)
                img_resized = cv2.resize(img, (new_width, new_height))
            else:
                img_resized = img
            
            # In RGB konvertieren
            img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
            
            # Pixel umformen
            pixels = img_rgb.reshape(-1, 3)
            
            # Verwende vereinfachte K-Means mit MiniBatch für Performance
            try:
                from sklearn.cluster import MiniBatchKMeans
                kmeans = MiniBatchKMeans(
                    n_clusters=n_colors,
                    random_state=42,
                    batch_size=100,
                    max_iter=20
                )
                kmeans.fit(pixels)
            except ImportError:
                # Fallback: einfache Farbquantisierung
                return self._simple_dominant_colors(img_rgb, n_colors)
            
            # Farben und Anteile
            colors = kmeans.cluster_centers_.astype(int)
            counts = np.bincount(kmeans.labels_)
            percentages = (counts / len(pixels) * 100).round(2)
            
            dominant = []
            for color, percent in zip(colors, percentages):
                color_name = self._get_color_name(color)
                dominant.append({
                    'rgb': color.tolist(),
                    'hex': f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}",
                    'name': color_name,
                    'percentage': float(percent)
                })
            
            # Sortiere nach Häufigkeit
            dominant.sort(key=lambda x: x['percentage'], reverse=True)
            
            return dominant
            
        except Exception as e:
            logger.warning(f"Dominante Farben fehlgeschlagen: {e}")
            return []
    
    def _simple_dominant_colors(self, img_rgb: np.ndarray, n_colors: int) -> List[Dict]:
        """Einfache Methode für dominante Farben"""
        # Reduziere Farbpalette
        pixels = img_rgb.reshape(-1, 3)
        
        # Quantisiere Farben
        quantized = (pixels // 64 * 64).clip(0, 255)
        
        # Zähle eindeutige Farben
        unique_colors, counts = np.unique(quantized, axis=0, return_counts=True)
        
        # Nehme die häufigsten Farben
        top_indices = np.argsort(counts)[-n_colors:][::-1]
        
        dominant = []
        for idx in top_indices:
            color = unique_colors[idx].tolist()
            percentage = (counts[idx] / len(pixels) * 100).round(2)
            
            color_name = self._get_color_name(color)
            dominant.append({
                'rgb': color,
                'hex': f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}",
                'name': color_name,
                'percentage': float(percentage)
            })
        
        return dominant
    
    def _get_color_name(self, rgb: List[int]) -> str:
        """Gibt den Namen der nächsten bekannten Farbe zurück"""
        rgb_array = np.array(rgb)
        min_dist = float('inf')
        closest_name = "unbekannt"
        
        for known_rgb, name in self.color_names.items():
            dist = np.linalg.norm(rgb_array - np.array(known_rgb))
            if dist < min_dist:
                min_dist = dist
                closest_name = name
        
        return closest_name
    
    def _get_brightness(self, img: np.ndarray) -> float:
        """Berechnet die Helligkeit des Bildes"""
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            brightness = np.mean(gray) / 255.0
            return float(np.clip(brightness, 0.0, 1.0))
        except:
            return 0.5
    
    def _get_contrast(self, img: np.ndarray) -> float:
        """Berechnet den Kontrast des Bildes"""
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            contrast = gray.std() / 255.0
            return float(np.clip(contrast, 0.0, 1.0))
        except:
            return 0.5
    
    def _calculate_sharpness(self, img: np.ndarray) -> float:
        """Berechnet die Schärfe des Bildes (Laplace Variance)"""
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            variance = laplacian.var()
            
            # Normalisiere (empirische Werte)
            sharpness = min(1.0, variance / 1000.0)
            return float(sharpness)
        except:
            return 0.5
    
    def _detect_objects_parallel(self, img: np.ndarray) -> List[str]:
        """Erkennt Objekte im Bild mit YOLO (parallel)"""
        if self.yolo_model is None:
            return []
        
        try:
            # YOLO ausführen
            results = self.yolo_model(img, verbose=False, conf=0.25)
            
            # Extrahiere erkannte Objekte
            objects = []
            for result in results:
                if result.boxes is not None:
                    for box in result.boxes:
                        class_id = int(box.cls[0])
                        confidence = float(box.conf[0])
                        
                        # Nur Objekte mit ausreichender Konfidenz
                        if confidence > 0.5 and class_id in self.yolo_classes:
                            class_name = self.yolo_classes[class_id]
                            objects.append(class_name)
            
            # Einzigartige Objekte, sortiert nach Häufigkeit
            object_counts = Counter(objects)
            sorted_objects = [obj for obj, _ in object_counts.most_common(10)]
            
            return sorted_objects
            
        except Exception as e:
            logger.warning(f"Objekterkennung fehlgeschlagen: {e}")
            return []
    
    def _detect_faces_parallel(self, img: np.ndarray) -> int:
        """Erkennt Gesichter (parallel)"""
        if self.face_cascade is None:
            return 0
        
        try:
            # In Graustufen konvertieren
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Gesichter erkennen
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            return len(faces)
            
        except Exception as e:
            logger.warning(f"Gesichtserkennung fehlgeschlagen: {e}")
            return 0
    
    def _generate_description(self, analysis: ImageAnalysisResult) -> str:
        """Generiert eine Textbeschreibung der Szene"""
        if not analysis.success:
            return "Unbekanntes Bild"
        
        parts = []
        
        # Objekte
        if analysis.objects:
            # Gruppiere ähnliche Objekte
            object_groups = {
                'person': ['person', 'man', 'woman', 'child', 'boy', 'girl'],
                'vehicle': ['car', 'truck', 'bus', 'motorcycle', 'bicycle', 'train'],
                'animal': ['dog', 'cat', 'bird', 'horse', 'sheep', 'cow', 'bear'],
                'food': ['apple', 'banana', 'orange', 'pizza', 'sandwich', 'cake'],
                'furniture': ['chair', 'table', 'couch', 'bed', 'desk', 'cabinet'],
                'electronic': ['laptop', 'cell phone', 'tv', 'keyboard', 'mouse'],
                'outdoor': ['tree', 'flower', 'plant', 'mountain', 'sky', 'cloud']
            }
            
            detected_groups = []
            for group_name, group_items in object_groups.items():
                if any(obj in analysis.objects for obj in group_items):
                    detected_groups.append(group_name)
            
            if detected_groups:
                parts.append(f"mit {', '.join(detected_groups[:2])}")
            elif len(analysis.objects) > 0:
                parts.append(f"mit {analysis.objects[0]}")
        
        # Gesichter
        if analysis.faces == 1:
            parts.append("eine Person")
        elif analysis.faces > 1:
            parts.append(f"{analysis.faces} Personen")
        
        # Farben
        if analysis.dominant_colors:
            main_color = analysis.dominant_colors[0]['name'] if analysis.dominant_colors else None
            if main_color and main_color != "unbekannt":
                parts.append(f"{main_color}es")
        
        # Helligkeit
        if analysis.brightness > 0.7:
            parts.append("helles")
        elif analysis.brightness < 0.3:
            parts.append("dunkles")
        
        # Kontrast
        if analysis.contrast > 0.6:
            parts.append("kontrastreiches")
        
        # Baue Beschreibung zusammen
        if len(parts) == 0:
            if analysis.colors:
                color_names = list(analysis.colors.keys())
                if color_names:
                    return f"{color_names[0]}es Bild"
            
            return "Fotografie"
        
        description = ' '.join(parts)
        return description.capitalize()
    
    def _cache_result(self, cache_key: str, result: ImageAnalysisResult):
        """Cached Analyse-Ergebnis"""
        if len(self.image_cache) >= self.cache_size:
            # Entferne ältesten Eintrag
            oldest_key = next(iter(self.image_cache))
            del self.image_cache[oldest_key]
        
        self.image_cache[cache_key] = result
    
    def analyze_images_batch(self, image_paths: List[Path]) -> Dict[Path, ImageAnalysisResult]:
        """Analysiert mehrere Bilder parallel"""
        results = {}
        futures = {}
        
        logger.info(f"Analysiere {len(image_paths)} Bilder im Batch...")
        
        # Starte alle Analysen parallel
        for image_path in image_paths:
            future = self.executor.submit(self.analyze_image, image_path)
            futures[future] = image_path
        
        # Sammle Ergebnisse
        for future in as_completed(futures):
            image_path = futures[future]
            try:
                result = future.result(timeout=10.0)
                results[image_path] = result
            except Exception as e:
                logger.warning(f"Batch-Analyse für {image_path} fehlgeschlagen: {e}")
                results[image_path] = ImageAnalysisResult(
                    success=False,
                    error=str(e),
                    description="Analyse fehlgeschlagen"
                )
        
        logger.info(f"Batch-Analyse abgeschlossen: {len(results)} Ergebnisse")
        return results
    
    def describe_image_for_filename(self, analysis: ImageAnalysisResult) -> str:
        """Generiert Bildbeschreibung für Dateinamen"""
        if not analysis.success:
            return "bild"
        
        description_parts = []
        
        # Hauptobjekte
        if analysis.objects:
            # Nehme die 2-3 wichtigsten Objekte
            main_objects = []
            for obj in analysis.objects[:3]:
                # Übersetze englische Objektnamen
                translations = {
                    'person': 'person',
                    'car': 'auto',
                    'dog': 'hund',
                    'cat': 'katze',
                    'bird': 'vogel',
                    'tree': 'baum',
                    'flower': 'blume',
                    'building': 'gebaeude',
                    'house': 'haus',
                    'chair': 'stuhl',
                    'table': 'tisch',
                    'computer': 'computer',
                    'phone': 'telefon'
                }
                
                german_obj = translations.get(obj, obj)
                if german_obj not in main_objects:
                    main_objects.append(german_obj)
            
            if main_objects:
                description_parts.extend(main_objects)
        
        # Farbe
        if analysis.dominant_colors:
            dominant_color = analysis.dominant_colors[0]['name']
            if dominant_color and dominant_color != "unbekannt":
                # Vereinfache Farbnamen
                simple_colors = {
                    'rot': 'rot',
                    'gruen': 'gruen',
                    'blau': 'blau',
                    'gelb': 'gelb',
                    'orange': 'orange',
                    'lila': 'lila',
                    'braun': 'braun',
                    'grau': 'grau',
                    'schwarz': 'schwarz',
                    'weiß': 'weiss'
                }
                
                for complex_color, simple_color in simple_colors.items():
                    if complex_color in dominant_color:
                        description_parts.append(simple_color)
                        break
        
        # Falls keine Beschreibung, generische
        if not description_parts:
            if analysis.faces > 0:
                description_parts.append('portrait')
            else:
                description_parts.append('bild')
        
        # Begrenze auf 4 Teile
        description_parts = description_parts[:4]
        
        return '_'.join(description_parts)
    
    def close(self):
        """Ressourcen freigeben"""
        self.executor.shutdown(wait=True)
        self.image_cache.clear()
        
        # YOLO Modell entladen
        if self.yolo_model is not None:
            try:
                del self.yolo_model
                import gc
                gc.collect()
                if torch is not None and torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except:
                pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Hilfsfunktion für sklearn Import
def check_sklearn_available():
    try:
        from sklearn.cluster import MiniBatchKMeans
        return True
    except ImportError:
        return False