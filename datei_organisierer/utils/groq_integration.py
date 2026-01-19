"""
Groq API Integration für intelligente Dateianalyse
"""

import json
import time
from typing import Dict, List, Optional, Any
from pathlib import Path
import hashlib
import base64
from groq import Groq

class GroqAnalyzer:
    def __init__(self, config: Dict):
        self.full_config = config  # Vollständige Config für Zugriff auf alle Werte
        self.config = config.get('ai', {})
        self.api_key = self.config.get('groq_api_key')
        self.model = self.config.get('groq_model', 'mixtral-8x7b-32768')
        self.max_tokens = self.config.get('max_tokens', 1000)
        self.temperature = self.config.get('temperature', 0.3)
        
        self.client = None
        if self.api_key and self.config.get('provider') == 'groq':
            try:
                self.client = Groq(api_key=self.api_key)
                print(f"✅ Groq API initialisiert mit Modell: {self.model}")
            except Exception as e:
                print(f"⚠️ Groq API konnte nicht initialisiert werden: {e}")
                self.client = None
    
    def is_available(self) -> bool:
        """Prüft ob Groq API verfügbar ist"""
        return self.client is not None
    
    def analyze_files_with_groq(self, files: List[Dict]) -> Dict[str, Any]:
        """
        Analysiert Dateien mit Groq API für intelligente Kategorisierung
        """
        if not self.is_available():
            return {"error": "Groq API nicht verfügbar", "categories": {}}
        
        print("🤖 Analysiere Dateien mit Groq AI...")
        
        try:
            # Erstelle optimierte Prompt
            prompt = self.create_analysis_prompt(files)
            
            # Sende Anfrage an Groq
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"}
            )
            
            # Parse Antwort
            content = response.choices[0].message.content
            if not content:
                return {"error": "Leere Antwort von Groq API", "categories": {}}
            
            try:
                result = json.loads(content)
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON-Parse-Fehler: {e}")
                print(f"   Antwort war: {content[:200]}...")
                return {"error": f"Ungültiges JSON von Groq API: {e}", "categories": {}}
            
            # Validiere und bereinige Ergebnis
            validated_result = self.validate_and_clean_result(result, files)
            
            return validated_result
            
        except Exception as e:
            print(f"⚠️ Groq API Fehler: {e}")
            import traceback
            print(f"   Details: {traceback.format_exc()}")
            return {"error": str(e), "categories": {}}
    
    def create_analysis_prompt(self, files: List[Dict]) -> str:
        """Erstellt Prompt für Groq API"""
        # Reduziere auf repräsentative Stichprobe (max 50 Dateien für Prompt)
        sample_files = files[:50] if len(files) > 50 else files
        
        # Vereinfache Daten für Prompt
        simplified_files = []
        for file in sample_files:
            simplified = {
                "filename": file.get("filename", ""),
                "extension": file.get("extension", ""),
                "size_kb": file.get("size_bytes", 0) / 1024,
                "content_preview": file.get("content_preview", "")[:500],
                "image_analysis": file.get("analysis", {}).get("image", {}).get("description", "") if "image" in file.get("analysis", {}) else "",
                "aesthetic_score": file.get("analysis", {}).get("aesthetic", {}).get("score", 0) if "aesthetic" in file.get("analysis", {}) else 0
            }
            simplified_files.append(simplified)
        
        # Granularität aus vollständiger Config
        granularity = self.full_config.get('category_granularity', 'mittel')
        max_categories = {
            'wenig': 5,
            'mittel': 15,
            'viel': 30
        }.get(granularity, 15)
        
        prompt = f"""
        ANALYSEAUFGABE: Dateien intelligent kategorisieren

        KONTEXT:
        - Insgesamt {len(files)} Dateien im Ordner
        - Zeige hier {len(simplified_files)} repräsentative Dateien
        - Gewünschte Granularität: {granularity} (ca. {max_categories} Kategorien)
        
        REGELN für Kategorien:
        1. Sei PRÄZISE und PRAKTISCH
        2. Verwende DEUTSCHE Kategorienamen
        3. Kategorienamen: maximal 2-3 Wörter
        4. KEINE generischen Namen wie "Dokumente" oder "Bilder"
        5. Berücksichtige ÄSTHETISCHE Dateien (Score > 0.7) extra
        
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
              "example_files": ["datei1.jpg", "datei2.pdf"]
            }}
          ],
          "file_assignments": [
            {{
              "filename": "datei1.jpg",
              "suggested_category": "Reisefotos/Italien",
              "confidence": 0.92,
              "reason": "Bild zeigt Kolosseum in Rom bei Sonnenuntergang"
            }}
          ],
          "aesthetic_collection": {{
            "name": "Inspiration & Schönes",
            "files": ["bild1.jpg", "bild2.png"],
            "reason": "Hoher ästhetischer Score und harmonische Farben"
          }}
        }}
        """
        
        return prompt
    
    def get_system_prompt(self) -> str:
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
        
        WICHTIG bei Kategorien:
        - Erfinde sinnvolle, spezifische Kategorienamen
        - Gruppiere zusammengehörige Dateien (Projekte!)
        - Ästhetisch schöne Dateien extra kennzeichnen
        - Dateien mit ähnlichem Stil zusammenfassen
        
        Beispiele für gute Kategorien:
        - "Reisefotos/Italien 2023" (statt "Bilder")
        - "Python/Datenanalyse" (statt "Code")
        - "Verträge & Vereinbarungen" (statt "Dokumente")
        - "Inspiration/Design-Vorlagen" (für ästhetische Dateien)
        
        Antworte IMMER im geforderten JSON-Format.
        """
    
    def validate_and_clean_result(self, result: Dict, files: List[Dict]) -> Dict:
        """Validiert und bereinigt das Groq-Ergebnis"""
        # Stelle sicher, dass result ein Dictionary ist
        if not isinstance(result, dict):
            result = {}
        
        # Stelle sicher, dass categories eine Liste ist
        if "categories" not in result or not isinstance(result["categories"], list):
            result["categories"] = []
        
        # Stelle sicher, dass file_assignments eine Liste ist
        if "file_assignments" not in result or not isinstance(result["file_assignments"], list):
            result["file_assignments"] = []
        
        # Stelle sicher, dass alle Dateien zugeordnet werden
        if result["file_assignments"]:
            assigned_files = {a.get("filename", "") for a in result["file_assignments"] if isinstance(a, dict)}
            all_files = {f.get("filename", "") for f in files if isinstance(f, dict)}
            
            # Fehlende Dateien hinzufügen
            missing_files = all_files - assigned_files
            if missing_files:
                for filename in missing_files:
                    result["file_assignments"].append({
                        "filename": filename,
                        "suggested_category": "Unsortiert/Verschiedenes",
                        "confidence": 0.5,
                        "reason": "Automatisch zugeordnet"
                    })
        
        return result
    
    def describe_image_with_groq(self, image_path: Path, analysis: Dict) -> str:
        """
        Beschreibt ein Bild mit Groq API (besser als lokale Analyse)
        Nur wenn use_groq_for_images = True
        """
        if not self.is_available() or not self.config.get('use_groq_for_images', False):
            return analysis.get('description', 'Bild')
        
        try:
            # Bild für Prompt codieren (Base64)
            import base64
            with open(image_path, 'rb') as img_file:
                img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
            
            prompt = f"""
            Beschreibe dieses Bild für einen Dateinamen:
            
            Bildanalyse-Daten:
            - Hauptobjekte: {analysis.get('objects', [])[:5]}
            - Dominante Farben: {[c.get('name', '') for c in analysis.get('dominant_colors', [])[:3]]}
            - Helligkeit: {'hell' if analysis.get('brightness', 0.5) > 0.7 else 'dunkel' if analysis.get('brightness', 0.5) < 0.3 else 'mittel'}
            - Stimmung: {'fröhlich' if analysis.get('colors', {}).get('gelb', 0) > 20 else 'ruhig' if analysis.get('colors', {}).get('blau', 0) > 20 else 'neutral'}
            
            Erwartetes Format: 3-5 Stichworte mit Unterstrichen, z.B.:
            sonnenuntergang_meer_strand_abend
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Du beschreibst Bilder für Dateinamen. Maximal 5 Stichworte, durch Unterstriche getrennt."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=50
            )
            
            description = response.choices[0].message.content.strip()
            # Bereinige die Antwort
            description = description.replace('.', '').replace(',', '').lower()
            description = '_'.join(description.split())
            
            return description if len(description) > 5 else analysis.get('description', 'bild')
            
        except Exception as e:
            print(f"⚠️ Groq Bildbeschreibung fehlgeschlagen: {e}")
            return analysis.get('description', 'bild')
    
    def suggest_renaming(self, files: List[Dict]) -> Dict[str, str]:
        """
        Schlägt intelligente Umbenennung für Dateien vor
        """
        if not self.is_available():
            return {}
        
        try:
            prompt = self.create_renaming_prompt(files)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Du schlägst beschreibende Dateinamen vor. Format: 'beschreibung_originalname.ext' oder komplett neuer Name."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            suggestions = json.loads(response.choices[0].message.content)
            return suggestions.get("renaming_suggestions", {})
            
        except Exception as e:
            print(f"⚠️ Groq Umbenennungsvorschläge fehlgeschlagen: {e}")
            return {}
    
    def create_renaming_prompt(self, files: List[Dict]) -> str:
        """Erstellt Prompt für Umbenennungsvorschläge"""
        sample_files = files[:30]  # Begrenze für Prompt
        
        file_list = []
        for file in sample_files:
            file_list.append({
                "current_name": file["filename"],
                "type": file["extension"],
                "content_hint": file.get("content_preview", "")[:200],
                "image_description": file.get("analysis", {}).get("image", {}).get("description", "") if "image" in file.get("analysis", {}) else ""
            })
        
        return f"""
        Vorschläge für beschreibende Dateinamen:
        
        REGELN:
        1. Dateinamen sollen INHALT beschreiben
        2. Deutsche Wörter verwenden
        3. Keine Sonderzeichen außer Unterstrichen und Bindestrichen
        4. Nicht zu lang (max 50 Zeichen)
        5. Bei Bildern: Hauptobjekte + Stimmung
        6. Bei Dokumenten: Thema + Datum
        
        BEISPIELE:
        - Aus "IMG_1234.jpg" → "sonnenuntergang_berge_20240115.jpg"
        - Aus "scan.pdf" → "mietvertrag_wohnung_berlin_2023.pdf"
        - Aus "data.csv" → "umsatzdaten_q1_2024.csv"
        
        DATEIEN:
        {json.dumps(file_list, indent=2, ensure_ascii=False)}
        
        ANTWORTFORMAT:
        {{
          "renaming_suggestions": {{
            "alter_dateiname.ext": "neuer_dateiname.ext",
            "IMG_1234.jpg": "sonnenuntergang_alpen_20240115.jpg"
          }}
        }}
        """