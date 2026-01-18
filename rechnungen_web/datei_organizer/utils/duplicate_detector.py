"""
Erweiterte Duplikaterkennung
"""

import hashlib
from pathlib import Path
from typing import Dict, List, Set, Tuple
try:
    import xxhash
    XXHASH_AVAILABLE = True
except ImportError:
    XXHASH_AVAILABLE = False
from PIL import Image
import numpy as np

class DuplicateDetector:
    def __init__(self, config: Dict):
        self.config = config
        self.similarity_threshold = config.get('similarity_threshold', 0.95)
        
    def find_duplicates(self, files: List[Dict]) -> List[List[Dict]]:
        """Findet Duplikate mit verschiedenen Methoden"""
        print("🔍 Suche nach Duplikaten...")
        
        # Methode 1: Exakte Duplikate (Hash)
        exact_duplicates = self.find_exact_duplicates(files)
        
        # Methode 2: Ähnliche Dateien (Inhalt)
        similar_files = self.find_similar_files(files, exact_duplicates)
        
        # Methode 3: Bild-Duplikate (visuell ähnlich)
        image_duplicates = self.find_image_duplicates(files)
        
        # Kombiniere alle Ergebnisse
        all_duplicates = exact_duplicates + similar_files + image_duplicates
        
        # Entferne doppelte Einträge
        return self.deduplicate_groups(all_duplicates)
    
    def find_exact_duplicates(self, files: List[Dict]) -> List[List[Dict]]:
        """Findet exakte Duplikate (gleicher Hash)"""
        hash_groups = {}
        
        for file in files:
            # Berechne Hash (schnell mit xxhash oder fallback zu md5)
            try:
                if XXHASH_AVAILABLE:
                    file_hash = self.calculate_xxhash(Path(file['path']))
                else:
                    file_hash = self.calculate_md5_hash(Path(file['path']))
                
                if file_hash not in hash_groups:
                    hash_groups[file_hash] = []
                hash_groups[file_hash].append(file)
            except:
                continue
        
        # Nur Gruppen mit mehr als einer Datei
        return [group for group in hash_groups.values() if len(group) > 1]
    
    def calculate_xxhash(self, file_path: Path) -> str:
        """Berechnet schnellen Hash mit xxhash"""
        hasher = xxhash.xxh64()
        
        with open(file_path, 'rb') as f:
            # Lese in Blöcken für große Dateien
            while chunk := f.read(8192):
                hasher.update(chunk)
        
        return hasher.hexdigest()
    
    def calculate_md5_hash(self, file_path: Path) -> str:
        """Fallback: MD5 Hash"""
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            # Nur ersten 64KB für schnellen Hash
            hasher.update(f.read(65536))
        return hasher.hexdigest()
    
    def find_similar_files(self, files: List[Dict], exclude_groups: List[List[Dict]]) -> List[List[Dict]]:
        """Findet ähnliche Dateien (gleicher Typ, ähnliche Größe/Name)"""
        # Dateien, die schon in exakten Duplikaten sind
        excluded_files = set()
        for group in exclude_groups:
            for file in group:
                excluded_files.add(file['path'])
        
        # Gruppiere nach Typ und ähnlicher Größe
        similar_groups = {}
        
        for file in files:
            if file['path'] in excluded_files:
                continue
            
            key = f"{file['extension']}_{self.get_size_bucket(file['size_bytes'])}"
            
            if key not in similar_groups:
                similar_groups[key] = []
            similar_groups[key].append(file)
        
        # Prüfe ähnliche Namen innerhalb der Gruppen
        result = []
        for files_in_group in similar_groups.values():
            if len(files_in_group) < 2:
                continue
            
            # Gruppiere nach ähnlichen Namen
            name_groups = self.group_by_similar_names(files_in_group)
            
            for name_group in name_groups:
                if len(name_group) > 1:
                    result.append(name_group)
        
        return result
    
    def get_size_bucket(self, size_bytes: int) -> str:
        """Gruppiert Dateigrößen in Buckets"""
        if size_bytes < 1024:  # < 1KB
            return "tiny"
        elif size_bytes < 1024 * 1024:  # < 1MB
            return "small"
        elif size_bytes < 10 * 1024 * 1024:  # < 10MB
            return "medium"
        elif size_bytes < 100 * 1024 * 1024:  # < 100MB
            return "large"
        else:
            return "huge"
    
    def group_by_similar_names(self, files: List[Dict]) -> List[List[Dict]]:
        """Gruppiert Dateien mit ähnlichen Namen"""
        from difflib import SequenceMatcher
        
        groups = []
        processed = set()
        
        for i, file1 in enumerate(files):
            if file1['path'] in processed:
                continue
            
            current_group = [file1]
            processed.add(file1['path'])
            
            for j, file2 in enumerate(files[i+1:], i+1):
                if file2['path'] in processed:
                    continue
                
                # Berechne Namensähnlichkeit
                similarity = SequenceMatcher(
                    None, 
                    file1['filename'].lower(), 
                    file2['filename'].lower()
                ).ratio()
                
                if similarity > 0.7:  # 70% ähnlich
                    current_group.append(file2)
                    processed.add(file2['path'])
            
            if len(current_group) > 1:
                groups.append(current_group)
        
        return groups
    
    def find_image_duplicates(self, files: List[Dict]) -> List[List[Dict]]:
        """Findet visuell ähnliche Bilder"""
        image_files = [f for f in files if f['extension'] in ['.jpg', '.jpeg', '.png', '.webp']]
        
        if len(image_files) < 2:
            return []
        
        print(f"  🔍 Prüfe {len(image_files)} Bilder auf visuelle Ähnlichkeit...")
        
        # Berechne Image Hashes
        image_hashes = {}
        
        for file in image_files:
            try:
                img_hash = self.calculate_image_hash(Path(file['path']))
                
                if img_hash and img_hash not in image_hashes:
                    image_hashes[img_hash] = []
                if img_hash:
                    image_hashes[img_hash].append(file)
            except Exception as e:
                continue
        
        # Finde ähnliche Hashes (Hamming-Distanz)
        similar_groups = []
        hash_list = list(image_hashes.items())
        
        for i, (hash1, files1) in enumerate(hash_list):
            current_group = files1.copy()
            
            for j, (hash2, files2) in enumerate(hash_list[i+1:], i+1):
                # Berechne Hamming-Distanz
                if self.hamming_distance(hash1, hash2) < 10:  # Ähnlich
                    current_group.extend(files2)
            
            if len(current_group) > len(files1):  # Wir haben ähnliche gefunden
                similar_groups.append(current_group)
        
        return similar_groups
    
    def calculate_image_hash(self, image_path: Path) -> str:
        """Berechnet Perceptual Hash für Bild"""
        try:
            img = Image.open(image_path)
            
            # Reduziere Größe für Hash
            img = img.resize((8, 8), Image.Resampling.LANCZOS)
            
            # Konvertiere zu Graustufen
            img = img.convert('L')
            
            # Berechne Durchschnitt
            pixels = list(img.getdata())
            avg = sum(pixels) / len(pixels)
            
            # Erstelle Hash
            hash_str = ''
            for pixel in pixels:
                hash_str += '1' if pixel > avg else '0'
            
            return hash_str
            
        except:
            return ''
    
    def hamming_distance(self, hash1: str, hash2: str) -> int:
        """Berechnet Hamming-Distanz zwischen zwei Hashes"""
        if len(hash1) != len(hash2):
            return 64  # Maximalwert
        
        return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
    
    def deduplicate_groups(self, groups: List[List[Dict]]) -> List[List[Dict]]:
        """Entfernt doppelte Dateien aus Gruppen"""
        file_to_groups = {}
        
        # Map: Datei → Gruppe Index
        for i, group in enumerate(groups):
            for file in group:
                if file['path'] not in file_to_groups:
                    file_to_groups[file['path']] = []
                file_to_groups[file['path']].append(i)
        
        # Entferne Duplikate
        processed_files = set()
        result = []
        
        for i, group in enumerate(groups):
            clean_group = []
            
            for file in group:
                if file['path'] not in processed_files:
                    clean_group.append(file)
                    processed_files.add(file['path'])
            
            if len(clean_group) > 1:
                result.append(clean_group)
        
        return result
    
    def suggest_duplicate_handling(self, duplicate_groups: List[List[Dict]]) -> Dict:
        """Schlägt Behandlung von Duplikaten vor"""
        suggestions = {}
        
        for i, group in enumerate(duplicate_groups):
            if len(group) < 2:
                continue
            
            # Analysiere Gruppe
            newest = max(group, key=lambda x: x.get('modified', ''))
            largest = max(group, key=lambda x: x.get('size_bytes', 0))
            smallest = min(group, key=lambda x: x.get('size_bytes', 0))
            
            suggestions[f"gruppe_{i}"] = {
                "files": [f['filename'] for f in group],
                "count": len(group),
                "suggestions": [
                    f"Behalte neueste: {newest['filename']}",
                    f"Behalte größte: {largest['filename']}",
                    f"Behalte kleinste: {smallest['filename']}",
                    "Behalte alle",
                    "Manuell auswählen"
                ],
                "stats": {
                    "size_range": f"{smallest['size_bytes']/1024:.1f}KB - {largest['size_bytes']/1024:.1f}KB",
                    "age_range": f"{min(group, key=lambda x: x.get('modified', ''))['modified'][:10]} - {newest['modified'][:10]}"
                }
            }
        
        return suggestions
