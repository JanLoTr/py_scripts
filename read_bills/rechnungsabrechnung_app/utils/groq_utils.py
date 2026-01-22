"""
Groq KI-Integration für intelligente Rechnungsanalyse
"""
from typing import Optional, List, Dict
import json
import re

def initialize_groq_client(api_key: str):
    """
    Initialisiert den Groq-Client
    
    Args:
        api_key: Der Groq API Key
        
    Returns:
        Groq-Client oder None
    """
    try:
        from groq import Groq
        if not api_key:
            print("API_KEY nicht vorhanden")
            return None
        return Groq(api_key=api_key)
    except Exception as e:
        print(f"Fehler beim Initialisieren des Groq-Clients: {e}")
        return None

def improve_invoice_data(client, raw_text: str) -> Optional[Dict]:
    """
    Verbessert extrahierte Rechnungsdaten mit intelligenter KI-Analyse
    
    Die KI führt folgende Verbesserungen durch:
    - Rechnungsverständnis und -struktur
    - Produkt- & Aktionslogik (ignoriert Rabatte als Produkte)
    - Shop-Erkennung (Spar, Hofer, Lidl, TransGourmet, TKMaxx, etc.)
    - Preis- & Summenprüfung
    - Semantische Verbesserung von Produktnamen
    
    Args:
        client: Groq-Client
        raw_text: Roher OCR-Text von der Rechnung
        
    Returns:
        Verbessertes JSON mit Produkten und Metadaten oder None
    """
    try:
        if not client:
            return None
        
        prompt = """Du erhältst OCR-Text von einer Rechnung oder einem Beleg.
Deine Aufgabe ist es, diese Daten intelligent zu analysieren, zu korrigieren und zu strukturieren.

WICHTIGE ANFORDERUNGEN:

1. RECHNUNGSVERSTÄNDNIS
   - Erkenne, ob es sich um eine Rechnung, einen Beleg oder Bon handelt
   - Rekonstruiere die logisch richtige Struktur (Shop, Positionen, Preise)
   
2. PRODUKT- & AKTIONSLOGIK
   - Aktionen wie "Rabatt", "AKTION -0,50€", "Gutschrift" sind KEINE Produkte
   - Ordne Rabatte dem Gesamtbetrag zu, nicht einzelnen Produkten
   - Berechne Endpreise nach Rabatten
   - Ignoriere Marketing-Text und Werbung
   
3. SHOP-ERKENNUNG
   - Erkenne zuverlässig den Shop/Händler aus dem Text
   - Mögliche Shops: Spar, Hofer, Lidl, Rewe, Edeka, TransGourmet, TKMaxx, dm, Rossmann, Müller, Aldi, etc.
   - Vereinheitliche Namen (z.B. "Sparmarkt" → "Spar", "REWE" → "Rewe")
   
4. PREIS- & SUMMENPRÜFUNG
   - Prüfe mathematische Konsistenz (Preise, Mengen, Summen)
   - Korrigiere offensichtliche Fehler
   
5. SEMANTISCHE VERBESSERUNG
   - Vereinfache kryptische Produktnamen wenn möglich
   - Nutze logische Produktergänzung (z.B. "Ap...el" → "Apfel")
   - Entferne OCR-Fehler in Produktnamen
   - Markiere Produkte als "unerkenntlich" wenn völlig unklar
   
6. OUTPUT FORMAT
   Gib folgendes JSON zurück:
   {
     "shop": "Shopname",
     "products": [
       {"produkt": "Produktname", "preis": 1.99},
       ...
     ],
     "subtotal": 25.00,
     "discount": 0.00,
     "total": 25.00,
     "notes": "Kurze Erklärung der Korrektionen"
   }

OCR-Text zur Verarbeitung:
{text}

Antworte NUR mit valid JSON, nichts anderes."""
        
        message = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt.format(text=raw_text)
                }
            ],
            model="mixtral-8x7b-32768",
            temperature=0.3,
            max_tokens=2048,
        )
        
        response_text = message.choices[0].message.content.strip()
        
        # Extrahiere JSON
        try:
            # Versuche JSON zwischen ``` zu finden
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(1)
            else:
                # Versuche direktes JSON
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_text = json_match.group(0)
                else:
                    json_text = response_text
            
            improved_data = json.loads(json_text)
            
            # Validiere und bereinige
            if "shop" not in improved_data:
                improved_data["shop"] = "Unbekannt"
            
            if "products" not in improved_data or not isinstance(improved_data["products"], list):
                improved_data["products"] = []
            
            # Bereinige Produkte
            cleaned_products = []
            for product in improved_data.get("products", []):
                if isinstance(product, dict) and "produkt" in product and "preis" in product:
                    try:
                        preis = float(str(product["preis"]).replace(",", "."))
                        cleaned_products.append({
                            "produkt": str(product["produkt"]).strip(),
                            "preis": round(preis, 2)
                        })
                    except (ValueError, TypeError):
                        continue
            
            improved_data["products"] = cleaned_products
            
            # Standardwerte für fehlende Felder
            if "total" not in improved_data or improved_data["total"] is None:
                improved_data["total"] = sum(p["preis"] for p in cleaned_products)
            
            if "subtotal" not in improved_data:
                improved_data["subtotal"] = improved_data.get("total", 0)
            
            if "discount" not in improved_data:
                improved_data["discount"] = 0
            
            improved_data["notes"] = improved_data.get("notes", "")
            
            return improved_data
            
        except json.JSONDecodeError as e:
            print(f"Fehler beim JSON-Parsing: {e}")
            print(f"Response: {response_text}")
            return None
            
    except Exception as e:
        print(f"Fehler bei der Datenverbesserung: {e}")
        return None

