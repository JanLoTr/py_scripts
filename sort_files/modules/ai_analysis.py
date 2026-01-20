# modules/ai_analysis.py - KI-Analyse mit Groq
import json
import re
from groq import Groq
import streamlit as st

def analyze_with_groq(files_data, api_key, detail_level="mittel"):
    """Analysiert Dateien mit Groq KI"""
    try:
        client = Groq(api_key=api_key)
        
        # Prompt basierend auf Detaillevel
        prompts = {
            "wenig": "Kurze Kategorien (1-2 Wörter).",
            "mittel": "Normale Kategorien (Haupt/Unterkategorie).",
            "viel": "Detaillierte Kategorien. Berücksichtige Dateiinhalt."
        }
        
        prompt = prompts.get(detail_level, prompts["mittel"])
        
        system_prompt = f"""Du bist ein Datei-Kategorisierungs-Assistent.

{prompt}

Wichtige Regeln:
1. Eine Kategorie pro Datei
2. Format: "Hauptkategorie / Unterkategorie"
3. Beispiele: "Finanzen / Rechnung", "Programmierung / Python"

Antworte NUR im JSON Format:
{{
  "results": [
    {{
      "filename": "dateiname.xyz",
      "category": "Kategorie / Unterkategorie",
      "confidence": 0.8
    }}
  ]
}}"""
        
        # Dateien für Prompt vorbereiten
        max_files = 30 if detail_level == "viel" else 50
        files_for_prompt = files_data[:max_files]
        
        file_summaries = []
        for f in files_for_prompt:
            summary = {
                "filename": f["filename"],
                "type": f["extension"],
                "preview": f["text_preview"][:300]
            }
            file_summaries.append(summary)
        
        user_message = f"Analysiere diese {len(files_data)} Dateien:\n"
        user_message += json.dumps({"files": file_summaries}, ensure_ascii=False)
        
        # API Call
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        content = response.choices[0].message.content.strip()
        
        # JSON extrahieren
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            content = json_match.group()
        
        result = json.loads(content)
        
        # Sicherstellen, dass alle Dateien eine Kategorie haben
        if "results" in result:
            return _ensure_all_files_categorized(result, files_data)
        
    except Exception as e:
        st.error(f"KI-Fehler: {str(e)[:200]}")
    
    # Fallback
    return create_fallback_categories(files_data)

def _ensure_all_files_categorized(result, files_data):
    """Stellt sicher, dass alle Dateien eine Kategorie haben"""
    processed_filenames = {r["filename"] for r in result["results"]}
    
    # Fehlende Dateien hinzufügen
    for file_data in files_data:
        if file_data["filename"] not in processed_filenames:
            category = _get_category_from_filetype(file_data["extension"])
            result["results"].append({
                "filename": file_data["filename"],
                "category": category,
                "confidence": 0.5
            })
    
    return result

def _get_category_from_filetype(extension):
    """Bestimmt Kategorie basierend auf Dateityp"""
    ext = extension.lower()
    
    if ext in [".py", ".java", ".js", ".cpp", ".c"]:
        return "Programmierung / Code"
    elif ext in [".pdf"]:
        return "Dokumente / PDF"
    elif ext in [".jpg", ".png", ".webp"]:
        return "Bilder / Fotos"
    elif ext in [".docx", ".txt"]:
        return "Dokumente / Text"
    elif ext in [".xlsx", ".csv"]:
        return "Daten / Tabellen"
    elif ext in [".zip"]:
        return "Archiv / ZIP"
    else:
        return "Divers / Sonstiges"

def create_fallback_categories(files_data):
    """Erstellt Fallback-Kategorien basierend auf Dateityp"""
    results = []
    
    for file_data in files_data:
        category = _get_category_from_filetype(file_data["extension"])
        
        results.append({
            "filename": file_data["filename"],
            "category": category,
            "confidence": 0.7
        })
    
    return {"results": results}