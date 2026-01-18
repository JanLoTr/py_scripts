#!/usr/bin/env python3
"""
ERWEITERTER DATEI-ORGANIZER mit Groq API Integration
"""

import os
import json
import sys
import shutil
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import click

# Eigene Module
from utils.image_analyzer import ImageAnalyzer
from utils.duplicate_detector import DuplicateDetector
from utils.filename_generator import FilenameGenerator
from utils.aesthetic_scorer import AestheticScorer
from utils.groq_integration import GroqAnalyzer

class EnhancedFileOrganizer:
    def __init__(self, config_path: Optional[Path] = None):
        self.config = self.load_config(config_path)
        
        # Module initialisieren
        self.image_analyzer = ImageAnalyzer(self.config)
        self.duplicate_detector = DuplicateDetector(self.config)
        self.filename_generator = FilenameGenerator(self.config)
        self.aesthetic_scorer = AestheticScorer(self.config)
        self.groq_analyzer = GroqAnalyzer(self.config)
        
        self.stats = {
            'total_files': 0,
            'processed': 0,
            'organized': 0,
            'renamed': 0,
            'duplicates_found': 0,
            'duplicates_handled': 0,
            'aesthetic_files': 0,
            'errors': 0,
            'groq_used': False
        }
        
        self.categories = {}
    
    def load_config(self, config_path: Optional[Path]) -> Dict:
        """Lädt Konfiguration mit Defaults"""
        defaults = {
            'input_dir': Path.home() / 'Downloads',
            'output_dir': Path.home() / 'Documents' / 'Organized',
            'category_granularity': 'mittel',
            'max_categories': {'wenig': 5, 'mittel': 15, 'viel': 30},
            'duplicate_handling': 'ask',
            'similarity_threshold': 0.95,
            'rename_files': True,
            'naming_scheme': 'descriptive',
            'detect_aesthetic_files': True,
            'aesthetic_categories': ['inspiration', 'schön', 'lustig', 'kunst', 'design'],
            'interactive': True,
            'preview_before_move': True,
            'image_analysis': {'use_yolo': True, 'describe_scene': True},
            'supported_extensions': [
                '.pdf', '.docx', '.doc', '.txt', '.md', '.json', '.csv', '.xlsx', '.xls',
                '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif', '.webp',
                '.py', '.c', '.cpp', '.java', '.js', '.ts', '.html', '.css', '.sql',
                '.mp3', '.mp4', '.avi', '.mov', '.wav', '.flac'
            ],
            'ai': {
                'provider': 'groq',
                'groq_api_key': '',
                'groq_model': 'mixtral-8x7b-32768',
                'use_groq_for_categorization': True,
                'use_groq_for_renaming': False
            }
        }
        
        if config_path and config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                # Tiefe Merge für nested dictionaries
                self.deep_merge(defaults, user_config)
        
        # Pfade konvertieren
        defaults['input_dir'] = Path(defaults['input_dir'])
        defaults['output_dir'] = Path(defaults['output_dir'])
        
        # Validierung: Prüfe ob Input-Verzeichnis existiert
        if not defaults['input_dir'].exists():
            print(f"⚠️ Warnung: Eingabeverzeichnis existiert nicht: {defaults['input_dir']}")
            print("   Bitte erstelle das Verzeichnis oder passe die Config an.")
        
        return defaults
    
    def deep_merge(self, base: Dict, update: Dict):
        """Führt dictionaries rekursiv zusammen"""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self.deep_merge(base[key], value)
            else:
                base[key] = value
    
    def run(self):
        """Hauptausführung"""
        print("="*60)
        print("🤖 ERWEITERTER DATEI-ORGANIZER mit Groq AI")
        print("="*60)
        
        # Validierung: Prüfe ob Input-Verzeichnis existiert
        if not self.config['input_dir'].exists():
            print(f"❌ Fehler: Eingabeverzeichnis existiert nicht: {self.config['input_dir']}")
            print("   Bitte erstelle das Verzeichnis oder passe die Config an.")
            return
        
        # Output-Verzeichnis erstellen falls nicht vorhanden
        try:
            self.config['output_dir'].mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"❌ Fehler: Ausgabeverzeichnis konnte nicht erstellt werden: {e}")
            return
        
        # Groq API Verfügbarkeit prüfen
        if self.groq_analyzer.is_available():
            print("✅ Groq AI verfügbar")
            self.stats['groq_used'] = True
        else:
            print("⚠️  Groq AI nicht verfügbar - verwende lokale Analyse")
        
        # Granularität fragen
        if self.config['interactive']:
            self.ask_user_preferences()
        
        # 1. Dateien analysieren
        print("\n🔍 STEP 1: Dateien analysieren...")
        analysis = self.analyze_files()
        
        if not analysis:
            print("❌ Analyse fehlgeschlagen")
            return
        
        # 2. Groq für intelligente Kategorisierung
        print("\n🤖 STEP 2: Intelligente Kategorisierung mit Groq...")
        if self.config['ai'].get('use_groq_for_categorization', True) and self.groq_analyzer.is_available():
            groq_result = self.groq_analyzer.analyze_files_with_groq(analysis['files'])
            
            if 'error' not in groq_result:
                # Übernehme Groq-Kategorien
                analysis['groq_categories'] = groq_result.get('categories', [])
                analysis['groq_assignments'] = groq_result.get('file_assignments', [])
                analysis['aesthetic_collection'] = groq_result.get('aesthetic_collection', {})
                
                print("✅ Groq Analyse erfolgreich")
                
                # Zeige Groq-Vorschläge
                self.show_groq_suggestions(groq_result)
            else:
                print(f"⚠️  Groq Analyse fehlgeschlagen: {groq_result['error']}")
        
        # 3. Duplikate behandeln
        print("\n🔍 STEP 3: Duplikate behandeln...")
        if analysis['duplicates']:
            analysis['duplicates'] = self.handle_duplicates_interactive(analysis['duplicates'])
        
        # 4. Umbenennungsvorschläge von Groq
        if self.config['ai'].get('use_groq_for_renaming', False) and self.groq_analyzer.is_available():
            print("\n📝 STEP 4: Intelligente Umbenennung mit Groq...")
            renaming_suggestions = self.groq_analyzer.suggest_renaming(analysis['files'])
            analysis['groq_renaming'] = renaming_suggestions
        
        # 5. Zusammenfassung anzeigen
        self.show_analysis_summary(analysis)
        
        # 6. Organisieren (falls gewünscht)
        if self.config['interactive']:
            proceed = input("\n📋 Mit Organisation fortfahren? (ja/nein): ").lower()
            if proceed != 'ja':
                print("❌ Abgebrochen.")
                return
        
        # 7. Dateien organisieren
        print("\n📦 STEP 5: Dateien organisieren...")
        success = self.organize_files(analysis)
        
        # 8. Bericht speichern
        self.save_report(analysis)
        
        if success:
            print(f"\n✅ Fertig! {self.stats['organized']} Dateien organisiert.")
        else:
            print("\n⚠️ Organisation abgebrochen.")
    
    def ask_user_preferences(self):
        """Fragt Benutzer nach Präferenzen"""
        print("\n📊 KONFIGURATION")
        print("-" * 40)
        
        # Kategoriengranularität
        print("Wie detailliert sollen Kategorien sein?")
        print("1. Wenig (ca. 5 Hauptkategorien)")
        print("2. Mittel (ca. 15 Kategorien)")
        print("3. Viel (ca. 30 spezifische Kategorien)")
        print("4. Automatisch bestimmen lassen")
        
        choice = input("\nDeine Wahl (1-4): ").strip()
        if choice == '1':
            self.config['category_granularity'] = 'wenig'
        elif choice == '2':
            self.config['category_granularity'] = 'mittel'
        elif choice == '3':
            self.config['category_granularity'] = 'viel'
        else:
            self.config['category_granularity'] = 'auto'
        
        # Groq Nutzung fragen
        if self.groq_analyzer.is_available():
            print("\n🤖 Groq AI verwenden für:")
            print("1. Nur Kategorisierung")
            print("2. Kategorisierung und Umbenennung")
            print("3. Gar nicht verwenden")
            
            ai_choice = input("\nDeine Wahl (1-3): ").strip()
            if ai_choice == '1':
                self.config['ai']['use_groq_for_categorization'] = True
                self.config['ai']['use_groq_for_renaming'] = False
            elif ai_choice == '2':
                self.config['ai']['use_groq_for_categorization'] = True
                self.config['ai']['use_groq_for_renaming'] = True
            else:
                self.config['ai']['use_groq_for_categorization'] = False
                self.config['ai']['use_groq_for_renaming'] = False
    
    def show_groq_suggestions(self, groq_result: Dict):
        """Zeigt Groq-Vorschläge an"""
        if 'categories' in groq_result:
            print("\n🤖 GROQ KATEGORIE-VORSCHLÄGE:")
            print("-" * 40)
            
            for category in groq_result['categories'][:10]:  # Zeige nur erste 10
                print(f"📁 {category['name']}:")
                print(f"   {category['description']}")
                print(f"   Dateien: {category['file_count']}")
                
                if 'example_files' in category:
                    examples = ', '.join(category['example_files'][:3])
                    print(f"   Beispiele: {examples}")
                print()
        
        if 'aesthetic_collection' in groq_result:
            aesthetic = groq_result['aesthetic_collection']
            print("\n🎨 ÄSTHETISCHE SAMMLUNG:")
            print(f"   Name: {aesthetic.get('name', 'Inspiration')}")
            print(f"   Dateien: {len(aesthetic.get('files', []))}")
            print(f"   Grund: {aesthetic.get('reason', '')}")
    
    def analyze_files(self) -> Optional[Dict]:
        """Analysiert alle Dateien"""
        print(f"📁 Durchsuche: {self.config['input_dir']}")
        
        all_files = []
        for ext in self.config.get('supported_extensions', ['.*']):
            if ext == '.*':
                all_files.extend(self.config['input_dir'].rglob("*"))
            else:
                all_files.extend(self.config['input_dir'].rglob(f"*{ext}"))
        
        self.stats['total_files'] = len(all_files)
        
        if self.stats['total_files'] == 0:
            print("❌ Keine Dateien gefunden")
            return None
        
        print(f"🔍 Gefunden: {self.stats['total_files']} Dateien")
        
        results = []
        for file_path in all_files[:1000]:  # Begrenze auf 1000 Dateien pro Lauf
            try:
                if file_path.is_file():
                    file_info = self.analyze_single_file(file_path)
                    results.append(file_info)
                    self.stats['processed'] += 1
                    
                    # Fortschritt anzeigen
                    if self.stats['processed'] % 50 == 0:
                        print(f"  Verarbeitet: {self.stats['processed']}/{self.stats['total_files']}")
            except Exception as e:
                print(f"⚠️ Fehler bei {file_path.name}: {e}")
                self.stats['errors'] += 1
        
        # Duplikate finden
        duplicate_groups = self.duplicate_detector.find_duplicates(results)
        self.stats['duplicates_found'] = sum(len(group) for group in duplicate_groups)
        
        # Ästhetische Dateien
        aesthetic_files = []
        if self.config['detect_aesthetic_files']:
            aesthetic_files = self.aesthetic_scorer.find_aesthetic_files(results)
            self.stats['aesthetic_files'] = len(aesthetic_files)
        
        # Lokale Kategorien (Fallback)
        categories = self.suggest_categories_local(results)
        
        return {
            'files': results,
            'duplicates': duplicate_groups,
            'aesthetic_files': aesthetic_files,
            'local_categories': categories,
            'categories': categories,  # Für Kompatibilität
            'stats': self.stats.copy()
        }
    
    def analyze_single_file(self, file_path: Path) -> Dict:
        """Analysiert eine einzelne Datei mit allen Funktionen"""
        file_info = {
            'path': str(file_path),
            'filename': file_path.name,
            'extension': file_path.suffix.lower(),
            'size_bytes': file_path.stat().st_size,
            'modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
            'created': datetime.fromtimestamp(file_path.stat().st_ctime).isoformat(),
            'hash': self.calculate_file_hash(file_path),
            'content_preview': '',
            'metadata': {},
            'analysis': {}
        }
        
        # Inhalt extrahieren
        file_info['content_preview'] = self.extract_content_preview(file_path)
        
        # Für Bilder: Erweiterte Analyse
        if file_info['extension'] in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
            image_analysis = self.image_analyzer.analyze_image(file_path)
            file_info['analysis']['image'] = image_analysis
            
            # Automatische Beschreibung generieren
            if self.config['rename_files'] and self.config['naming_scheme'] == 'descriptive':
                description = self.image_analyzer.describe_image(image_analysis)
                file_info['suggested_name'] = self.filename_generator.generate_image_name(
                    description, file_info['extension']
                )
        
        # Ästhetik bewerten
        if self.config['detect_aesthetic_files']:
            aesthetic_score = self.aesthetic_scorer.score_file(file_path, file_info)
            file_info['analysis']['aesthetic'] = {
                'score': aesthetic_score,
                'category': self.aesthetic_scorer.get_aesthetic_category(aesthetic_score)
            }
        
        return file_info
    
    def extract_content_preview(self, file_path: Path) -> str:
        """Extrahiert Vorschau-Inhalt basierend auf Dateityp"""
        ext = file_path.suffix.lower()
        
        try:
            if ext in ['.txt', '.md', '.json', '.csv']:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read(2000)
            elif ext == '.pdf':
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    text = ""
                    for page in pdf.pages[:2]:  # Nur erste 2 Seiten
                        text += page.extract_text() or ""
                    return text[:2000]
            elif ext == '.py':
                with open(file_path, 'r', encoding='utf-8') as f:
                    # Extrahiere Kommentare und Funktionen
                    lines = f.readlines()
                    important = [l for l in lines if l.strip().startswith(('#', 'def ', 'class '))]
                    return ''.join(important[:20])[:2000]
            else:
                return f"Dateityp: {ext}"
        except:
            return f"Kann Inhalt nicht lesen: {ext}"
    
    def calculate_file_hash(self, file_path: Path) -> str:
        """Berechnet Hash für Duplikaterkennung"""
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            # Nur ersten 64KB für schnellen Hash
            hasher.update(f.read(65536))
        return hasher.hexdigest()
    
    def handle_duplicates_interactive(self, duplicate_groups: List[List[Dict]]) -> List[List[Dict]]:
        """Behandelt Duplikate interaktiv"""
        if not duplicate_groups:
            return []
        
        print(f"\n🔍 {self.stats['duplicates_found']} mögliche Duplikate gefunden!")
        print("Wie möchtest Du mit Duplikaten umgehen?")
        print("1. Behalte alle")
        print("2. Behalte nur die neueste Version")
        print("3. Behalte nur die größte Datei")
        print("4. Manuell für jede Gruppe entscheiden")
        print("5. Zeige Details der Duplikate")
        
        choice = input("\nDeine Wahl (1-5): ").strip()
        
        if choice == '1':
            print("✅ Behalte alle Dateien")
            return duplicate_groups
        elif choice in ['2', '3']:
            strategy = 'newest' if choice == '2' else 'largest'
            filtered_groups = []
            for group in duplicate_groups:
                if strategy == 'newest':
                    newest = max(group, key=lambda x: x.get('modified', ''))
                    filtered_groups.append([newest])
                else:
                    largest = max(group, key=lambda x: x.get('size_bytes', 0))
                    filtered_groups.append([largest])
            return filtered_groups
        elif choice == '4':
            return self.manual_duplicate_selection(duplicate_groups)
        elif choice == '5':
            self.show_duplicate_details(duplicate_groups)
            return self.handle_duplicates_interactive(duplicate_groups)
        
        return duplicate_groups
    
    def manual_duplicate_selection(self, duplicate_groups: List[List[Dict]]) -> List[List[Dict]]:
        """Manuelle Auswahl für jede Duplikatgruppe"""
        filtered = []
        for i, group in enumerate(duplicate_groups, 1):
            print(f"\nGruppe {i} ({len(group)} Dateien):")
            for j, file in enumerate(group, 1):
                size_mb = file['size_bytes'] / 1024 / 1024
                modified = file['modified'][:10]
                print(f"  {j}. {file['filename']} ({size_mb:.1f} MB, {modified})")
            
            while True:
                choice = input(f"Welche Datei behalten? (1-{len(group)} oder 'alle'): ").strip()
                if choice.lower() == 'alle':
                    filtered.append(group)
                    break
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(group):
                        filtered.append([group[idx]])
                        break
                except ValueError:
                    print("❌ Ungültige Eingabe.")
        
        return filtered
    
    def suggest_categories_local(self, files: List[Dict]) -> Dict:
        """Schlägt Kategorien basierend auf Granularität vor (lokale Methode)"""
        granularity = self.config['category_granularity']
        if granularity == 'auto':
            if len(files) < 50:
                granularity = 'wenig'
            elif len(files) < 200:
                granularity = 'mittel'
            else:
                granularity = 'viel'
        
        max_cats = self.config['max_categories'][granularity]
        categories = {}
        
        for file in files:
            cat = self.get_base_category(file)
            
            if granularity == 'viel':
                cat = self.get_detailed_category(file, cat)
            elif granularity == 'mittel':
                cat = self.get_medium_category(file, cat)
            
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(file)
        
        if len(categories) > max_cats:
            categories = self.merge_similar_categories(categories, max_cats)
        
        return categories
    
    def get_base_category(self, file: Dict) -> str:
        """Bestimmt Basiskategorie"""
        ext = file['extension']
        
        if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp']:
            return 'Bilder'
        elif ext in ['.pdf', '.docx', '.doc', '.txt', '.md']:
            return 'Dokumente'
        elif ext in ['.mp3', '.wav', '.flac', '.mp4', '.avi', '.mov']:
            return 'Medien'
        elif ext in ['.py', '.c', '.cpp', '.java', '.js']:
            return 'Code'
        elif ext in ['.xlsx', '.xls', '.csv']:
            return 'Tabellen'
        else:
            return 'Sonstiges'
    
    def get_medium_category(self, file: Dict, base_cat: str) -> str:
        """Mittlere Detaillierung"""
        if base_cat == 'Bilder':
            if 'analysis' in file and 'image' in file['analysis']:
                img_info = file['analysis']['image']
                if 'objects' in img_info:
                    objects = img_info['objects']
                    if any(obj in ['person', 'face'] for obj in objects):
                        return 'Bilder/Personen'
                    elif any(obj in ['car', 'bicycle', 'motorcycle'] for obj in objects):
                        return 'Bilder/Fahrzeuge'
                    elif any(obj in ['tree', 'flower', 'plant'] for obj in objects):
                        return 'Bilder/Natur'
            
            if 'analysis' in file and 'aesthetic' in file['analysis']:
                aesthetic_cat = file['analysis']['aesthetic'].get('category', '')
                if aesthetic_cat in self.config['aesthetic_categories']:
                    return f'Bilder/{aesthetic_cat.capitalize()}'
        
        return base_cat
    
    def get_detailed_category(self, file: Dict, base_cat: str) -> str:
        """Sehr detaillierte Kategorisierung"""
        return base_cat
    
    def merge_similar_categories(self, categories: Dict, max_cats: int) -> Dict:
        """Vereint ähnliche Kategorien"""
        sorted_cats = sorted(categories.items(), key=lambda x: len(x[1]), reverse=True)
        merged = {}
        for cat, files in sorted_cats[:max_cats]:
            merged[cat] = files
        if len(sorted_cats) > max_cats:
            if 'Sonstiges' not in merged:
                merged['Sonstiges'] = []
            for cat, files in sorted_cats[max_cats:]:
                merged['Sonstiges'].extend(files)
        return merged
    
    def show_duplicate_details(self, duplicate_groups: List[List[Dict]]):
        """Zeigt Details der Duplikate"""
        print("\n" + "="*60)
        print("🔍 DUPLIKAT-DETAILS")
        print("="*60)
        
        for i, group in enumerate(duplicate_groups[:5], 1):
            print(f"\nGruppe {i} ({len(group)} Dateien):")
            for file in group:
                size_mb = file['size_bytes'] / 1024 / 1024
                modified = file['modified'][:10]
                print(f"  • {file['filename']} ({size_mb:.1f} MB, {modified})")
        
        if len(duplicate_groups) > 5:
            print(f"\n... und {len(duplicate_groups) - 5} weitere Gruppen")
    
    def show_analysis_summary(self, analysis: Dict):
        """Zeigt Zusammenfassung der Analyse"""
        print("\n" + "="*60)
        print("📊 ANALYSE-ZUSAMMENFASSUNG")
        print("="*60)
        
        print(f"\nDateien gesamt: {analysis['stats']['total_files']}")
        print(f"Verarbeitet: {analysis['stats']['processed']}")
        print(f"Ästhetisch interessant: {analysis['stats']['aesthetic_files']}")
        print(f"Duplikate gefunden: {analysis['stats']['duplicates_found']}")
        
        if 'groq_categories' in analysis:
            print(f"\n🤖 Groq Kategorien: {len(analysis['groq_categories'])}")
        else:
            print(f"\n📁 Lokale Kategorien: {len(analysis.get('local_categories', {}))}")
        
        print("\n📁 Kategorien-Struktur:")
        categories = analysis.get('groq_categories', [])
        if categories:
            for cat in categories[:10]:
                print(f"  📁 {cat.get('name', 'Unbekannt')}: {cat.get('file_count', 0)} Dateien")
        else:
            local_cats = analysis.get('local_categories', {})
            for category, files in list(local_cats.items())[:10]:
                print(f"  📁 {category}: {len(files)} Dateien")
    
    def organize_files(self, analysis: Dict) -> bool:
        """Organisiert Dateien basierend auf Analyse"""
        print("\n📦 Organisiere Dateien...")
        
        # Verwende Groq-Kategorien falls verfügbar, sonst lokale
        if 'groq_assignments' in analysis and analysis['groq_assignments']:
            return self.organize_with_groq_categories(analysis)
        else:
            return self.organize_with_local_categories(analysis)
    
    def organize_with_groq_categories(self, analysis: Dict) -> bool:
        """Organisiert mit Groq-Kategorien"""
        assignments = analysis['groq_assignments']
        file_map = {f['filename']: f for f in analysis['files']}
        
        moved_count = 0
        for assignment in assignments:
            filename = assignment['filename']
            category = assignment['suggested_category']
            
            if filename not in file_map:
                continue
            
            file_info = file_map[filename]
            source_path = Path(file_info['path'])
            
            target_dir = self.config['output_dir'] / self.clean_category_name(category)
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Dateiname bestimmen
            if self.config['rename_files']:
                if 'groq_renaming' in analysis and filename in analysis['groq_renaming']:
                    new_name = analysis['groq_renaming'][filename]
                else:
                    new_name = self.filename_generator.generate_filename(file_info, category)
            else:
                new_name = source_path.name
            
            target_path = target_dir / new_name
            
            # Sicherheitscheck
            if target_path.exists():
                counter = 1
                while target_path.exists():
                    name_parts = new_name.rsplit('.', 1)
                    if len(name_parts) == 2:
                        target_path = target_dir / f"{name_parts[0]}_{counter}.{name_parts[1]}"
                    else:
                        target_path = target_dir / f"{new_name}_{counter}"
                    counter += 1
            
            try:
                # Prüfe ob Quelldatei existiert
                if not source_path.exists():
                    print(f"  ⚠️ Datei nicht gefunden: {source_path.name}")
                    self.stats['errors'] += 1
                    continue
                
                if self.config['preview_before_move']:
                    print(f"  📄 {source_path.name} → {target_path.name}")
                shutil.move(str(source_path), str(target_path))
                moved_count += 1
            except PermissionError as e:
                print(f"  ✗ Berechtigungsfehler bei {source_path.name}: {e}")
                self.stats['errors'] += 1
            except FileNotFoundError as e:
                print(f"  ✗ Datei nicht gefunden: {source_path.name}")
                self.stats['errors'] += 1
            except Exception as e:
                print(f"  ✗ Fehler bei {source_path.name}: {e}")
                self.stats['errors'] += 1
        
        self.stats['organized'] = moved_count
        return True
    
    def organize_with_local_categories(self, analysis: Dict) -> bool:
        """Organisiert mit lokalen Kategorien"""
        categories = analysis.get('local_categories', analysis.get('categories', {}))
        
        if self.config['interactive']:
            print(f"\nGefundene Kategorien ({len(categories)}):")
            for cat, files in categories.items():
                print(f"  📁 {cat}: {len(files)} Dateien")
            
            proceed = input("\n📋 Mit Organisation fortfahren? (ja/nein/details): ").lower()
            if proceed == 'nein':
                return False
            elif proceed == 'details':
                self.show_organization_details(analysis)
                proceed = input("\n📋 Trotzdem fortfahren? (ja/nein): ").lower()
                if proceed != 'ja':
                    return False
        
        moved_count = 0
        for category, files in categories.items():
            target_dir = self.config['output_dir'] / self.clean_category_name(category)
            target_dir.mkdir(parents=True, exist_ok=True)
            
            for file_info in files:
                source_path = Path(file_info['path'])
                
                if self.config['rename_files']:
                    new_name = self.filename_generator.generate_filename(file_info, category)
                else:
                    new_name = source_path.name
                
                target_path = target_dir / new_name
                
                if target_path.exists():
                    counter = 1
                    while target_path.exists():
                        name_parts = new_name.rsplit('.', 1)
                        if len(name_parts) == 2:
                            target_path = target_dir / f"{name_parts[0]}_{counter}.{name_parts[1]}"
                        else:
                            target_path = target_dir / f"{new_name}_{counter}"
                        counter += 1
                
                try:
                    # Prüfe ob Quelldatei existiert
                    if not source_path.exists():
                        print(f"  ⚠️ Datei nicht gefunden: {source_path.name}")
                        self.stats['errors'] += 1
                        continue
                    
                    if self.config['preview_before_move']:
                        print(f"  📄 {source_path.name} → {target_path.name}")
                    shutil.move(str(source_path), str(target_path))
                    moved_count += 1
                except PermissionError as e:
                    print(f"  ✗ Berechtigungsfehler bei {source_path.name}: {e}")
                    self.stats['errors'] += 1
                except FileNotFoundError as e:
                    print(f"  ✗ Datei nicht gefunden: {source_path.name}")
                    self.stats['errors'] += 1
                except Exception as e:
                    print(f"  ✗ Fehler bei {source_path.name}: {e}")
                    self.stats['errors'] += 1
        
        self.stats['organized'] = moved_count
        return True
    
    def clean_category_name(self, name: str) -> str:
        """Bereinigt Kategorienamen für Dateisystem"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')
        while '__' in name:
            name = name.replace('__', '_')
        return name.strip('_')
    
    def show_organization_details(self, analysis: Dict):
        """Zeigt detaillierte Organisationsinformationen"""
        print("\n" + "="*60)
        print("📊 ORGANISATIONS-DETAILS")
        print("="*60)
        
        print(f"\nDateien gesamt: {analysis['stats']['total_files']}")
        print(f"Davon ästhetisch interessant: {analysis['stats']['aesthetic_files']}")
        print(f"Duplikate gefunden: {analysis['stats']['duplicates_found']}")
        
        print("\n📁 Kategorien-Struktur:")
        categories = analysis.get('local_categories', analysis.get('categories', {}))
        for category, files in list(categories.items())[:10]:
            print(f"\n  {category}:")
            for file in files[:3]:
                print(f"    • {file['filename']}")
            if len(files) > 3:
                print(f"    ... und {len(files) - 3} weitere")
    
    def save_report(self, analysis: Dict):
        """Speichert detaillierten Bericht"""
        report_path = self.config['output_dir'] / 'organizer_report.json'
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'config': self.config,
            'stats': self.stats,
            'categories_summary': {},
            'aesthetic_files': [f['filename'] for f in analysis.get('aesthetic_files', [])],
            'duplicates_found': analysis['stats']['duplicates_found']
        }
        
        if 'groq_categories' in analysis:
            report['groq_categories'] = analysis['groq_categories']
            report['categories_summary'] = {cat['name']: cat['file_count'] for cat in analysis['groq_categories']}
        else:
            local_cats = analysis.get('local_categories', analysis.get('categories', {}))
            report['categories_summary'] = {cat: len(files) for cat, files in local_cats.items()}
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📝 Detaillierter Bericht gespeichert: {report_path}")

@click.command()
@click.option('--input', '-i', help='Eingabeverzeichnis')
@click.option('--output', '-o', help='Ausgabeverzeichnis')
@click.option('--config', '-c', default='config.json', help='Konfigurationsdatei')
@click.option('--groq-key', help='Groq API Key (optional)')
@click.option('--granularity', '-g', type=click.Choice(['wenig', 'mittel', 'viel', 'auto']))
@click.option('--use-groq/--no-groq', default=True, help='Groq AI verwenden')
def main(input, output, config, groq_key, granularity, use_groq):
    """Datei-Organizer mit Groq AI Integration"""
    
    # Konfiguration laden
    config_path = Path(config) if config else None
    
    # Overrides
    overrides = {}
    if input:
        overrides['input_dir'] = str(Path(input))
    if output:
        overrides['output_dir'] = str(Path(output))
    if granularity:
        overrides['category_granularity'] = granularity
    if groq_key:
        if 'ai' not in overrides:
            overrides['ai'] = {}
        overrides['ai']['groq_api_key'] = groq_key
    if not use_groq:
        if 'ai' not in overrides:
            overrides['ai'] = {}
        overrides['ai']['use_groq_for_categorization'] = False
        overrides['ai']['use_groq_for_renaming'] = False
    
    # Temporäre Konfig erstellen
    import tempfile
    temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    json.dump(overrides, temp_config)
    temp_config.close()
    
    try:
        organizer = EnhancedFileOrganizer(Path(temp_config.name))
        organizer.run()
    finally:
        Path(temp_config.name).unlink(missing_ok=True)

if __name__ == '__main__':
    main()