def extract_invoice_products(client, invoice_text: str) -> Optional[List[Dict]]:
    """
    Extrahiert Produkte und Preise aus Rechnungstext mit intelligenter KI-Analyse
    
    Die KI nutzt folgende Intelligenz:
    - Wenn ein Produktname unvollständig ist (z.B. "Ap...El"), versucht sie,
      das Produkt zu vervollständigen
    - Aktions-Preise werden ignoriert, der Endpreis wird verwendet
    - Unerkannte Produkte werden als "unerkenntlich" gekennzeichnet
    - Preise werden immer von der Rechnung übernommen
    
    Args:
        client: Groq-Client
        invoice_text: Rechnungstext zum Analysieren
        
    Returns:
        Liste von Produkten mit Preisen oder None
    """
    try:
        if not client:
            return None
        
        prompt = """Analysiere folgende Rechnung und extrahiere ALLE Produkte mit ihren Endpreisen.

WICHTIGE REGELN:
1. Extrahiere JEDEN gekauften Artikel mit dem ENDPREIS von der Rechnung
2. Ignoriere "Aktion-Preis" oder "Rabatt" Einträge - nutze den Endpreis beim Artikel
3. Bei unvollständigen Produktnamen (z.B. "Ap...El", "M...lch"):
   - Denke logisch: "Ap" + viel Platz + "El" = wahrscheinlich "Apfel"
   - "M" + kurzer Platz + "lch" = wahrscheinlich "Milch"
   - Versuche das Produkt intelligent zu vervollständigen
4. Wenn der Produktname GAR NICHT erkennbar ist, schreibe "unerkenntlich"
5. Nutze immer den ENDPREIS von der Rechnung, nicht selbst berechnen
6. Format: JSON-Array mit {"produkt": "Name", "preis": 0.00}

Rechnungstext:
{text}

Antwort (nur JSON-Array, nichts anderes):"""
        
        message = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt.format(text=invoice_text)
                }
            ],
            model="mixtral-8x7b-32768",
            temperature=0.3,
            max_tokens=2048,
        )
        
        response_text = message.choices[0].message.content.strip()
        
        # Extrahiere JSON aus der Antwort
        try:
            # Versuche JSON zwischen ``` zu finden
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(1)
            else:
                # Versuche direktes JSON
                json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
                if json_match:
                    json_text = json_match.group(0)
                else:
                    json_text = response_text
            
            products = json.loads(json_text)
            
            # Validiere und bereinige die Produktliste
            cleaned_products = []
            for product in products:
                if isinstance(product, dict) and "produkt" in product and "preis" in product:
                    try:
                        preis = float(str(product["preis"]).replace(",", "."))
                        cleaned_products.append({
                            "produkt": str(product["produkt"]).strip(),
                            "preis": round(preis, 2)
                        })
                    except ValueError:
                        continue
            
            return cleaned_products if cleaned_products else None
        except json.JSONDecodeError as e:
            print(f"Fehler beim JSON-Parsing: {e}")
            print(f"Response: {response_text}")
            return None
            
    except Exception as e:
        print(f"Fehler bei der Produktextraktion: {e}")
        return None

