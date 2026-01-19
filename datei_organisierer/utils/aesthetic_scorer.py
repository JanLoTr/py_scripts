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
[file content end]

[file name]: duplicate_detector_fixed.py
[file content begin]
"""
Erweiterte Duplikaterkennung - Verbesserte Version
"""

import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import numpy as np

try:
    import xxhash
    XXHASH_AVAILABLE = True
except ImportError:
    XXHASH_AVAILABLE = False

try:
    from PIL import Image, UnidentifiedImageError
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Logging konfigurieren
logger = logging.getLogger(__name__)


@dataclass
class FileMetadata:
    """Dataclass für Datei-Metadaten"""
    path: Path
    filename: str
    extension: str
    size_bytes: int
    modified: str
    hash: Optional[str] = None
    image_hash: Optional[str] = None
    size_bucket: str = field(init=False)
    
    def __post_init__(self):
        self.size_bucket = self._get_size_bucket()
    
    def _get_size_bucket(self) -> str:
        """Gruppiert Dateigrößen in Buckets"""
        if self.size_bytes < 1024:  # < 1KB
            return "tiny"
        elif self.size_bytes < 1024 * 1024:  # < 1MB
            return "small"
        elif self.size_bytes < 10 * 1024 * 1024:  # < 10MB
            return "medium"
        elif self.size_bytes < 100 * 1024 * 1024:  # < 100MB
            return "large"
        else:
            return "huge"


@dataclass
class DuplicateGroup:
    """Dataclass für Duplikat-Gruppen"""
    files: List[FileMetadata]
    similarity_type: str  # 'exact', 'similar', 'image'
    confidence: float
    suggested_action: str = ""


