#!/usr/bin/env python3
"""
Erweiterter Datei-Organizer mit allen Funktionen:
- Kategoriengranularität (wenig/mittel/viel)
- Duplikaterkennung und -behandlung
- Intelligente Umbenennung
- Ästhetik-Erkennung
- Lokale Bildanalyse ohne API-Kosten
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

class EnhancedFileOrganizer:
    def __init__(self, config_path: Optional[Path] = None):
        self.config = self.load_config(config_path)
        self.image_analyzer = ImageAnalyzer(self.config)
        self.duplicate_detector = DuplicateDetector(self.config)
        self.filename_generator = FilenameGenerator(self.config)
        self.aesthetic_scorer = AestheticScorer(self.config)
        
        self.stats = {
            'total_files': 0,
            'processed': 0,
            'organized': 0,
            'renamed': 0,
            'duplicates_found': 0,
            'duplicates_handled': 0,
            'aesthetic_files': 0,
            'errors': 0
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
            'image_analysis': {'use_yolo': True, 'describe_scene': True}
        }
        
        if config_path and config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                defaults.update(user_config)
        
        # Pfade konvertieren
        defaults['input_dir'] = Path(defaults['input_dir'])
        defaults['output_dir'] = Path(defaults['output_dir'])
        
        return defaults
    
    def ask_category_granularity(self) -> str:
        """Fragt nach der gewünschten Kategoriengranularität"""
        print("\n" + "="*60)
        print("📊 KATEGORIEN-GRANULARITÄT")
        print("="*60)
        print("Wie detailliert sollen Kategorien sein?")
        print("1. Wenig (ca. 5 Hauptkategorien)")
        print("2. Mittel (ca. 15 Kategorien)")
        print("3. Viel (ca. 30 spezifische Kategorien)")
        print("4. Automatisch bestimmen lassen")
        
        while True:
            choice = input("\nDeine Wahl (1-4): ").strip()
            if choice == '1':
                return 'wenig'
            elif choice == '2':
                return 'mittel'
            elif choice == '3':
                return 'viel'
            elif choice == '4':
                return 'auto'
            else:
                print("❌ Ungültige Eingabe. Bitte 1-4 wählen.")
    
    def analyze_files(self) -> Dict[str, Any]:
        """Analysiert alle Dateien mit erweiterten Funktionen"""
        print("🔍 Analysiere Dateien...")
        
        all_files = []
        for ext in self.config['supported_extensions']:
            all_files.extend(self.config['input_dir'].rglob(f"*{ext}"))
        
        self.stats['total_files'] = len(all_files)
        
        results = []
        with click.progressbar(all_files, label='Dateien analysieren') as files:
            for file_path in files:
                try:
                    file_info = self.analyze_single_file(file_path)
                    results.append(file_info)
                    self.stats['processed'] += 1
                except Exception as e:
                    print(f"\n⚠️ Fehler bei {file_path.name}: {e}")
                    self.stats['errors'] += 1
        
        # Duplikate finden
        print("\n🔍 Suche nach Duplikaten...")
        duplicate_groups = self.duplicate_detector.find_duplicates(results)
        self.stats['duplicates_found'] = sum(len(group) for group in duplicate_groups)
        
        # Duplikate behandeln
        if duplicate_groups and self.config['interactive']:
            duplicate_groups = self.handle_duplicates_interactive(duplicate_groups)
        
        # Ästhetische Dateien erkennen
        if self.config['detect_aesthetic_files']:
            print("\n🎨 Analysiere auf ästhetische Dateien...")
            aesthetic_files = self.aesthetic_scorer.find_aesthetic_files(results)
            self.stats['aesthetic_files'] = len(aesthetic_files)
        
        # Kategorien vorschlagen
        categories = self.suggest_categories(results)
        
        return {
            'files': results,
            'duplicates': duplicate_groups,
            'aesthetic_files': aesthetic_files if 'aesthetic_files' in locals() else [],
            'categories': categories,
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
                    # Behalte neueste Datei
                    newest = max(group, key=lambda x: x.get('modified', ''))
                    filtered_groups.append([newest])
                else:  # largest
                    largest = max(group, key=lambda x: x.get('size_bytes', 0))
                    filtered_groups.append([largest])
            return filtered_groups
        elif choice == '4':
            return self.manual_duplicate_selection(duplicate_groups)
        elif choice == '5':
            self.show_duplicate_details(duplicate_groups)
            return self.handle_duplicates_interactive(duplicate_groups)
        
        return duplicate_groups
    
    def suggest_categories(self, files: List[Dict]) -> Dict:
        """Schlägt Kategorien basierend auf Granularität vor"""
        granularity = self.config['category_granularity']
        if granularity == 'auto':
            # Automatisch basierend auf Dateianzahl bestimmen
            if len(files) < 50:
                granularity = 'wenig'
            elif len(files) < 200:
                granularity = 'mittel'
            else:
                granularity = 'viel'
        
        max_cats = self.config['max_categories'][granularity]
        
        # Einfache kategorisierung basierend auf Dateityp und Inhalt
        categories = {}
        
        for file in files:
            # Bestimme Basiskategorie
            cat = self.get_base_category(file)
            
            # Verfeinere basierend auf Granularität
            if granularity == 'viel':
                cat = self.get_detailed_category(file, cat)
            elif granularity == 'mittel':
                cat = self.get_medium_category(file, cat)
            # Bei 'wenig' bleibt die Basiskategorie
            
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(file)
        
        # Begrenze Anzahl der Kategorien
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
            # Analysiere Bildinhalt für genauere Kategorie
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
            
            # Ästhetik-basierte Kategorien
            if 'analysis' in file and 'aesthetic' in file['analysis']:
                aesthetic_cat = file['analysis']['aesthetic'].get('category', '')
                if aesthetic_cat in self.config['aesthetic_categories']:
                    return f'Bilder/{aesthetic_cat.capitalize()}'
        
        return base_cat
    
    def get_detailed_category(self, file: Dict, base_cat: str) -> str:
        """Sehr detaillierte Kategorisierung"""
        # Hier könnten komplexere Regeln oder lokale KI verwendet werden
        return base_cat
    
    def merge_similar_categories(self, categories: Dict, max_cats: int) -> Dict:
        """Vereint ähnliche Kategorien"""
        # Einfache Implementierung: Behalte die größten Kategorien
        sorted_cats = sorted(categories.items(), key=lambda x: len(x[1]), reverse=True)
        merged = {}
        for cat, files in sorted_cats[:max_cats]:
            merged[cat] = files
        # Rest in "Sonstiges"
        if len(sorted_cats) > max_cats:
            if 'Sonstiges' not in merged:
                merged['Sonstiges'] = []
            for cat, files in sorted_cats[max_cats:]:
                merged['Sonstiges'].extend(files)
        return merged
    
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
    
    def organize_files(self, analysis: Dict) -> bool:
        """Organisiert Dateien basierend auf Analyse"""
        print("\n📦 Organisiere Dateien...")
        
        # Frage nach Bestätigung
        if self.config['interactive']:
            print(f"\nGefundene Kategorien ({len(analysis['categories'])}):")
            for cat, files in analysis['categories'].items():
                print(f"  📁 {cat}: {len(files)} Dateien")
            
            proceed = input("\n📋 Mit Organisation fortfahren? (ja/nein/details): ").lower()
            if proceed == 'nein':
                return False
            elif proceed == 'details':
                self.show_organization_details(analysis)
                proceed = input("\n📋 Trotzdem fortfahren? (ja/nein): ").lower()
                if proceed != 'ja':
                    return False
        
        # Dateien organisieren
        moved_count = 0
        for category, files in analysis['categories'].items():
            target_dir = self.config['output_dir'] / self.clean_category_name(category)
            target_dir.mkdir(parents=True, exist_ok=True)
            
            for file_info in files:
                source_path = Path(file_info['path'])
                
                # Ziel-Dateiname bestimmen
                if self.config['rename_files']:
                    new_name = self.generate_new_filename(file_info, category)
                else:
                    new_name = source_path.name
                
                target_path = target_dir / new_name
                
                # Sicherheitscheck
                if target_path.exists():
                    # Erstelle eindeutigen Namen
                    counter = 1
                    while target_path.exists():
                        name_parts = new_name.rsplit('.', 1)
                        if len(name_parts) == 2:
                            target_path = target_dir / f"{name_parts[0]}_{counter}.{name_parts[1]}"
                        else:
                            target_path = target_dir / f"{new_name}_{counter}"
                        counter += 1
                
                try:
                    # Vorschau anzeigen
                    if self.config['preview_before_move']:
                        print(f"  📄 {source_path.name} → {target_path.name}")
                    
                    # Datei verschieben
                    shutil.move(str(source_path), str(target_path))
                    moved_count += 1
                    
                except Exception as e:
                    print(f"  ✗ Fehler bei {source_path.name}: {e}")
                    self.stats['errors'] += 1
        
        self.stats['organized'] = moved_count
        return True
    
    def generate_new_filename(self, file_info: Dict, category: str) -> str:
        """Generiert neuen, beschreibenden Dateinamen"""
        original_name = Path(file_info['filename']).stem
        ext = file_info['extension']
        
        if self.config['naming_scheme'] == 'descriptive':
            if 'suggested_name' in file_info:
                return file_info['suggested_name']
            
            # Versuche, aus Inhalt zu generieren
            description = self.generate_description(file_info)
            clean_desc = self.clean_string_for_filename(description)
            
            # Kürze wenn nötig
            if len(clean_desc) > 50:
                clean_desc = clean_desc[:50]
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"{clean_desc}_{timestamp}{ext}"
        
        elif self.config['naming_scheme'] == 'timestamp':
            timestamp = datetime.fromisoformat(file_info['modified']).strftime("%Y%m%d_%H%M%S")
            return f"{timestamp}_{original_name}{ext}"
        
        else:  # original_descriptive
            timestamp = datetime.now().strftime("%Y%m%d")
            return f"{timestamp}_{original_name}{ext}"
    
    def generate_description(self, file_info: Dict) -> str:
        """Generiert Beschreibung aus Dateiinhalt"""
        ext = file_info['extension']
        
        if ext in ['.jpg', '.jpeg', '.png']:
            if 'analysis' in file_info and 'image' in file_info['analysis']:
                img_info = file_info['analysis']['image']
                if 'description' in img_info:
                    return img_info['description']
                elif 'objects' in img_info:
                    return f"Bild_mit_{'_'.join(img_info['objects'][:3])}"
        
        # Für Textdateien: Extrahiere Schlüsselwörter
        preview = file_info.get('content_preview', '')
        if preview and len(preview) > 50:
            # Einfache Schlüsselwort-Extraktion
            words = preview.split()[:10]
            return '_'.join(words[:5])
        
        return file_info['filename']
    
    def clean_category_name(self, name: str) -> str:
        """Bereinigt Kategorienamen für Dateisystem"""
        # Ersetze ungültige Zeichen
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')
        
        # Entferne doppelte Unterstriche
        while '__' in name:
            name = name.replace('__', '_')
        
        return name.strip('_')
    
    def clean_string_for_filename(self, text: str) -> str:
        """Bereinigt String für Dateinamen"""
        # Entferne Sonderzeichen
        import re
        text = re.sub(r'[^\w\s-]', '', text)
        # Ersetze Leerzeichen mit Unterstrichen
        text = text.replace(' ', '_')
        # Mehrfache Unterstriche entfernen
        text = re.sub(r'_+', '_', text)
        return text.strip('_').lower()
    
    def show_duplicate_details(self, duplicate_groups: List[List[Dict]]):
        """Zeigt Details der Duplikate"""
        print("\n" + "="*60)
        print("🔍 DUPLIKAT-DETAILS")
        print("="*60)
        
        for i, group in enumerate(duplicate_groups[:5], 1):  # Zeige nur erste 5 Gruppen
            print(f"\nGruppe {i} ({len(group)} Dateien):")
            for file in group:
                size_mb = file['size_bytes'] / 1024 / 1024
                modified = file['modified'][:10]
                print(f"  • {file['filename']} ({size_mb:.1f} MB, {modified})")
        
        if len(duplicate_groups) > 5:
            print(f"\n... und {len(duplicate_groups) - 5} weitere Gruppen")
    
    def show_organization_details(self, analysis: Dict):
        """Zeigt detaillierte Organisationsinformationen"""
        print("\n" + "="*60)
        print("📊 ORGANISATIONS-DETAILS")
        print("="*60)
        
        print(f"\nDateien gesamt: {analysis['stats']['total_files']}")
        print(f"Davon ästhetisch interessant: {analysis['stats']['aesthetic_files']}")
        print(f"Duplikate gefunden: {analysis['stats']['duplicates_found']}")
        
        print("\n📁 Kategorien-Struktur:")
        for category, files in analysis['categories'].items():
            print(f"\n  {category}:")
            for file in files[:3]:  # Zeige nur erste 3 Dateien pro Kategorie
                print(f"    • {file['filename']}")
            if len(files) > 3:
                print(f"    ... und {len(files) - 3} weitere")
    
    def run(self):
        """Hauptausführung"""
        print("="*60)
        print("🤖 ERWEITERTER DATEI-ORGANIZER")
        print("="*60)
        
        # Granularität fragen
        if self.config['interactive']:
            self.config['category_granularity'] = self.ask_category_granularity()
        
        # Analyse durchführen
        analysis = self.analyze_files()
        
        # Zusammenfassung
        self.show_organization_details(analysis)
        
        # Organisieren (falls gewünscht)
        if self.config['interactive']:
            proceed = input("\n📋 Mit Organisation fortfahren? (ja/nein): ").lower()
            if proceed != 'ja':
                print("❌ Abgebrochen.")
                return
        
        # Ausführen
        success = self.organize_files(analysis)
        
        # Bericht speichern
        self.save_report(analysis)
        
        if success:
            print(f"\n✅ Fertig! {self.stats['organized']} Dateien organisiert.")
        else:
            print("\n⚠️ Organisation abgebrochen.")
    
    def save_report(self, analysis: Dict):
        """Speichert detaillierten Bericht"""
        report_path = self.config['output_dir'] / 'organizer_report.json'
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'config': self.config,
            'stats': self.stats,
            'categories_summary': {cat: len(files) for cat, files in analysis['categories'].items()},
            'aesthetic_files': [f['filename'] for f in analysis.get('aesthetic_files', [])],
            'duplicates_found': analysis['stats']['duplicates_found']
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📝 Detaillierter Bericht gespeichert: {report_path}")

@click.command()
@click.option('--input', '-i', help='Eingabeverzeichnis')
@click.option('--output', '-o', help='Ausgabeverzeichnis')
@click.option('--config', '-c', help='Konfigurationsdatei', default='config.json')
@click.option('--granularity', '-g', type=click.Choice(['wenig', 'mittel', 'viel', 'auto']), 
              help='Kategoriengranularität')
@click.option('--rename/--no-rename', default=True, help='Dateien umbenennen')
@click.option('--interactive/--non-interactive', default=True, help='Interaktiver Modus')
def main(input, output, config, granularity, rename, interactive):
    """Erweiterter Datei-Organizer mit allen Funktionen"""
    
    # Konfiguration laden
    config_path = Path(config) if config else None
    
    # Overrides aus Kommandozeile
    overrides = {}
    if input:
        overrides['input_dir'] = Path(input)
    if output:
        overrides['output_dir'] = Path(output)
    if granularity:
        overrides['category_granularity'] = granularity
    if rename is not None:
        overrides['rename_files'] = rename
    if interactive is not None:
        overrides['interactive'] = interactive
    
    # Temporäre Konfigurationsdatei erstellen
    if overrides:
        import tempfile
        temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        json.dump(overrides, temp_config)
        temp_config.close()
        config_path = Path(temp_config.name)
    
    try:
        organizer = EnhancedFileOrganizer(config_path)
        organizer.run()
    finally:
        # Temporäre Datei löschen
        if 'temp_config' in locals():
            Path(temp_config.name).unlink(missing_ok=True)

if __name__ == '__main__':
    main()