def correct_product_name(product_name: str) -> str:
    """
    Korrigiert einen Produktnamen intelligently
    
    Args:
        product_name: Der zu korrigierende Name
        
    Returns:
        Korrigierter Produktname
    """
    # Mapping von häufigen OCR-Fehlern
    corrections = {
        "l": "I",  # Kleine l zu I
        "O": "0",  # Großes O zu 0
    }
    
    # Wenn der Name sehr kurz ist und Punkte hat, versuche zu rekonstruieren
    if "." in product_name and len(product_name.replace(".", "")) < 5:
        # Das ist wahrscheinlich ein unvollständiger Name wie "Ap...el"
        parts = product_name.split(".")
        if len(parts) >= 2:
            # Versuche intelligente Ergänzung
            start = parts[0]
            end = parts[-1]
            
            # Bekannte Produkte mit Anfang und Ende
            common_products = {
                ("Ap", "el"): "Apfel",
                ("M", "lch"): "Milch",
                ("B", "t"): "Brot",
                ("K", "se"): "Käse",
                ("W", "st"): "Wurst",
                ("Sc", "nken"): "Schinken",
            }
            
            for (s, e), full_name in common_products.items():
                if product_name.lower().startswith(s.lower()) and product_name.lower().endswith(e.lower()):
                    return full_name
    
    return product_name if product_name else "unerkenntlich"

def validate_prices_and_detect_anomalies(client, products: List[Dict]) -> Optional[Dict]:
    """
    Validiert Preise und erkennt anomale Produkte/Preise
    
    Detektiert:
    - Unrealistisch hohe oder niedrige Preise
    - Verdächtige Produkt-Preis-Kombinationen
    - Mögliche Duplikate oder ähnliche Produkte
    
    Args:
        client: Groq-Client
        products: Liste von Produkten mit Preisen
        
    Returns:
        Dict mit Validierungsergebnissen oder None
    """
    try:
        if not client or not products:
            return None
        
        products_text = "\n".join([f"- {p['produkt']}: €{p['preis']:.2f}" for p in products])
        
        prompt = f"""Validiere diese Einkaufsprodukte und erkenne Anomalien:

{products_text}

Prüfe auf:
1. Unrealistisch hohe/niedrige Preise für das Produkt
2. Verdächtige Produkt-Preis-Kombinationen
3. Mögliche Duplikate oder sehr ähnliche Produkte
4. Plausibilität des Gesamteinkaufs

Format für Warnung: {{"produkt": "Name", "issue": "Kurze Erklärung", "severity": "low|medium|high"}}

Antwort: JSON-Array nur mit problematischen Produkten, oder leeres Array wenn alles ok"""
        
        message = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="mixtral-8x7b-32768",
            temperature=0.2,
            max_tokens=1024,
        )
        
        response_text = message.choices[0].message.content.strip()
        
        try:
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                issues = json.loads(json_match.group(0))
                return {"anomalies": issues} if issues else {"anomalies": []}
        except json.JSONDecodeError:
            pass
        
        return {"anomalies": []}
    except Exception as e:
        print(f"Fehler bei Preisvalidierung: {e}")
        return None

