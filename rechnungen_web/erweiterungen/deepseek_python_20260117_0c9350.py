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
            'stats': self.stats.copy()
        }
    
    # ... (restliche Methoden bleiben wie zuvor) ...

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
        overrides['input_dir'] = Path(input)
    if output:
        overrides['output_dir'] = Path(output)
    if granularity:
        overrides['category_granularity'] = granularity
    if groq_key:
        overrides['ai'] = {'groq_api_key': groq_key}
    if not use_groq:
        overrides['ai'] = {'use_groq_for_categorization': False, 'use_groq_for_renaming': False}
    
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