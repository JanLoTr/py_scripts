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