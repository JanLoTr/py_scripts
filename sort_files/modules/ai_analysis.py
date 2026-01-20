# modules/ai_analysis.py - KI-Analyse mit Groq
import json
import re
from groq import Groq
import streamlit as st

def analyze_with_groq(files_data, api_key, detail_level="mittel"):
    """Analysiert Dateien mit Groq KI - Kategorisiert nach INHALT, nicht nur Dateityp"""
    try:
        client = Groq(api_key=api_key)
        
        # Prompt basierend auf Detaillevel - beeinflusst Anzahl der Ordner
        prompts = {
            "wenig": """
            ERSTELLE WENIGE ORDNER (5-8 Hauptkategorien).
            Gruppiere ähnliche Inhalte zusammen, ignoriere kleine Unterschiede.
            Beispiele: "Dokumente", "Bilder", "Code", "Schule/Arbeit", "Persönliches"
            Sehr breite Kategorien verwenden!
            """,
            
            "mittel": """
            ERSTELLE AUSGEWOGENE ORDNER (10-15 Kategorien).
            Unterscheide nach Hauptthemen, aber nicht zu fein.
            Beispiele: "Finanzen/Rechnungen", "Schule/Mathematik", "Code/Python", 
                       "Urlaubsbilder", "Bewerbungsunterlagen", "Projektdokumente"
            Gute Balance zwischen Übersicht und Genauigkeit.
            """,
            
            "viel": """
            ERSTELLE VIELE SPEZIFISCHE ORDNER (20+ Kategorien).
            Sehr detaillierte Kategorisierung nach exaktem Inhalt.
            Beispiele: "Steuererklärung 2024", "Python/Datenanalyse-Projekt", 
                       "Maturavorbereitung/Mathematik", "Geburtsurkunden", 
                       "Urlaub/Griechenland 2023", "Diplomarbeit/Robotik"
            Sehr spezifische Kategorien verwenden!
            """
        }
        
        prompt = prompts.get(detail_level, prompts["mittel"])
        
        system_prompt = f"""Du bist ein intelligentes Datei-Kategorisierungs-System.

{prompt}

WICHTIGSTE REGEL: KATEGORISIERE NACH INHALT, NICHT NACH DATEITYP!
Analysiere den Dateiinhalt in 'text_preview' und erstelle sinnvolle Kategorien.

ANWEISUNGEN:
1. LIES den Dateiinhalt in 'text_preview' 
2. ERKENNE das Hauptthema (nicht Dateityp!)
3. ERSTELLE sinnvolle Kategorien wie: "Schule/Mathematik-Hausaufgaben", "Arbeit/Projekt-X", "Finanzen/Steuern"
4. KEINE generischen Kategorien wie "PDF-Dateien" oder "Bilder"
5. Format: "Hauptkategorie / Spezifische Kategorie"

BEISPIELE FÜR GUTE KATEGORIEN:
- "Rechnung/Elektrizitätsanbieter" (nicht "PDF")
- "Lebenslauf/Bewerbung" (nicht "Word-Dokument")
- "Python/Web-Scraping" (nicht "Code")
- "Familie/Geburtsurkunde" (nicht "Scan")
- "Auto/Reparaturkosten" (nicht "Rechnung")

BEISPIELE FÜR SCHLECHTE KATEGORIEN:
- "PDF Datei" ❌ (zu generisch)
- "Bild" ❌ (sagt nichts aus)
- "Textdatei" ❌ (uninformativ)
- "Microsoft Word" ❌ (Dateityp, nicht Inhalt)

ANALYSIERE JETZT DIESE DATEIEN NACH IHREM INHALT:

Antworte NUR im JSON Format:
{{
  "results": [
    {{
      "filename": "dateiname.xyz",
      "category": "Hauptkategorie / Spezifische Kategorie",
      "confidence": 0.0-1.0,
      "reason": "kurze Begründung basierend auf Inhalt"
    }}
  ]
}}"""
        
        # Dateien für Prompt vorbereiten
        max_files = 40 if detail_level == "viel" else 60
        files_for_prompt = files_data[:max_files]
        
        # Erstelle detaillierte Dateibeschreibungen mit Inhalt
        file_descriptions = []
        for f in files_for_prompt:
            # Extrahiere Schlüsselwörter aus dem Inhalt
            preview = f["text_preview"]
            
            # Erkenne wichtige Themen (einfache Heuristik)
            themes = []
            preview_lower = preview.lower()
            
            # Schule/Studium
            if any(word in preview_lower for word in ["schule", "studium", "matura", "prüfung", "hausaufgabe", "klausur", "seminar"]):
                themes.append("Schule/Studium")
            
            # Arbeit/Beruf
            if any(word in preview_lower for word in ["arbeit", "beruf", "projekt", "kunde", "auftrag", "geschäft", "firma"]):
                themes.append("Arbeit/Beruf")
            
            # Finanzen
            if any(word in preview_lower for word in ["rechnung", "kosten", "preis", "euro", "€", "steuer", "bank", "konto", "gehalt"]):
                themes.append("Finanzen")
            
            # Code/Programmierung
            if any(word in preview_lower for word in ["python", "java", "code", "programm", "funktion", "variable", "import", "def ", "class "]):
                themes.append("Programmierung")
            
            # Persönlich
            if any(word in preview_lower for word in ["geburt", "familie", "freund", "urlaub", "reise", "hobby", "interesse"]):
                themes.append("Persönliches")
            
            # Gesundheit
            if any(word in preview_lower for word in ["arzt", "krank", "gesund", "medizin", "rezept", "apotheke"]):
                themes.append("Gesundheit")
            
            description = {
                "filename": f["filename"],
                "type": f["extension"],
                "size_kb": f.get("size_kb", 0),
                "content_preview": preview[:500],  # Erste 500 Zeichen des Inhalts
                "detected_themes": themes[:3]  # Max 3 Themen
            }
            file_descriptions.append(description)
        
        user_message = f"Analysiere diese {len(files_data)} Dateien NACH IHREM INHALT:\n"
        user_message += json.dumps({"files": file_descriptions}, ensure_ascii=False, indent=2)
        
        # API Call mit mehr Tokens für detaillierte Analyse
        max_tokens = 4000 if detail_level == "viel" else 3000
        
        response = client.chat.completions.create(
            model="llama3-70b-8192" if detail_level == "viel" else "llama3-8b-8192",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.2,  # Weniger kreativ, mehr konsistent
            max_tokens=max_tokens
        )
        
        content = response.choices[0].message.content.strip()
        
        # JSON extrahieren
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            content = json_match.group()
        
        result = json.loads(content)
        
        # Sicherstellen, dass alle Dateien eine Kategorie haben
        if "results" in result:
            return _ensure_all_files_categorized_by_content(result, files_data, detail_level)
        
    except json.JSONDecodeError as e:
        st.error(f"KI konnte kein gültiges JSON zurückgeben. Antwort war: {content[:500]}")
    except Exception as e:
        st.error(f"KI-Fehler: {str(e)[:200]}")
    
    # Fallback mit verbesserter Inhaltsanalyse
    return create_content_based_fallback_categories(files_data, detail_level)

