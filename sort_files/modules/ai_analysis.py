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

BENUTZER-KONTEXT:
- Der Benutzer ging in die HTL (Berufsschule) - HTL-Material daher älter, archiviert
- Der Benutzer studiert an einer FH (Fachhochschule) - FH-Material ist aktueller
- HTL-typische Inhalte: Kostenrechnung, Betriebswirtschaft, BWL, Lagerbestand
- FH-typische Inhalte: Vorlesungen, Diplomarbeit, aktuelle Studiumsinhalte

{prompt}

WICHTIGSTE REGEL: KATEGORISIERE NACH INHALT, NICHT NACH DATEITYP!
Analysiere den Dateiinhalt in 'text_preview' und erstelle sinnvolle Kategorien.

ANWEISUNGEN:
1. LIES den Dateiinhalt in 'text_preview' 
2. ERKENNE das Hauptthema (nicht Dateityp!)
3. UNTERSCHEIDE zwischen HTL-Material und FH-Material
4. ERSTELLE sinnvolle Kategorien wie: "HTL/Betriebswirtschaft", "FH/Mathematik", "Arbeit/Projekt-X", "Finanzen/Steuern"
5. KEINE generischen Kategorien wie "PDF-Dateien" oder "Bilder"
6. Format: "Hauptkategorie / Spezifische Kategorie"

SPEZIAL-REGEL - KOSTENRECHNUNG:
- Wenn "Kostenrechnung" oder "Kalkulieren" erwähnt wird → IMMER "HTL / Betriebswirtschaft"
- Das ist ein HTL-Fach, NICHT persönlich!

BEISPIELE FÜR GUTE KATEGORIEN:
- "HTL / Betriebswirtschaft" (für Kostenrechnung-Unterlagen)
- "FH / Mathematik" (für aktuelle FH-Vorlesungen)
- "Bewerbung / Lebenslauf" (nicht "Word-Dokument")
- "Programmierung / Python" (nicht "Code")
- "Familie / Geburtsurkunde" (nicht "Scan")
- "Auto / Reparaturkosten" (nicht "Rechnung")
- "Finanzen / Stromrechnung" (nicht "PDF")

BEISPIELE FÜR SCHLECHTE KATEGORIEN:
- "PDF Datei" ❌ (zu generisch)
- "Bild" ❌ (sagt nichts aus)
- "Textdatei" ❌ (uninformativ)
- "Microsoft Word" ❌ (Dateityp, nicht Inhalt)
- "Persönlich / Kostenrechnung" ❌ (Kostenrechnung ist HTL-Material!)

ANALYSIERE JETZT DIESE DATEIEN NACH IHREM INHALT UND KONTEXT:

