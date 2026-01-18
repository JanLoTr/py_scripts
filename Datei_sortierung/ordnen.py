import json
import shutil
from pathlib import Path
import time

INPUT_JSON = "ki_antwort.json"
BASE_DIR = r"C:\Users\jan\Downloads\WA2"
TARGET_BASE = r"C:\Users\jan\Downloads\WA2_SORTIERT"

class FileOrganizer:
    def __init__(self):
        self.stats = {
            'total': 0,
            'moved': 0,
            'not_found': 0,
            'errors': 0,
            'categories': {}
        }
        self.start_time = time.time()
    
    def organize_files(self):
        try:
            with open(INPUT_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)["results"]
            
            self.stats['total'] = len(data)
            
            print(f"Starte Sortierung von {self.stats['total']} Dateien...")
            print("-" * 50)
            
            for item in data:
                filename = item["filename"]
                category = item["category"].replace("/", "-")
                
                # Kategorie-Statistik aktualisieren
                if category not in self.stats['categories']:
                    self.stats['categories'][category] = 0
                
                source = Path(BASE_DIR) / filename
                target_dir = Path(TARGET_BASE) / category
                
                try:
                    if source.exists():
                        target_dir.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(source), str(target_dir / filename))
                        
                        self.stats['moved'] += 1
                        self.stats['categories'][category] += 1
                        print(f"✓ {filename:40} → {category:20}")
                    else:
                        print(f"✗ {filename:40} → NICHT GEFUNDEN")
                        self.stats['not_found'] += 1
                        
                except Exception as e:
                    print(f"✗ {filename:40} → FEHLER: {str(e)}")
                    self.stats['errors'] += 1
            
            return True
            
        except Exception as e:
            print(f"\nFEHLER beim Laden der JSON-Datei: {e}")
            return False
    
    def print_summary(self):
        elapsed_time = time.time() - self.start_time
        
        print("\n" + "="*60)
        print("SORTIERSTATISTIK")
        print("="*60)
        print(f"{'Einsortierte Dateien:':30} {self.stats['moved']:>4}")
        print(f"{'Nicht gefundene Dateien:':30} {self.stats['not_found']:>4}")
        print(f"{'Fehler:':30} {self.stats['errors']:>4}")
        print(f"{'Gesamt verarbeitet:':30} {self.stats['total']:>4}")
        print("-"*60)
        
        if self.stats['categories']:
            print("\nDateien pro Kategorie:")
            print("-"*30)
            for category, count in sorted(self.stats['categories'].items()):
                if count > 0:
                    print(f"{category:25}: {count:>4}")
        
        print("="*60)
        print(f"\nDauer: {elapsed_time:.2f} Sekunden")
        
        if self.stats['moved'] > 0:
            print(f"✓ Erfolgreich abgeschlossen! {self.stats['moved']} Dateien wurden sortiert.")
        else:
            print("⚠ Keine Dateien wurden einsortiert.")

def main():
    organizer = FileOrganizer()
    
    if organizer.organize_files():
        organizer.print_summary()
    
    # Optional: Ergebnis in Datei speichern
    log_file = Path(TARGET_BASE) / "sortier_log.txt"
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"Sortierung abgeschlossen am {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Einsortierte Dateien: {organizer.stats['moved']}\n")
        f.write(f"Nicht gefundene Dateien: {organizer.stats['not_found']}\n")

if __name__ == "__main__":
    main()