def categorize_products(client, products: List[Dict]) -> Optional[List[Dict]]:
    """
    Kategorisiert Produkte intelligent
    
    Kategorien: Lebensmittel, Getränke, Haushalt, Kosmetik/Hygiene, Sonstiges
    
    Args:
        client: Groq-Client
        products: Liste von Produkten
        
    Returns:
        Produkte mit Kategorien oder None
    """
    try:
        if not client or not products:
            return None
        
        products_text = "\n".join([f"- {p['produkt']}" for p in products])
        
        prompt = f"""Kategorisiere diese Produkte in Kategorien:

{products_text}

Kategorien: Lebensmittel, Getränke, Haushalt, Kosmetik/Hygiene, Sonstiges

Format: {{"produkt": "Name", "kategorie": "Kategorie"}}

Antwort: JSON-Array mit allen Produkten"""
        
        message = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="mixtral-8x7b-32768",
            temperature=0.2,
            max_tokens=1024,
        )
        
        response_text = message.choices[0].message.content.strip()
        
        try:
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                categorized = json.loads(json_match.group(0))
                return categorized
        except json.JSONDecodeError:
            pass
        
        return None
    except Exception as e:
        print(f"Fehler bei Kategorisierung: {e}")
        return None

def suggest_split_distribution(client, products: List[Dict], person1: str, person2: str) -> Optional[Dict]:
    """
    Schlägt intelligente Aufteilung basierend auf Produktnamen vor
    
    Logik:
    - Persönliche Hygieneprodukte: 100/0 oder 0/100
    - Getränke/Snacks: Wahrscheinlich 50/50
    - Luxusartikel: Häufig 100/0 oder 0/100
    
    Args:
        client: Groq-Client
        products: Liste von Produkten
        person1: Name Bruder 1
        person2: Name Bruder 2
        
    Returns:
        Aufteilungsvorschläge oder None
    """
    try:
        if not client or not products:
            return None
        
        products_text = "\n".join([f"- {p['produkt']} (€{p['preis']:.2f})" for p in products])
        
        prompt = f"""Schlag eine intelligente Kostaufteilung vor zwischen {person1} und {person2}:

{products_text}

Logik:
- Persönliche Hygieneprodukte: 100/0 oder 0/100 (vermute basierend auf Produktname oder sei neutral 50/50)
- Getränke/Snacks: Meist 50/50
- Luxusartikel: Oft 100/0 oder 0/100 (frag dich: würde der andere das kaufen?)
- Haushalt: 50/50
- Bei Zweifeln: 50/50

Format: {{"produkt": "Name", "person1_percent": 50, "person2_percent": 50, "reasoning": "Kurze Begründung"}}

Antwort: JSON-Array mit Vorschlägen für ALLE Produkte"""
        
        message = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="mixtral-8x7b-32768",
            temperature=0.3,
            max_tokens=2048,
        )
        
        response_text = message.choices[0].message.content.strip()
        
        try:
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                suggestions = json.loads(json_match.group(0))
                return {"suggestions": suggestions}
        except json.JSONDecodeError:
            pass
        
        return None
    except Exception as e:
        print(f"Fehler bei Aufteilungsvorschlag: {e}")
        return None

def generate_receipt_summary(client, shop: str, products: List[Dict], total: float) -> Optional[str]:
    """
    Generiert eine intelligente Zusammenfassung der Rechnung
    
    Args:
        client: Groq-Client
        shop: Shop-Name
        products: Liste von Produkten
        total: Gesamtbetrag
        
    Returns:
        Textsummary oder None
    """
    try:
        if not client or not products:
            return None
        
        products_text = "\n".join([f"- {p['produkt']}: €{p['preis']:.2f}" for p in products])
        
        prompt = f"""Schreibe eine kurze, humorvolle 2-3 Satz Zusammenfassung dieses Einkaufs:

Shop: {shop}
Artikel ({len(products)}):
{products_text}

Gesamtbetrag: €{total:.2f}

Beobachtungen: Welche Produkte fallen auf? Wirkt der Einkauf sinnvoll? Gibt es interessante Kombinationen?

Schreibe informativ aber humorvoll, max 3 Sätze."""
        
        message = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="mixtral-8x7b-32768",
            temperature=0.7,
            max_tokens=256,
        )
        
        return message.choices[0].message.content.strip()
    except Exception as e:
        print(f"Fehler bei Summary-Generierung: {e}")
        return None