Antworte NUR im JSON Format:
{{
  "results": [
    {{
      "filename": "dateiname.xyz",
      "category": "Hauptkategorie / Spezifische Kategorie",
      "confidence": 0.0-1.0,
      "reason": "kurze Begründung basierend auf Inhalt und Kontext"
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
            
            # Erkenne wichtige Themen (erweiterte Heuristik mit HTL/FH Unterscheidung)
            themes = []
            preview_lower = preview.lower()
            filename_lower = f["filename"].lower()
            
            # HTL-spezifisch (Berufsschule)
            if any(word in preview_lower or word in filename_lower for word in ["kostenrechnung", "betriebswirtschaft", "bw", "buchhaltung", "deckungsbeitrag", "lagerhaltung"]):
                themes.append("HTL / Betriebswirtschaft")
            
            # FH-spezifisch (Fachhochschule - aktuelle Studiumsinhalte)
            if any(word in preview_lower or word in filename_lower for word in ["diplomarbeit", "seminar", "vorlesung", "modulhandbuch", "prüfungsordnung"]):
                themes.append("FH / Studium")
            
            # Schule/Studium (allgemein)
            if any(word in preview_lower for word in ["schule", "studium", "matura", "prüfung", "hausaufgabe", "klausur", "unterricht"]):
                if "HTL" not in str(themes) and "FH" not in str(themes):
                    themes.append("Schule/Studium")
            
            # Arbeit/Beruf/Praktikum
            if any(word in preview_lower for word in ["arbeit", "beruf", "projekt", "kunde", "auftrag", "geschäft", "firma", "praktikum", "internship"]):
                themes.append("Arbeit/Beruf")
            
            # Finanzen
            if any(word in preview_lower for word in ["rechnung", "kosten", "preis", "euro", "€", "steuer", "bank", "konto", "gehalt", "miete", "versicherung"]):
                themes.append("Finanzen")
            
            # Code/Programmierung
            if any(word in preview_lower for word in ["python", "java", "code", "programm", "funktion", "variable", "import", "def ", "class ", "html", "css"]):
                themes.append("Programmierung")
            
            # Persönlich/Familie
            if any(word in preview_lower for word in ["geburt", "familie", "freund", "verwandt", "verwandtschaft"]):
                themes.append("Familie/Persönlich")
            
            # Reisen/Freizeit
            if any(word in preview_lower for word in ["urlaub", "reise", "trip", "hotel", "flug", "fahrkarte"]):
                themes.append("Reisen/Freizeit")
            
            # Einkaufe/Shopping
            if any(word in preview_lower for word in ["einkauf", "kassenzettel", "rechnung", "amazon", "shopping", "bestellt"]):
                if "Finanzen" not in str(themes):
                    themes.append("Shopping/Einkäufe")
            
            # Gesundheit
            if any(word in preview_lower for word in ["arzt", "krank", "gesund", "medizin", "rezept", "apotheke", "zahnarzt", "impf"]):
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
    """Bestimmt Kategorie basierend auf DateiINHALT (nicht Dateityp!)
    
    KONTEXT: Benutzer ging in HTL (Berufsschule) und studiert an einer FH (Fachhochschule)
    HTL-Inhalte: Kostenrechnung, Betriebswirtschaft, technische Fächer
    FH-Inhalte: Neuere Vorlesungen, Diplomarbeit, aktuelle Projekte
    """
    preview = file_data["text_preview"].lower()
    ext = file_data["extension"].lower()
    
    # Analyse des Inhalts
    content_lower = preview.lower()
    filename_lower = file_data["filename"].lower()
    
    # ===== HTL vs. FH UNTERSCHEIDUNG (intelligente Kontextualisierung) =====
    htl_keywords = [
        "kostenrechnung", "betriebswirtschaft", "bw", "buchhaltung", "kalkulieren",
        "deckungsbeitrag", "gewinn", "verlust", "betrieb", "kaufmann", "handel",
        "lagerbestand", "bestellung", "lieferant", "lagerhaltung"
    ]
    
    fh_keywords = [
        "semester", "vorlesung", "diplomarbeit", "masterarbeit", "hochschule",
        "fachhochschule", "klausur", "prüfung", "skript", "vorlesungsmitschrift",
        "prüfungsordnung", "modulhandbuch"
    ]
    
    is_htl_content = any(keyword in content_lower or keyword in filename_lower for keyword in htl_keywords)
    is_fh_content = any(keyword in content_lower or keyword in filename_lower for keyword in fh_keywords)
    
    # Schule/Studium Inhalte mit HTL/FH Unterscheidung
    school_keywords = ["schule", "studium", "matura", "prüfung", "klausur", "semester", "vorlesung", "hausaufgabe", "unterricht", "lehrplan"]
    if any(keyword in content_lower for keyword in school_keywords):
        # Spezifische Fächer erkennen
        if "mathe" in content_lower or "mathematik" in content_lower:
            folder = "Mathematik"
        elif "deutsch" in content_lower or "literatur" in content_lower:
            folder = "Deutsch"
        elif "englisch" in content_lower or "english" in content_lower:
            folder = "Englisch"
        elif "informatik" in content_lower or "programmierung" in content_lower:
            folder = "Informatik"
        elif "physik" in content_lower:
            folder = "Physik"
        elif "chemie" in content_lower:
            folder = "Chemie"
        elif "biologie" in content_lower:
            folder = "Biologie"
        else:
            folder = "Sonstiges"
        
        # HTL vs FH Unterscheidung
        if is_htl_content:
            return f"HTL / {folder}"
        elif is_fh_content:
            return f"FH / {folder}"
        else:
            return f"Schule / {folder}"
    
    # Arbeit/Beruf/Praktikum
    work_keywords = ["arbeit", "beruf", "projekt", "kunde", "auftrag", "geschäft", "firma", "kollege", "meeting", "praktikum", "internship"]
    if any(keyword in content_lower for keyword in work_keywords):
        if "bewerbung" in content_lower or "lebenslauf" in content_lower or "cv" in content_lower:
            return "Bewerbung / Unterlagen"
        elif "rechnung" in content_lower or "kosten" in content_lower or "budget" in content_lower:
            return "Arbeit / Finanzen"
        elif "praktikum" in content_lower or "internship" in content_lower:
            return "Praktikum / Unterlagen"
        else:
            return "Arbeit / Projekt"
    
    # Finanzen (ABER: Kostenrechnung könnte HTL-Material sein!)
    finance_keywords = ["rechnung", "kosten", "preis", "euro", "€", "steuer", "bank", "konto", "gehalt", "miete", "zinsen", "versicherung"]
    if any(keyword in content_lower for keyword in finance_keywords):
        # Überprüfe ob es HTL-Material ist (Kostenrechnung ist ein HTL-Fach)
        if is_htl_content or ("kostenrechnung" in content_lower and "betrieb" in content_lower):
            return "HTL / Betriebswirtschaft"
        elif "strom" in content_lower or "energie" in content_lower:
            return "Finanzen / Stromrechnung"
        elif "miete" in content_lower or "wohnung" in content_lower or "nebenkosten" in content_lower:
            return "Finanzen / Miete & Wohnung"
        elif "steuer" in content_lower or "steuererklärung" in content_lower:
            return "Finanzen / Steuern"
        elif "versicherung" in content_lower or "versichert" in content_lower:
            return "Finanzen / Versicherung"
        else:
            return "Finanzen / Rechnungen"
    
    # Code/Programmierung
    code_keywords = ["python", "java", "code", "programm", "funktion", "variable", "import", "def ", "class ", "html", "css"]
    if any(keyword in content_lower for keyword in code_keywords):
        if "python" in content_lower:
            return "Programmierung / Python"
        elif "java" in content_lower:
            return "Programmierung / Java"
        elif "html" in content_lower or "css" in content_lower or "javascript" in content_lower:
            return "Programmierung / Web"
        else:
            return "Programmierung / Code"
    
    # Persönliches & Freizeit
    personal_keywords = ["geburt", "familie", "freund", "urlaub", "reise", "hobby", "interesse", "einkauf", "kassenzettel", "event", "party", "wedding"]
    if any(keyword in content_lower for keyword in personal_keywords):
        if "urlaub" in content_lower or "reise" in content_lower or "trip" in content_lower:
            return "Freizeit / Reisen"
        elif "einkauf" in content_lower or "kassenzettel" in content_lower or "shopping" in content_lower:
            return "Persönlich / Einkäufe"
        elif "familie" in content_lower or "geburt" in content_lower:
            return "Familie / Dokumente"
        elif "freund" in content_lower or "party" in content_lower or "event" in content_lower:
            return "Freizeit / Aktivitäten"
        else:
            return "Persönlich / Sonstiges"
    
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
            return "FH / Diplomarbeit"
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