def _ensure_all_files_categorized_by_content(result, files_data, detail_level):
    """Stellt sicher, dass alle Dateien nach Inhalt kategorisiert sind"""
    processed_filenames = {r["filename"] for r in result["results"]}
    
    # Fehlende Dateien hinzufügen
    for file_data in files_data:
        if file_data["filename"] not in processed_filenames:
            category = _get_category_from_content(file_data, detail_level)
            result["results"].append({
                "filename": file_data["filename"],
                "category": category,
                "confidence": 0.6,
                "reason": "Automatisch aus Dateiinhalt erstellt"
            })
    
    return result

def _get_category_from_content(file_data, detail_level):
    """Bestimmt Kategorie basierend auf DateiINHALT (nicht Dateityp!)"""
    preview = file_data["text_preview"].lower()
    ext = file_data["extension"].lower()
    
    # Analyse des Inhalts
    content_lower = preview.lower()
    
    # Schule/Studium Inhalte
    school_keywords = ["schule", "studium", "matura", "prüfung", "klausur", "semester", "vorlesung", "hausaufgabe"]
    if any(keyword in content_lower for keyword in school_keywords):
        if "mathe" in content_lower or "mathematik" in content_lower:
            return "Schule / Mathematik"
        elif "deutsch" in content_lower or "literatur" in content_lower:
            return "Schule / Deutsch"
        elif "englisch" in content_lower or "english" in content_lower:
            return "Schule / Englisch"
        elif "informatik" in content_lower or "programmierung" in content_lower:
            return "Schule / Informatik"
        else:
            return "Schule / Sonstiges"
    
    # Arbeit/Beruf
    work_keywords = ["arbeit", "beruf", "projekt", "kunde", "auftrag", "geschäft", "firma", "kollege", "meeting"]
    if any(keyword in content_lower for keyword in work_keywords):
        if "bewerbung" in content_lower or "lebenslauf" in content_lower:
            return "Arbeit / Bewerbung"
        elif "rechnung" in content_lower or "kosten" in content_lower:
            return "Arbeit / Finanzen"
        else:
            return "Arbeit / Projekt"
    
    # Finanzen
    finance_keywords = ["rechnung", "kosten", "preis", "euro", "€", "steuer", "bank", "konto", "gehalt", "miete"]
    if any(keyword in content_lower for keyword in finance_keywords):
        if "strom" in content_lower or "energie" in content_lower:
            return "Finanzen / Stromrechnung"
        elif "miete" in content_lower or "wohnung" in content_lower:
            return "Finanzen / Miete"
        elif "steuer" in content_lower:
            return "Finanzen / Steuern"
        else:
            return "Finanzen / Rechnungen"
    
    # Code/Programmierung
    code_keywords = ["python", "java", "code", "programm", "funktion", "variable", "import", "def ", "class ", "html", "css"]
    if any(keyword in content_lower for keyword in code_keywords):
        if "python" in content_lower:
            return "Programmierung / Python"
        elif "java" in content_lower:
            return "Programmierung / Java"
        elif "html" in content_lower or "css" in content_lower:
            return "Programmierung / Web"
        else:
            return "Programmierung / Code"
    
    # Persönliches
    personal_keywords = ["geburt", "familie", "freund", "urlaub", "reise", "hobby", "interesse", "einkauf", "kassenzettel"]
    if any(keyword in content_lower for keyword in personal_keywords):
        if "urlaub" in content_lower or "reise" in content_lower:
            return "Persönlich / Reisen"
        elif "einkauf" in content_lower or "kassenzettel" in content_lower:
            return "Persönlich / Einkäufe"
        else:
            return "Persönlich / Dokumente"
    
    # Bilder (basierend auf OCR-Text)
    if ext in [".jpg", ".jpeg", ".png", ".webp"]:
        if "rechnung" in content_lower or "kosten" in content_lower:
            return "Bilder / Rechnungen"
        elif "urlaub" in content_lower or "reise" in content_lower:
            return "Bilder / Urlaub"
        elif "familie" in content_lower or "freund" in content_lower:
            return "Bilder / Familie"
        else:
            return "Bilder / Fotos"
    
    # Je nach Detaillevel unterschiedlich spezifisch
    if detail_level == "viel":
        # Sehr spezifisch
        if "diplomarbeit" in content_lower:
            return "Studium / Diplomarbeit"
        elif "fahrzeug" in content_lower or "auto" in content_lower:
            return "Transport / Fahrzeug"
        elif "gesundheit" in content_lower or "arzt" in content_lower:
            return "Gesundheit / Arzt"
        else:
            return f"Dokumente / {ext[1:].upper() if ext else 'Sonstiges'}"
    
    elif detail_level == "mittel":
        # Mittel spezifisch
        if ext == ".pdf":
            return "Dokumente / PDF"
        elif ext == ".docx":
            return "Dokumente / Word"
        elif ext in [".jpg", ".png"]:
            return "Bilder / Fotos"
        else:
            return "Dokumente / Sonstiges"
    
    else:
        # Wenig spezifisch (breite Kategorien)
        if ext in [".pdf", ".docx", ".txt"]:
            return "Dokumente"
        elif ext in [".jpg", ".png", ".webp"]:
            return "Bilder"
        elif ext in [".py", ".java", ".js"]:
            return "Programmierung"
        else:
            return "Sonstiges"

def create_content_based_fallback_categories(files_data, detail_level):
    """Erstellt Fallback-Kategorien basierend auf DateiINHALT"""
    results = []
    
    for file_data in files_data:
        category = _get_category_from_content(file_data, detail_level)
        
        results.append({
            "filename": file_data["filename"],
            "category": category,
            "confidence": 0.7,
            "reason": "Automatisch aus Inhalt erstellt"
        })
    
    return {"results": results}

# Alte Funktion für Kompatibilität (kann entfernt werden)
def create_fallback_categories(files_data):
    """Veraltete Funktion - verwendet jetzt Inhaltsanalyse"""
    return create_content_based_fallback_categories(files_data, "mittel")