class DuplicateDetector:
    def __init__(self, config: Dict):
        self.config = config
        self.similarity_threshold = config.get('similarity_threshold', 0.95)
        self.hash_block_size = config.get('hash_block_size', 8192)
        self.image_hash_size = config.get('image_hash_size', 8)
        self.max_image_size = config.get('max_image_size', 3840 * 2160 * 3)  # 4K RGB
        
        # Performance-Optimierung
        self.executor = ThreadPoolExecutor(max_workers=8)
        self.use_cache = config.get('use_hash_cache', True)
        self.hash_cache: Dict[Path, str] = {}
        
        logger.info(f"DuplicateDetector initialisiert (XXHash: {XXHASH_AVAILABLE}, PIL: {PIL_AVAILABLE})")
    
    def find_duplicates(self, files: List[Dict]) -> List[DuplicateGroup]:
        """Findet Duplikate mit verschiedenen Methoden (parallelisiert)"""
        logger.info(f"🔍 Suche nach Duplikaten in {len(files)} Dateien...")
        
        # Konvertiere zu FileMetadata Objekten
        file_metas = [self._dict_to_filemeta(f) for f in files]
        
        # Parallele Verarbeitung
        futures = []
        
        # 1. Exakte Duplikate
        future_exact = self.executor.submit(self.find_exact_duplicates, file_metas)
        futures.append(('exact', future_exact))
        
        # 2. Ähnliche Dateien
        future_similar = self.executor.submit(self.find_similar_files, file_metas)
        futures.append(('similar', future_similar))
        
        # 3. Bild-Duplikate (nur wenn Bilder vorhanden und PIL verfügbar)
        image_files = [f for f in file_metas if f.extension.lower() in ['.jpg', '.jpeg', '.png', '.webp', '.bmp']]
        if image_files and PIL_AVAILABLE:
            future_image = self.executor.submit(self.find_image_duplicates, image_files)
            futures.append(('image', future_image))
        
        # Sammle Ergebnisse
        all_groups = []
        for method_name, future in futures:
            try:
                groups = future.result(timeout=30.0)
                for group in groups:
                    group.similarity_type = method_name
                    all_groups.append(group)
                logger.info(f"  ✅ {method_name}: {len(groups)} Gruppen gefunden")
            except Exception as e:
                logger.warning(f"  ⚠️ {method_name} fehlgeschlagen: {e}")
        
        # Entferne doppelte Einträge
        deduplicated = self.deduplicate_groups(all_groups)
        
        # Sortiere nach Priorität
        deduplicated.sort(key=lambda g: len(g.files), reverse=True)
        
        logger.info(f"✅ Insgesamt {len(deduplicated)} Duplikat-Gruppen gefunden")
        return deduplicated
    
    def _dict_to_filemeta(self, file_dict: Dict) -> FileMetadata:
        """Konvertiert Dictionary zu FileMetadata"""
        return FileMetadata(
            path=Path(file_dict['path']),
            filename=file_dict['filename'],
            extension=file_dict['extension'].lower(),
            size_bytes=file_dict['size_bytes'],
            modified=file_dict.get('modified', '')
        )
    
    def find_exact_duplicates(self, files: List[FileMetadata]) -> List[DuplicateGroup]:
        """Findet exakte Duplikate (gleicher Hash) - parallelisiert"""
        logger.info("  🔍 Berechne Datei-Hashes...")
        
        # Parallele Hash-Berechnung
        hash_results = {}
        futures = {}
        
        for file_meta in files:
            future = self.executor.submit(self._calculate_file_hash, file_meta.path)
            futures[future] = file_meta
        
        for future in as_completed(futures):
            file_meta = futures[future]
            try:
                file_hash = future.result(timeout=10.0)
                file_meta.hash = file_hash
                
                if file_hash not in hash_results:
                    hash_results[file_hash] = []
                hash_results[file_hash].append(file_meta)
            except Exception as e:
                logger.warning(f"Hash-Berechnung für {file_meta.filename} fehlgeschlagen: {e}")
        
        # Erstelle DuplicateGroup Objekte
        groups = []
        for file_hash, file_list in hash_results.items():
            if len(file_list) > 1:
                group = DuplicateGroup(
                    files=file_list,
                    similarity_type='exact',
                    confidence=1.0,
                    suggested_action="Behalte neueste/kleinste Datei"
                )
                groups.append(group)
        
        return groups
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Berechnet Datei-Hash (mit Cache)"""
        if self.use_cache and file_path in self.hash_cache:
            return self.hash_cache[file_path]
        
        try:
            if XXHASH_AVAILABLE:
                hasher = xxhash.xxh64()
            else:
                hasher = hashlib.md5()
            
            with open(file_path, 'rb') as f:
                while chunk := f.read(self.hash_block_size):
                    hasher.update(chunk)
            
            file_hash = hasher.hexdigest()
            
            if self.use_cache:
                self.hash_cache[file_path] = file_hash
            
            return file_hash
            
        except Exception as e:
            logger.error(f"Fehler bei Hash-Berechnung von {file_path}: {e}")
            raise
    
    def find_similar_files(self, files: List[FileMetadata], 
                          exclude_files: Optional[Set[Path]] = None) -> List[DuplicateGroup]:
        """Findet ähnliche Dateien (gleicher Typ, ähnliche Größe/Name)"""
        if exclude_files is None:
            exclude_files = set()
        
        # Gruppiere nach Typ und Größen-Bucket
        type_size_groups = defaultdict(list)
        
        for file_meta in files:
            if file_meta.path in exclude_files:
                continue
            
            key = f"{file_meta.extension}_{file_meta.size_bucket}"
            type_size_groups[key].append(file_meta)
        
        # Prüfe ähnliche Namen innerhalb der Gruppen
        groups = []
        for files_in_group in type_size_groups.values():
            if len(files_in_group) < 2:
                continue
            
            # Gruppiere nach ähnlichen Namen
            name_groups = self._group_by_similar_names(files_in_group)
            
            for name_group in name_groups:
                if len(name_group) > 1:
                    # Berechne Ähnlichkeits-Score
                    similarity = self._calculate_name_similarity(name_group)
                    
                    group = DuplicateGroup(
                        files=name_group,
                        similarity_type='similar',
                        confidence=similarity,
                        suggested_action="Überprüfe auf verschiedene Versionen"
                    )
                    groups.append(group)
        
        return groups
    
    def _group_by_similar_names(self, files: List[FileMetadata]) -> List[List[FileMetadata]]:
        """Gruppiert Dateien mit ähnlichen Namen (optimiert)"""
        from difflib import SequenceMatcher
        
        groups = []
        processed = set()
        
        # Sortiere nach Dateinamen für bessere Gruppierung
        files_sorted = sorted(files, key=lambda x: x.filename)
        
        for i, file1 in enumerate(files_sorted):
            if file1.path in processed:
                continue
            
            current_group = [file1]
            processed.add(file1.path)
            
            # Suche ähnliche Namen in der Nähe (optimiert für O(n log n))
            for j, file2 in enumerate(files_sorted[i+1:], i+1):
                if file2.path in processed:
                    continue
                
                # Schnellprüfung: Gleiche Länge ±30%
                len1, len2 = len(file1.filename), len(file2.filename)
                if abs(len1 - len2) / max(len1, len2) > 0.3:
                    continue
                
                # Berechne Namensähnlichkeit
                similarity = SequenceMatcher(
                    None, 
                    file1.filename.lower(), 
                    file2.filename.lower()
                ).ratio()
                
                if similarity > 0.7:  # 70% ähnlich
                    current_group.append(file2)
                    processed.add(file2.path)
            
            if len(current_group) > 1:
                groups.append(current_group)
        
        return groups
    
    def _calculate_name_similarity(self, files: List[FileMetadata]) -> float:
        """Berechnet durchschnittliche Namensähnlichkeit in einer Gruppe"""
        from difflib import SequenceMatcher
        
        if len(files) < 2:
            return 0.0
        
        similarities = []
        for i in range(len(files)):
            for j in range(i+1, len(files)):
                similarity = SequenceMatcher(
                    None,
                    files[i].filename.lower(),
                    files[j].filename.lower()
                ).ratio()
                similarities.append(similarity)
        
        return float(np.mean(similarities)) if similarities else 0.0
    
    def find_image_duplicates(self, files: List[FileMetadata]) -> List[DuplicateGroup]:
        """Findet visuell ähnliche Bilder (optimiert)"""
        logger.info(f"  🔍 Prüfe {len(files)} Bilder auf visuelle Ähnlichkeit...")
        
        if not PIL_AVAILABLE:
            logger.warning("PIL nicht verfügbar, überspringe Bild-Duplikaterkennung")
            return []
        
        # Berechne Image Hashes parallel
        hash_map = {}
        futures = {}
        
        for file_meta in files:
            future = self.executor.submit(self._calculate_perceptual_hash, file_meta.path)
            futures[future] = file_meta
        
        for future in as_completed(futures):
            file_meta = futures[future]
            try:
                img_hash = future.result(timeout=5.0)
                if img_hash:
                    file_meta.image_hash = img_hash
                    
                    if img_hash not in hash_map:
                        hash_map[img_hash] = []
                    hash_map[img_hash].append(file_meta)
            except Exception as e:
                logger.warning(f"Image-Hash für {file_meta.filename} fehlgeschlagen: {e}")
        
        # Finde ähnliche Hashes mit optimiertem Algorithmus
        groups = []
        hash_list = list(hash_map.items())
        
        # Verwende optimierte Suche mit Hash-Buckets
        hash_buckets = defaultdict(list)
        for hash_str, file_list in hash_list:
            # Erstelle Buckets basierend auf Hash-Präfixen für schnellere Suche
            bucket_key = hash_str[:8]  # Erste 8 Zeichen
            hash_buckets[bucket_key].append((hash_str, file_list))
        
        processed_hashes = set()
        
        for bucket_key, bucket_items in hash_buckets.items():
            for i, (hash1, files1) in enumerate(bucket_items):
                if hash1 in processed_hashes:
                    continue
                
                current_group = files1.copy()
                processed_hashes.add(hash1)
                
                # Vergleiche nur mit Hashes im selben Bucket
                for j, (hash2, files2) in enumerate(bucket_items[i+1:], i+1):
                    if hash2 in processed_hashes:
                        continue
                    
                    # Berechne Hamming-Distanz
                    if self._hamming_distance(hash1, hash2) < 8:  # Ähnlich
                        current_group.extend(files2)
                        processed_hashes.add(hash2)
                
                if len(current_group) > len(files1):
                    # Berechne durchschnittliche Ähnlichkeit
                    avg_similarity = 1.0 - (self._avg_hamming_distance(current_group) / 64.0)
                    
                    group = DuplicateGroup(
                        files=current_group,
                        similarity_type='image',
                        confidence=avg_similarity,
                        suggested_action="Behalte beste Qualität (höchste Auflösung)"
                    )
                    groups.append(group)
        
        return groups
    
    def _calculate_perceptual_hash(self, image_path: Path) -> Optional[str]:
        """Berechnet Perceptual Hash für Bild"""
        if not PIL_AVAILABLE:
            return None
        
        try:
            with Image.open(image_path) as img:
                # Größe begrenzen für Performance
                max_size = (512, 512)
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Reduziere Größe für Hash
                img = img.resize((self.image_hash_size, self.image_hash_size), 
                               Image.Resampling.LANCZOS)
                
                # Konvertiere zu Graustufen
                img = img.convert('L')
                
                # Berechne Durchschnitt
                pixels = list(img.getdata())
                avg = sum(pixels) / len(pixels)
                
                # Erstelle Hash
                hash_str = ''.join('1' if pixel > avg else '0' for pixel in pixels)
                
                return hash_str
                
        except UnidentifiedImageError:
            logger.warning(f"Ungültiges Bildformat: {image_path}")
            return None
        except Exception as e:
            logger.warning(f"Fehler bei Image-Hash von {image_path}: {e}")
            return None
    
    def _hamming_distance(self, hash1: str, hash2: str) -> int:
        """Berechnet Hamming-Distanz zwischen zwei Hashes"""
        if len(hash1) != len(hash2):
            return len(hash1)  # Maximale Distanz
        
        return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
    
    def _avg_hamming_distance(self, files: List[FileMetadata]) -> float:
        """Berechnet durchschnittliche Hamming-Distanz in einer Gruppe"""
        if len(files) < 2:
            return 0.0
        
        distances = []
        hashes = [f.image_hash for f in files if f.image_hash]
        
        for i in range(len(hashes)):
            for j in range(i+1, len(hashes)):
                dist = self._hamming_distance(hashes[i], hashes[j])
                distances.append(dist)
        
        return float(np.mean(distances)) if distances else 0.0
    
    def deduplicate_groups(self, groups: List[DuplicateGroup]) -> List[DuplicateGroup]:
        """Entfernt doppelte Dateien aus Gruppen"""
        file_to_groups = defaultdict(list)
        
        # Map: Datei → Gruppen Index
        for i, group in enumerate(groups):
            for file_meta in group.files:
                file_to_groups[file_meta.path].append(i)
        
        # Entferne Duplikate
        processed_files = set()
        result = []
        
        for i, group in enumerate(groups):
            clean_group = []
            
            for file_meta in group.files:
                if file_meta.path not in processed_files:
                    clean_group.append(file_meta)
                    processed_files.add(file_meta.path)
            
            if len(clean_group) > 1:
                # Aktualisiere Konfidenz für die bereinigte Gruppe
                if group.similarity_type == 'image' and clean_group[0].image_hash:
                    avg_similarity = 1.0 - (self._avg_hamming_distance(clean_group) / 64.0)
                    group.confidence = avg_similarity
                
                group.files = clean_group
                result.append(group)
        
        return result
    
    def suggest_duplicate_handling(self, duplicate_groups: List[DuplicateGroup]) -> Dict:
        """Schlägt Behandlung von Duplikaten vor"""
        suggestions = {}
        
        for i, group in enumerate(duplicate_groups):
            if len(group.files) < 2:
                continue
            
            # Analysiere Gruppe
            files_sorted_by_date = sorted(group.files, 
                                        key=lambda x: x.modified, 
                                        reverse=True)
            files_sorted_by_size = sorted(group.files, 
                                        key=lambda x: x.size_bytes, 
                                        reverse=True)
            
            newest = files_sorted_by_date[0]
            largest = files_sorted_by_size[0]
            smallest = files_sorted_by_size[-1]
            
            # Bestimme beste Qualität für Bilder
            if group.similarity_type == 'image':
                # Für Bilder: größte Datei = beste Qualität (normalerweise)
                best_quality = largest
            else:
                # Für andere Dateien: neueste = beste Version
                best_quality = newest
            
            suggestions[f"gruppe_{i}"] = {
                "files": [f.filename for f in group.files],
                "count": len(group.files),
                "similarity_type": group.similarity_type,
                "confidence": round(group.confidence, 2),
                "suggestions": [
                    f"Behalte neueste: {newest.filename}",
                    f"Behalte größte (beste Qualität): {largest.filename}",
                    f"Behalte kleinste: {smallest.filename}",
                    "Behalte alle",
                    "Manuell auswählen"
                ],
                "recommended": f"Behalte {best_quality.filename}",
                "stats": {
                    "size_range": f"{smallest.size_bytes/1024:.1f}KB - {largest.size_bytes/1024:.1f}KB",
                    "age_range": f"{files_sorted_by_date[-1].modified[:10]} - {newest.modified[:10]}"
                }
            }
        
        return suggestions
    
    def close(self):
        """Ressourcen freigeben"""
        self.executor.shutdown(wait=True)
        self.hash_cache.clear()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
[file content end]

[file name]: filename_generator_fixed.py
[file content begin]
"""
Intelligente Generierung von Dateinamen - Verbesserte Version
"""

import re
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, TypedDict
from pathlib import Path
from dataclasses import dataclass
from collections import Counter
import hashlib

# Logging konfigurieren
logger = logging.getLogger(__name__)


@dataclass
class FileNamingConfig:
    """Konfiguration für Dateinamen-Generierung"""
    naming_scheme: str = 'descriptive'
    max_filename_length: int = 80
    timestamp_format: str = "%Y%m%d_%H%M%S"
    use_utc_time: bool = True
    ensure_uniqueness: bool = True
    allowed_chars: str = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-."
    stopwords: Set[str] = None
    
    def __post_init__(self):
        if self.stopwords is None:
            self.stopwords = {
                'der', 'die', 'das', 'und', 'oder', 'in', 'zu', 'von', 'mit', 'für', 'auf',
                'ein', 'eine', 'einer', 'einem', 'einen', 'the', 'and', 'or', 'in', 'to', 'from',
                'with', 'for', 'on', 'a', 'an', 'of', 'by'
            }


class GeneratedName(TypedDict):
    """Struktur für generierte Dateinamen"""
    original: str
    new: str
    category: Optional[str]
    method: str
    timestamp: str


class FilenameGenerator:
    def __init__(self, config: Dict):
        self.config = FileNamingConfig(**config.get('filename_generation', {}))
        self._counter = 0  # Für eindeutige Namen
        self._generated_names: Set[str] = set()  # Für Eindeutigkeit
        
        logger.info(f"FilenameGenerator initialisiert mit Schema: {self.config.naming_scheme}")
    
    def generate_filename(self, file_info: Dict, category: Optional[str] = None) -> str:
        """Generiert neuen Dateinamen basierend auf Schema"""
        original_name = Path(file_info['filename']).stem
        extension = self._normalize_extension(file_info['extension'])
        
        try:
            if self.config.naming_scheme == 'descriptive':
                new_name = self.generate_descriptive_name(file_info, extension)
            elif self.config.naming_scheme == 'timestamp':
                new_name = self.generate_timestamp_name(file_info, extension)
            elif self.config.naming_scheme == 'category_based':
                new_name = self.generate_category_based_name(file_info, category, extension)
            else:
                new_name = self.generate_hybrid_name(file_info, category, extension)
            
            # Stelle Eindeutigkeit sicher
            if self.config.ensure_uniqueness:
                new_name = self._ensure_unique_name(new_name)
            
            # Validiere und bereinige den Namen
            new_name = self._validate_and_clean_filename(new_name)
            
            # Speichere generierten Namen
            self._generated_names.add(new_name.lower())
            
            return new_name
            
        except Exception as e:
            logger.error(f"Fehler bei Generierung von {file_info['filename']}: {e}")
            return self._create_fallback_name(file_info, extension)
    
    def generate_image_name(self, description: str, extension: str) -> str:
        """Generiert Dateinamen für Bilder basierend auf Beschreibung"""
        # Bereinige Beschreibung
        clean_desc = self.clean_for_filename(description)
        
        # Kürze wenn nötig
        max_desc_length = self.config.max_filename_length - 30  # Platz für Timestamp und Extension
        if len(clean_desc) > max_desc_length:
            clean_desc = clean_desc[:max_desc_length]
        
        # Timestamp hinzufügen (thread-safe mit Counter)
        timestamp = self._get_thread_safe_timestamp()
        
        # Baue Dateinamen
        extension = self._normalize_extension(extension)
        filename = f"{clean_desc}_{timestamp}{extension}"
        
        # Stelle Eindeutigkeit sicher
        if self.config.ensure_uniqueness:
            filename = self._ensure_unique_name(filename)
        
        return filename
    
    def generate_descriptive_name(self, file_info: Dict, extension: str) -> str:
        """Generiert beschreibenden Namen"""
        description = self.extract_description(file_info)
        clean_desc = self.clean_for_filename(description)
        
        # Kürze falls nötig
        max_desc_length = self.config.max_filename_length - 20
        if len(clean_desc) > max_desc_length:
            clean_desc = clean_desc[:max_desc_length]
        
        # Füge Datum hinzu
        date_str = self._get_current_date()
        
        # Baue finalen Namen
        if len(clean_desc) > 0:
            filename = f"{clean_desc}_{date_str}{extension}"
        else:
            # Fallback: Originalname mit Datum und Hash
            original_stem = Path(file_info['filename']).stem[:30]
            file_hash = hashlib.md5(file_info['filename'].encode()).hexdigest()[:6]
            filename = f"{original_stem}_{date_str}_{file_hash}{extension}"
        
        return filename
    
    def extract_description(self, file_info: Dict) -> str:
        """Extrahiert Beschreibung aus Dateimetadaten"""
        ext = file_info.get('extension', '').lower()
        
        # Für Bilder
        if ext in ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif', '.tiff']:
            return self.extract_image_description(file_info)
        
        # Für Dokumente
        elif ext in ['.pdf', '.docx', '.doc', '.txt', '.rtf', '.odt']:
            return self.extract_document_description(file_info)
        
        # Für Tabellen
        elif ext in ['.xlsx', '.xls', '.csv', '.ods']:
            return self.extract_spreadsheet_description(file_info)
        
        # Für Präsentationen
        elif ext in ['.pptx', '.ppt', '.odp']:
            return self.extract_presentation_description(file_info)
        
        # Für Code
        elif ext in ['.py', '.js', '.java', '.cpp', '.c', '.html', '.css', '.php', '.rb']:
            return self.extract_code_description(file_info)
        
        # Für Archive
        elif ext in ['.zip', '.rar', '.7z', '.tar', '.gz']:
            return self.extract_archive_description(file_info)
        
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
                if color:
                    return f"{color}es_bild"
        
        # Fallback aus Dateinamen
        name = file_info['filename'].lower()
        
        # Häufige Muster erkennen
        patterns = {
            'screenshot': 'screenshot',
            'photo': 'foto',
            'img': 'bild',
            'pic': 'bild',
            'camera': 'foto',
            'scan': 'scan'
        }
        
        for pattern, description in patterns.items():
            if pattern in name:
                return description
        
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
            'invoice': 'rechnung',
            'vertrag': 'vertrag',
            'contract': 'vertrag',
            'lebenslauf': 'lebenslauf',
            'cv': 'lebenslauf',
            'bewerbung': 'bewerbung',
            'application': 'bewerbung',
            'notizen': 'notizen',
            'notes': 'notizen',
            'protokoll': 'protokoll',
            'minutes': 'protokoll',
            'bericht': 'bericht',
            'report': 'bericht'
        }
        
        for pattern, description in patterns.items():
            if pattern in name:
                return description
        
        return "dokument"
    
    def extract_spreadsheet_description(self, file_info: Dict) -> str:
        """Extrahiert Tabellen-Beschreibung"""
        name = file_info['filename'].lower()
        
        patterns = {
            'budget': 'budget',
            'finanz': 'finanzen',
            'finance': 'finanzen',
            'kosten': 'kosten',
            'cost': 'kosten',
            'umsatz': 'umsatz',
            'revenue': 'umsatz',
            'daten': 'daten',
            'data': 'daten',
            'liste': 'liste',
            'list': 'liste',
            'plan': 'plan',
            'schedule': 'plan'
        }
        
        for pattern, description in patterns.items():
            if pattern in name:
                return f"tabelle_{description}"
        
        return "tabelle"
    
    def extract_presentation_description(self, file_info: Dict) -> str:
        """Extrahiert Präsentations-Beschreibung"""
        name = file_info['filename'].lower()
        
        patterns = {
            'präsentation': 'präsentation',
            'presentation': 'präsentation',
            'vortrag': 'vortrag',
            'talk': 'vortrag',
            'pitch': 'pitch',
            'projekt': 'projekt',
            'project': 'projekt',
            'konzept': 'konzept',
            'concept': 'konzept'
        }
        
        for pattern, description in patterns.items():
            if pattern in name:
                return f"präsentation_{description}"
        
        return "präsentation"
    
    def extract_code_description(self, file_info: Dict) -> str:
        """Extrahiert Code-Beschreibung"""
        content = file_info.get('content_preview', '').lower()
        filename = file_info['filename'].lower()
        
        # Erkenne Code-Typ
        code_patterns = {
            'python': ('import', 'def ', 'class ', 'from ', 'print('),
            'javascript': ('function', 'const ', 'let ', 'var ', 'export '),
            'java': ('public class', 'import ', 'void ', 'System.out'),
            'cpp': ('#include', 'int main', 'cout <<', 'using namespace'),
            'html': ('<!DOCTYPE', '<html', '<body', '<div '),
            'css': ('body {', '.class', '#id', '@media'),
            'php': ('<?php', '$_', 'echo ', 'function ')
        }
        
        for lang, patterns in code_patterns.items():
            if any(pattern in content for pattern in patterns):
                return f"{lang}_datei"
        
        # Aus Dateinamen
        file_patterns = {
            'test': 'test',
            'test_': 'test',
            'spec': 'test',
            'unit': 'test',
            'util': 'hilfe',
            'helper': 'hilfe',
            'utility': 'hilfe',
            'config': 'konfig',
            'settings': 'konfig',
            'setup': 'konfig',
            'main': 'haupt',
            'app': 'anwendung',
            'application': 'anwendung'
        }
        
        for pattern, description in file_patterns.items():
            if pattern in filename:
                return f"code_{description}"
        
        return "code_datei"
    
    def extract_archive_description(self, file_info: Dict) -> str:
        """Extrahiert Archiv-Beschreibung"""
        name = file_info['filename'].lower()
        
        patterns = {
            'backup': 'backup',
            'sicherung': 'sicherung',
            'export': 'export',
            'daten': 'daten',
            'data': 'daten',
            'files': 'dateien',
            'projekt': 'projekt',
            'project': 'projekt'
        }
        
        for pattern, description in patterns.items():
            if pattern in name:
                return f"archiv_{description}"
        
        return "archiv"
    
    def extract_generic_description(self, file_info: Dict) -> str:
        """Generische Beschreibung"""
        stem = Path(file_info['filename']).stem.lower()
        
        # Entferne numerische Präfixe (z.B. "IMG_1234" -> "IMG")
        stem = re.sub(r'^[0-9_\-]+', '', stem)
        stem = re.sub(r'[0-9_\-]+$', '', stem)
        
        if len(stem) > 3:
            return stem
        else:
            return "datei"
    
    def extract_keywords(self, text: str, max_words: int = 5) -> List[str]:
        """Extrahiert Schlüsselwörter aus Text"""
        if not text:
            return []
        
        # Bereinige Text
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        words = text.split()
        
        # Entferne Stoppwörter
        filtered = [w for w in words if w not in self.config.stopwords and len(w) > 2]
        
        if not filtered:
            return []
        
        # Nehme die häufigsten Wörter
        common = Counter(filtered).most_common(max_words)
        
        # Entferne zu kurze Wörter
        keywords = [word for word, _ in common if len(word) > 2]
        
        return keywords[:max_words]
    
    def clean_for_filename(self, text: str) -> str:
        """Bereinigt Text für Dateinamen"""
        if not text:
            return ""
        
        # Entferne Sonderzeichen (ein Schritt)
        text = re.sub(r'[^\w\s-]', '', text)
        
        # Ersetze alle nicht-Buchstaben/Ziffern mit Unterstrichen
        text = re.sub(r'[^\w]+', '_', text)
        
        # Entferne doppelte Unterstriche
        text = re.sub(r'_+', '_', text)
        
        # Entferne führende/abschließende Unterstriche
        text = text.strip('_')
        
        # Kürze wenn nötig
        if len(text) > 40:
            # Versuche bei Wortgrenze zu kürzen
            if '_' in text[:45]:
                text = text[:45].rsplit('_', 1)[0]
            else:
                text = text[:40]
        
        # Stelle sicher, dass nicht leer
        if not text:
            text = "datei"
        
        return text.lower()
    
    def generate_timestamp_name(self, file_info: Dict, extension: str) -> str:
        """Generiert Namen mit Zeitstempel (thread-safe)"""
        try:
            modified = file_info.get('modified', '')
            
            if modified:
                # Versuche Datum aus Metadaten zu extrahieren
                dt = self._parse_datetime(modified)
            else:
                # Verwende aktuelle Zeit
                dt = self._get_current_datetime()
            
            timestamp = dt.strftime(self.config.timestamp_format)
            
            # Füge Teile des Originalnamens hinzu
            original_stem = Path(file_info['filename']).stem
            # Entferne bereits vorhandene Timestamps
            original_stem = re.sub(r'\d{8}[_-]\d{6}', '', original_stem)
            original_stem = re.sub(r'\d{4}[-_]\d{2}[-_]\d{2}', '', original_stem)
            
            if original_stem:
                # Kürze Originalnamen
                original_stem = original_stem[:20].strip('_-')
                filename = f"{timestamp}_{original_stem}{extension}"
            else:
                filename = f"{timestamp}{extension}"
            
            return filename
            
        except Exception as e:
            logger.warning(f"Fehler bei Timestamp-Generierung: {e}")
            return self.generate_descriptive_name(file_info, extension)
    
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
        
        # Extrahiere Beschreibung
        description = self.extract_description(file_info)
        clean_desc = self.clean_for_filename(description)[:20]
        
        # Füge Datum hinzu
        date_str = self._get_current_date()
        
        return f"{clean_category}_{clean_desc}_{date_str}{extension}"
    
    def generate_hybrid_name(self, file_info: Dict, category: Optional[str], extension: str) -> str:
        """Kombiniert verschiedene Methoden"""
        descriptive = self.extract_description(file_info)
        clean_desc = self.clean_for_filename(descriptive)[:20]
        
        date_str = self._get_current_date()
        
        if category:
            clean_cat = self.clean_for_filename(category)[:15]
            return f"{clean_cat}_{clean_desc}_{date_str}{extension}"
        else:
            return f"{clean_desc}_{date_str}{extension}"
    
    def _normalize_extension(self, extension: str) -> str:
        """Normalisiert Dateiendung"""
        if not extension:
            return ""
        
        # Stelle sicher, dass Extension mit Punkt beginnt
        if not extension.startswith('.'):
            extension = '.' + extension
        
        # Konvertiere zu Kleinbuchstaben
        return extension.lower()
    
    def _get_current_datetime(self) -> datetime:
        """Gibt aktuelles Datum/Zeit zurück (thread-safe)"""
        if self.config.use_utc_time:
            return datetime.now(timezone.utc)
        else:
            return datetime.now()
    
    def _get_current_date(self) -> str:
        """Gibt aktuelles Datum zurück"""
        return self._get_current_datetime().strftime("%Y%m%d")
    
    def _get_thread_safe_timestamp(self) -> str:
        """Thread-sicherer Timestamp mit Counter"""
        base_timestamp = self._get_current_datetime().strftime(self.config.timestamp_format)
        counter = self._get_next_counter()
        
        if counter > 0:
            return f"{base_timestamp}_{counter:03d}"
        else:
            return base_timestamp
    
    def _get_next_counter(self) -> int:
        """Thread-sichere Counter-Erhöhung"""
        import threading
        with threading.Lock():
            self._counter += 1
            return self._counter
    
    def _parse_datetime(self, date_str: str) -> datetime:
        """Versucht Datum aus String zu parsen"""
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y%m%d_%H%M%S",
            "%Y%m%d"
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str[:19], fmt)
                if 'Z' in date_str:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        
        # Fallback zu aktueller Zeit
        return self._get_current_datetime()
    
    def _ensure_unique_name(self, filename: str) -> str:
        """Stellt sicher, dass Dateiname eindeutig ist"""
        if filename.lower() not in self._generated_names:
            return filename
        
        # Füge Suffix hinzu für Eindeutigkeit
        base, ext = Path(filename).stem, Path(filename).suffix
        
        counter = 1
        while True:
            new_name = f"{base}_{counter}{ext}"
            if new_name.lower() not in self._generated_names:
                return new_name
            counter += 1
            
            if counter > 1000:  # Sicherheitslimit
                raise ValueError(f"Konnte keinen eindeutigen Namen für {filename} finden")
    
    def _validate_and_clean_filename(self, filename: str) -> str:
        """Validiert und bereinigt Dateinamen"""
        # Stelle sicher, dass nicht leer
        if not filename or filename.isspace():
            filename = f"datei_{self._get_thread_safe_timestamp()}"
        
        # Entferne ungültige Zeichen
        filename = ''.join(c for c in filename if c in self.config.allowed_chars)
        
        # Stelle sicher, dass nicht zu lang
        if len(filename) > self.config.max_filename_length:
            base, ext = Path(filename).stem, Path(filename).suffix
            max_base_length = self.config.max_filename_length - len(ext)
            filename = base[:max_base_length] + ext
        
        return filename
    
    def _create_fallback_name(self, file_info: Dict, extension: str) -> str:
        """Erstellt Fallback-Dateinamen"""
        timestamp = self._get_thread_safe_timestamp()
        original_hash = hashlib.md5(file_info['filename'].encode()).hexdigest()[:8]
        
        return f"datei_{timestamp}_{original_hash}{extension}"
    
    def reset(self):
        """Setzt Generator zurück (z.B. für neue Ordner)"""
        self._counter = 0
        self._generated_names.clear()
[file content end]

[file name]: groq_integration_fixed.py
[file content begin]
"""
Groq API Integration für intelligente Dateianalyse - Verbesserte Version
"""

import json
import logging
import time
import hashlib
import base64
from typing import Dict, List, Optional, Any, TypedDict
from pathlib import Path
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import backoff
from functools import lru_cache

try:
    from groq import Groq, GroqError
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    Groq = None
    GroqError = Exception

# Logging konfigurieren
logger = logging.getLogger(__name__)


@dataclass
class GroqConfig:
    """Konfiguration für Groq API"""
    api_key: str = ""
    model: str = "mixtral-8x7b-32768"
    max_tokens: int = 1000
    temperature: float = 0.3
    timeout: int = 30
    max_retries: int = 3
    rate_limit_delay: float = 1.0
    provider: str = "groq"
    use_groq_for_images: bool = False
    max_file_size_mb: int = 10  # Maximale Dateigröße für Bildanalyse


@dataclass
class AnalysisRequest:
    """Datenstruktur für Analyse-Anfragen"""
    files: List[Dict]
    granularity: str
    max_categories: int
    request_id: str = ""


@dataclass
class AnalysisResponse:
    """Datenstruktur für Analyse-Antworten"""
    request_id: str
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    processing_time: float = 0.0


class GroqAnalyzer:
    def __init__(self, config: Dict):
        # Validiere Konfiguration
        self.full_config = config
        ai_config = config.get('ai', {})
        
        self.config = GroqConfig(
            api_key=self._validate_api_key(ai_config.get('groq_api_key')),
            model=ai_config.get('groq_model', 'mixtral-8x7b-32768'),
            max_tokens=ai_config.get('max_tokens', 1000),
            temperature=ai_config.get('temperature', 0.3),
            timeout=ai_config.get('timeout', 30),
            max_retries=ai_config.get('max_retries', 3),
            rate_limit_delay=ai_config.get('rate_limit_delay', 1.0),
            provider=ai_config.get('provider', 'groq'),
            use_groq_for_images=ai_config.get('use_groq_for_images', False),
            max_file_size_mb=ai_config.get('max_file_size_mb', 10)
        )
        
        self.client = None
        self._rate_limit_last_call = 0.0
        
        # Cache für API-Antworten
        self.response_cache = {}
        self.cache_ttl = 300  # 5 Minuten
        
        # Thread Pool für parallele Anfragen
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # Initialisiere Client wenn API verfügbar und Key gültig
        if self.config.api_key and self.config.provider == 'groq' and GROQ_AVAILABLE:
            try:
                self.client = Groq(api_key=self.config.api_key, timeout=self.config.timeout)
                logger.info(f"✅ Groq API initialisiert mit Modell: {self.config.model}")
            except Exception as e:
                logger.error(f"⚠️ Groq API konnte nicht initialisiert werden: {e}")
                self.client = None
        else:
            if not GROQ_AVAILABLE:
                logger.warning("Groq Python client nicht verfügbar. Bitte installieren: pip install groq")
            elif not self.config.api_key:
                logger.warning("Kein Groq API Key konfiguriert")
            else:
                logger.warning(f"Provider {self.config.provider} nicht unterstützt")
    
    def _validate_api_key(self, api_key: Optional[str]) -> str:
        """Validiert und bereinigt API Key"""
        if not api_key or not isinstance(api_key, str):
            return ""
        
        # Entferne Whitespace
        api_key = api_key.strip()
        
        # Grundlegende Validierung (Groq Keys beginnen normalerweise mit 'gsk_')
        if not api_key.startswith('gsk_') and len(api_key) < 20:
            logger.warning("API Key scheint ungültig zu sein")
        
        return api_key
    
    def is_available(self) -> bool:
        """Prüft ob Groq API verfügbar ist"""
        return self.client is not None and GROQ_AVAILABLE
    
    def analyze_files_with_groq(self, files: List[Dict]) -> Dict[str, Any]:
        """
        Analysiert Dateien mit Groq API für intelligente Kategorisierung
        """
        if not self.is_available():
            return self._create_error_response("Groq API nicht verfügbar")
        
        # Generiere Request ID für Tracking
        request_id = self._generate_request_id(files)
        
        # Prüfe Cache
        cached_response = self._get_cached_response(request_id)
        if cached_response:
            logger.info(f"✅ Verwende gecachte Antwort für Request {request_id[:8]}")
            return cached_response
        
        logger.info(f"🤖 Analysiere {len(files)} Dateien mit Groq AI...")
        
        start_time = time.time()
        
        try:
            # Erstelle optimierte Anfrage
            analysis_request = AnalysisRequest(
                files=files,
                granularity=self.full_config.get('category_granularity', 'mittel'),
                max_categories=self._get_max_categories(),
                request_id=request_id
            )
            
            # Sende Anfrage mit Retry-Mechanismus
            response = self._send_analysis_request(analysis_request)
            
            # Parse und validiere Antwort
            validated_response = self._validate_and_clean_response(response, files)
            
            # Cache Antwort
            self._cache_response(request_id, validated_response)
            
            processing_time = time.time() - start_time
            logger.info(f"✅ Analyse abgeschlossen in {processing_time:.2f}s")
            
            return validated_response
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"⚠️ Groq API Fehler nach {processing_time:.2f}s: {e}")
            return self._create_error_response(str(e), processing_time)
    
    @backoff.on_exception(
        backoff.expo,
        (GroqError, ConnectionError, TimeoutError),
        max_tries=3,
        max_time=30
    )
    def _send_analysis_request(self, request: AnalysisRequest) -> Dict:
        """Sendet Analyse-Request mit Rate Limiting"""
        # Rate Limiting
        current_time = time.time()
        time_since_last_call = current_time - self._rate_limit_last_call
        
        if time_since_last_call < self.config.rate_limit_delay:
            sleep_time = self.config.rate_limit_delay - time_since_last_call
            logger.debug(f"Rate limiting: Warte {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        # Erstelle Prompt
        prompt = self._create_analysis_prompt(request)
        
        # Sende Anfrage
        try:
            self._rate_limit_last_call = time.time()
            
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                response_format={"type": "json_object"}
            )
            
            if not response.choices:
                raise GroqError("Keine Antwort von Groq API erhalten")
            
            content = response.choices[0].message.content
            if not content:
                raise GroqError("Leere Antwort von Groq API")
            
            return json.loads(content)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON-Parse-Fehler: {e}")
            raise GroqError(f"Ungültiges JSON von Groq API: {e}")
        except Exception as e:
            logger.error(f"API Request fehlgeschlagen: {e}")
            raise
    
    def _create_analysis_prompt(self, request: AnalysisRequest) -> str:
        """Erstellt Prompt für Groq API"""
        # Reduziere auf repräsentative Stichprobe
        sample_size = min(50, len(request.files))
        sample_files = request.files[:sample_size]
        
        # Vereinfache Daten für Prompt
        simplified_files = []
        for file in sample_files:
            simplified = {
                "filename": file.get("filename", ""),
                "extension": file.get("extension", ""),
                "size_kb": round(file.get("size_bytes", 0) / 1024, 1),
                "content_preview": file.get("content_preview", "")[:300],
                "image_analysis": self._get_image_analysis_summary(file),
                "aesthetic_score": round(file.get("analysis", {}).get("aesthetic", {}).get("score", 0), 2)
            }
            simplified_files.append(simplified)
        
        prompt = f"""
        ANALYSEAUFGABE: Dateien intelligent kategorisieren

        KONTEXT:
        - Insgesamt {len(request.files)} Dateien im Ordner
        - Zeige hier {len(simplified_files)} repräsentative Dateien
        - Gewünschte Granularität: {request.granularity} (ca. {request.max_categories} Kategorien)
        - Request ID: {request.request_id[:8]}
        
        REGELN für Kategorien:
        1. Sei PRÄZISE und PRAKTISCH
        2. Verwende DEUTSCHE Kategorienamen
        3. Kategorienamen: maximal 2-3 Wörter
        4. KEINE generischen Namen wie "Dokumente" oder "Bilder"
        5. Berücksichtige ÄSTHETISCHE Dateien (Score > 0.7) extra
        6. Gruppiere zusammengehörige Dateien (Projekte, Themen)
        
        DATEIEN:
        {json.dumps(simplified_files, indent=2, ensure_ascii=False)}

        ANTWORTFORMAT (JSON):
        {{
          "analysis_summary": "Kurze Zusammenfassung was du erkannt hast",
          "categories": [
            {{
              "name": "Kategoriename",
              "description": "Kurze Beschreibung",
              "priority": 1,  // 1=hoch, 2=mittel, 3=niedrig
              "file_count": 5,
              "example_files": ["datei1.jpg", "datei2.pdf"],
              "keywords": ["stichwort1", "stichwort2"]
            }}
          ],
          "file_assignments": [
            {{
              "filename": "datei1.jpg",
              "suggested_category": "Reisefotos/Italien",
              "confidence": 0.92,
              "reason": "Bild zeigt Kolosseum in Rom bei Sonnenuntergang",
              "keywords": ["reise", "italien", "rom", "kolosseum"]
            }}
          ],
          "aesthetic_collection": {{
            "name": "Inspiration & Schönes",
            "files": ["bild1.jpg", "bild2.png"],
            "reason": "Hoher ästhetischer Score und harmonische Farben",
            "avg_score": 0.85
          }},
          "metadata": {{
            "total_files": {len(request.files)},
            "analyzed_files": {len(simplified_files)},
            "granularity": "{request.granularity}",
            "request_id": "{request.request_id}"
          }}
        }}
        
        WICHTIG: Antworte NUR mit gültigem JSON, keine zusätzlichen Erklärungen.
        """
        
        return prompt
    
    def _get_image_analysis_summary(self, file: Dict) -> str:
        """Extrahiert Bildanalyse-Zusammenfassung"""
        if 'analysis' not in file or 'image' not in file['analysis']:
            return ""
        
        img_info = file['analysis']['image']
        summary_parts = []
        
        if 'description' in img_info:
            summary_parts.append(img_info['description'])
        
        if 'objects' in img_info and img_info['objects']:
            summary_parts.append(f"Objekte: {', '.join(img_info['objects'][:3])}")
        
        if 'dominant_colors' in img_info and img_info['dominant_colors']:
            colors = [c.get('name', '') for c in img_info['dominant_colors'][:2] if c.get('name')]
            if colors:
                summary_parts.append(f"Farben: {', '.join(colors)}")
        
        return "; ".join(summary_parts)
    
    def _get_system_prompt(self) -> str:
        """System-Prompt für Groq"""
        return """
        Du bist ein spezialisiertes System zur intelligenten Dateiorganisation.
        Deine Aufgabe: Dateien nach Inhalt, Kontext und Ästhetik analysieren.
        
        SPEZIFISCHE ANWEISUNGEN:
        1. Erkenne THEMEN und ZUSAMMENHÄNGE zwischen Dateien
        2. Berücksichtige Dateitypen, Inhalte und Metadaten
        3. Für Bilder: Analysiere Objekte, Farben, Komposition
        4. Für Dokumente: Erkenne Themen aus Textvorschau
        5. Für Code: Erkenne Programmiersprache und Zweck
        6. Erkenne Projekt-Strukturen und thematische Gruppen
        
        WICHTIG bei Kategorien:
        - Erfinde sinnvolle, spezifische Kategorienamen (2-3 Wörter max)
        - Gruppiere zusammengehörige Dateien (Projekte, Ereignisse, Themen)
        - Ästhetisch schöne Dateien extra kennzeichnen
        - Dateien mit ähnlichem Stil zusammenfassen
        - Vermeide generische Kategorien wie "Dokumente" oder "Bilder"
        
        Beispiele für gute Kategorien:
        - "Reisefotos/Italien 2023"
        - "Python/Datenanalyse Projekt"
        - "Verträge & Vereinbarungen"
        - "Inspiration/Design-Vorlagen"
        - "Projekt X/Dokumentation"
        
        Format: Gib immer gültiges JSON zurück.
        """
    
    def _validate_and_clean_response(self, result: Dict, files: List[Dict]) -> Dict[str, Any]:
        """Validiert und bereinigt das Groq-Ergebnis"""
        if not isinstance(result, dict):
            result = {}
        
        # Stelle sicher, dass alle benötigten Felder existieren
        default_result = {
            "analysis_summary": "Automatische Dateianalyse",
            "categories": [],
            "file_assignments": [],
            "aesthetic_collection": {
                "name": "Inspiration & Schönes",
                "files": [],
                "reason": "Dateien mit hohem ästhetischen Wert",
                "avg_score": 0.0
            },
            "metadata": {
                "total_files": len(files),
                "analyzed_files": min(50, len(files)),
                "granularity": self.full_config.get('category_granularity', 'mittel'),
                "request_id": hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
            }
        }
        
        # Merge mit Defaults
        for key, default_value in default_result.items():
            if key not in result:
                result[key] = default_value
            elif isinstance(default_value, dict) and isinstance(result[key], dict):
                result[key] = {**default_value, **result[key]}
        
        # Validiere Kategorien
        if not isinstance(result["categories"], list):
            result["categories"] = []
        
        result["categories"] = [
            cat for cat in result["categories"] 
            if isinstance(cat, dict) and "name" in cat
        ]
        
        # Stelle sicher, dass alle Dateien zugeordnet werden
        if result["file_assignments"] and isinstance(result["file_assignments"], list):
            assigned_files = {
                a.get("filename", "") for a in result["file_assignments"] 
                if isinstance(a, dict)
            }
            
            all_files = {f.get("filename", "") for f in files if isinstance(f, dict)}
            missing_files = all_files - assigned_files
            
            if missing_files:
                for filename in missing_files:
                    result["file_assignments"].append({
                        "filename": filename,
                        "suggested_category": "Unsortiert/Verschiedenes",
                        "confidence": 0.5,
                        "reason": "Automatisch zugeordnet",
                        "keywords": ["unsortiert"]
                    })
        
        return result
    
    def describe_image_with_groq(self, image_path: Path, analysis: Dict) -> str:
        """
        Beschreibt ein Bild mit Groq API
        Nur wenn use_groq_for_images = True
        """
        if not self.is_available() or not self.config.use_groq_for_images:
            return analysis.get('description', 'Bild')
        
        # Prüfe Dateigröße
        try:
            file_size_mb = image_path.stat().st_size / (1024 * 1024)
            if file_size_mb > self.config.max_file_size_mb:
                logger.warning(f"Bild zu groß für Groq-Analyse: {file_size_mb:.1f}MB")
                return analysis.get('description', 'Bild')
        except:
            pass
        
        try:
            # Lies Bild in Chunks für große Dateien
            with open(image_path, 'rb') as img_file:
                img_data = img_file.read()
            
            # Base64 codieren
            img_base64 = base64.b64encode(img_data).decode('utf-8')
            
            # Erstelle Prompt mit vorhandener Analyse
            existing_objects = analysis.get('objects', [])[:5]
            existing_colors = [
                c.get('name', '') for c in analysis.get('dominant_colors', [])[:3] 
                if c.get('name')
            ]
            
            prompt = f"""
            Bildanalyse für Dateinamen-Generierung:
            
            Vorhandene Analyse:
            - Hauptobjekte: {existing_objects or 'keine erkannt'}
            - Dominante Farben: {existing_colors or 'keine erkannt'}
            - Helligkeit: {'hell' if analysis.get('brightness', 0.5) > 0.7 else 'dunkel' if analysis.get('brightness', 0.5) < 0.3 else 'mittel'}
            
            Anforderung:
            Generiere 3-5 aussagekräftige Stichworte für einen Dateinamen.
            Format: stichwort1_stichwort2_stichwort3 (nur Kleinbuchstaben, Unterstriche)
            
            Beispiele:
            - sonnenuntergang_meer_strand_abend
            - katze_fensterbank_schlafend
            - gebaeude_architektur_modern
            """
            
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {
                        "role": "system", 
                        "content": "Du generierst präzise Stichworte für Bild-Dateinamen. Maximal 5 Wörter, durch Unterstriche getrennt, nur Kleinbuchstaben."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=50
            )
            
            description = response.choices[0].message.content.strip()
            
            # Bereinige die Antwort
            description = description.replace('.', '').replace(',', '').lower()
            description = re.sub(r'[^a-z0-9_]', '_', description)
            description = re.sub(r'_+', '_', description)
            description = description.strip('_')
            
            # Kürze wenn nötig
            if len(description) > 50:
                parts = description.split('_')
                if len(parts) > 5:
                    description = '_'.join(parts[:5])
                else:
                    description = description[:50]
            
            return description if len(description) > 3 else analysis.get('description', 'bild')
            
        except Exception as e:
            logger.warning(f"Groq Bildbeschreibung fehlgeschlagen: {e}")
            return analysis.get('description', 'bild')
    
    def suggest_renaming(self, files: List[Dict]) -> Dict[str, str]:
        """
        Schlägt intelligente Umbenennung für Dateien vor (batch)
        """
        if not self.is_available():
            return {}
        
        try:
            # Teile Dateien in Batches auf
            batch_size = 20
            all_suggestions = {}
            
            for i in range(0, len(files), batch_size):
                batch = files[i:i+batch_size]
                
                prompt = self._create_renaming_prompt(batch)
                
                try:
                    response = self.client.chat.completions.create(
                        model=self.config.model,
                        messages=[
                            {
                                "role": "system", 
                                "content": "Du schlägst beschreibende Dateinamen vor. Format: JSON mit 'renaming_suggestions' Dictionary."
                            },
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.3,
                        max_tokens=800,
                        response_format={"type": "json_object"}
                    )
                    
                    suggestions = json.loads(response.choices[0].message.content)
                    batch_suggestions = suggestions.get("renaming_suggestions", {})
                    
                    # Validiere und füge hinzu
                    for old_name, new_name in batch_suggestions.items():
                        if isinstance(new_name, str) and len(new_name) <= 80:
                            all_suggestions[old_name] = new_name
                    
                    # Rate Limiting
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.warning(f"Batch {i//batch_size + 1} fehlgeschlagen: {e}")
                    continue
            
            return all_suggestions
            
        except Exception as e:
            logger.error(f"Umbenennungsvorschläge fehlgeschlagen: {e}")
            return {}
    
    def _create_renaming_prompt(self, files: List[Dict]) -> str:
        """Erstellt Prompt für Umbenennungsvorschläge"""
        file_list = []
        
        for file in files:
            file_list.append({
                "current_name": file.get("filename", ""),
                "type": file.get("extension", ""),
                "size_kb": round(file.get("size_bytes", 0) / 1024, 1),
                "content_hint": file.get("content_preview", "")[:150],
                "image_description": file.get("analysis", {}).get("image", {}).get("description", "") 
                    if "image" in file.get("analysis", {}) else ""
            })
        
        return f"""
        Vorschläge für beschreibende Dateinamen:
        
        REGELN:
        1. Dateinamen sollen INHALT beschreiben (deutsche Wörter)
        2. Maximal 50 Zeichen (inkl. Extension)
        3. Keine Sonderzeichen außer Unterstrichen und Bindestrichen
        4. Bei Bildern: Hauptobjekte + Stimmung/Kontext
        5. Bei Dokumenten: Thema + Zweck + ggf. Datum
        6. Bei Code: Funktion + Programmiersprache
        
        BEISPIELE:
        - "IMG_1234.jpg" → "sonnenuntergang_berge_20240115.jpg"
        - "scan.pdf" → "mietvertrag_wohnung_berlin_2023.pdf"
        - "data.csv" → "umsatzdaten_q1_2024.csv"
        - "script.py" → "daten_bereinigung_python.py"
        
        DATEIEN:
        {json.dumps(file_list, indent=2, ensure_ascii=False)}
        
        ANTWORTFORMAT (JSON):
        {{
          "renaming_suggestions": {{
            "alter_dateiname.ext": "neuer_dateiname.ext"
          }}
        }}
        """
    
    def _get_max_categories(self) -> int:
        """Bestimmt maximale Anzahl an Kategorien basierend auf Granularität"""
        granularity = self.full_config.get('category_granularity', 'mittel')
        
        return {
            'wenig': 8,
            'mittel': 15,
            'viel': 25,
            'sehr_viel': 40
        }.get(granularity, 15)
    
    def _generate_request_id(self, files: List[Dict]) -> str:
        """Generiert eindeutige Request ID"""
        file_info = "|".join(sorted([f.get("filename", "") for f in files[:10]]))
        timestamp = str(time.time())
        
        return hashlib.md5((file_info + timestamp).encode()).hexdigest()
    
    def _get_cached_response(self, request_id: str) -> Optional[Dict]:
        """Holt gecachte Antwort"""
        if request_id in self.response_cache:
            cached_time, response = self.response_cache[request_id]
            if time.time() - cached_time < self.cache_ttl:
                return response
        
        return None
    
    def _cache_response(self, request_id: str, response: Dict):
        """Cached API-Antwort"""
        self.response_cache[request_id] = (time.time(), response)
        
        # Bereinige alten Cache
        current_time = time.time()
        expired_keys = [
            key for key, (cached_time, _) in self.response_cache.items()
            if current_time - cached_time > self.cache_ttl
        ]
        
        for key in expired_keys:
            del self.response_cache[key]
    
    def _create_error_response(self, error_message: str, processing_time: float = 0.0) -> Dict[str, Any]:
        """Erstellt Fehler-Antwort"""
        return {
            "error": error_message,
            "categories": [],
            "file_assignments": [],
            "aesthetic_collection": {
                "name": "Inspiration & Schönes",
                "files": [],
                "reason": "",
                "avg_score": 0.0
            },
            "metadata": {
                "total_files": 0,
                "analyzed_files": 0,
                "granularity": self.full_config.get('category_granularity', 'mittel'),
                "request_id": "",
                "processing_time": processing_time,
                "success": False
            }
        }
    
    def close(self):
        """Ressourcen freigeben"""
        self.executor.shutdown(wait=True)
        self.response_cache.clear()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Utility-Funktionen
import re
[file content end]

[file name]: image_analyzer_fixed.py
[file content begin]
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
[file content end]