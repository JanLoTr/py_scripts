import json
from pathlib import Path
import pandas as pd
from datetime import datetime

# ============ KONFIGURATION ============
SCRIPT_DIR = Path(__file__).parent.absolute()
EXTRACTED_DATA_DIR = SCRIPT_DIR / "extracted_data"
INPUT_DIR = SCRIPT_DIR / "rechnungen"
OUTPUT_REPORT_DIR = SCRIPT_DIR / "rechnungsberichte"
OUTPUT_REPORT_DIR.mkdir(exist_ok=True)

# ============ FUNKTIONEN ============
def rename_invoice_files():
    """Benennt Rechnungsdateien um basierend auf extrahierten Daten"""
    
    print("=== DATEIEN UMBENENNEN ===")
    
    # Lade alle extrahierten Daten
    json_files = list(EXTRACTED_DATA_DIR.glob("*_data.json"))
    
    if not json_files:
        print("Keine extrahierten Daten gefunden. Führen Sie zuerst das Extraktionsskript aus.")
        return []
    
    renamed_files = []
    
    for json_file in json_files:
        with open(json_file, 'r', encoding='utf-8') as f:
            invoice_data = json.load(f)
        
        original_path = Path(invoice_data['original_path'])
        new_name = invoice_data.get('suggested_filename', original_path.name)
        new_path = original_path.parent / new_name
        
        # Verhindere doppelte Dateinamen
        counter = 1
        while new_path.exists() and new_path != original_path:
            name_parts = new_name.rsplit('.', 1)
            if len(name_parts) == 2:
                new_path = original_path.parent / f"{name_parts[0]}_{counter}.{name_parts[1]}"
            else:
                new_path = original_path.parent / f"{new_name}_{counter}"
            counter += 1
        
        try:
            original_path.rename(new_path)
            renamed_files.append({
                'old': original_path.name,
                'new': new_path.name,
                'shop': invoice_data['shop'],
                'date': invoice_data['date'],
                'total': invoice_data.get('total', 0)
            })
            print(f"Umbenannt: {original_path.name} → {new_path.name}")
            
            # Aktualisiere den Pfad in der JSON-Datei
            invoice_data['renamed_to'] = new_path.name
            invoice_data['renamed_path'] = str(new_path)
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(invoice_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"Fehler beim Umbenennen von {original_path.name}: {e}")
    
    return renamed_files

def create_summary_report():
    """Erstellt eine Gesamtübersicht aller Rechnungen"""
    
    print("\n=== GESAMTÜBERSICHT ERSTELLEN ===")
    
    json_files = list(EXTRACTED_DATA_DIR.glob("*_data.json"))
    
    if not json_files:
        print("Keine Daten gefunden.")
        return None
    
    all_invoices = []
    all_products = []
    
    for json_file in json_files:
        with open(json_file, 'r', encoding='utf-8') as f:
            invoice = json.load(f)
        
        # Rechnungsdaten
        invoice_summary = {
            'Dateiname': invoice.get('renamed_to', invoice['original_filename']),
            'Datum': invoice.get('date', 'Unbekannt'),
            'Shop': invoice.get('shop', 'Unbekannt'),
            'Gesamtbetrag': invoice.get('total', 0),
            'Produktanzahl': len(invoice.get('products', [])),
            'Produktsumme': invoice.get('product_total', 0),
            'Differenz': invoice.get('discrepancy', 0),
            'Dateipfad': invoice.get('renamed_path', invoice['original_path'])
        }
        all_invoices.append(invoice_summary)
        
        # Produktdaten
        for product in invoice.get('products', []):
            product_entry = {
                'Rechnung': invoice_summary['Dateiname'],
                'Datum': invoice_summary['Datum'],
                'Shop': invoice_summary['Shop'],
                'Produkt': product.get('name', 'Unbekannt'),
                'Menge': product.get('quantity', 1),
                'Einzelpreis': product.get('price', 0),
                'Gesamt': product.get('total', 0),
                'Vertrauen': product.get('confidence', 'unbekannt'),
                'Für mich allein': False,  # Manuell zu setzen
                'Kommentar': ''
            }
            all_products.append(product_entry)
    
    # DataFrames erstellen
    df_invoices = pd.DataFrame(all_invoices)
    df_products = pd.DataFrame(all_products)
    
    # Berichte speichern
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. Rechnungsübersicht
    invoice_report = OUTPUT_REPORT_DIR / f"rechnungsuebersicht_{timestamp}.xlsx"
    with pd.ExcelWriter(invoice_report, engine='openpyxl') as writer:
        df_invoices.to_excel(writer, sheet_name='Rechnungen', index=False)
        
        # Zusammenfassung
        summary_data = {
            'Metrik': ['Gesamtrechnungen', 'Gesamtbetrag', 'Durchschnitt pro Rechnung',
                      'Häufigster Shop', 'Zeitraum'],
            'Wert': [
                len(df_invoices),
                f"{df_invoices['Gesamtbetrag'].sum():.2f} EUR",
                f"{df_invoices['Gesamtbetrag'].mean():.2f} EUR",
                df_invoices['Shop'].mode().iloc[0] if not df_invoices['Shop'].mode().empty else 'N/A',
                f"{df_invoices['Datum'].min()} bis {df_invoices['Datum'].max()}"
            ]
        }
        df_summary = pd.DataFrame(summary_data)
        df_summary.to_excel(writer, sheet_name='Zusammenfassung', index=False)
        
        # Shop-Statistik
        shop_stats = df_invoices.groupby('Shop').agg({
            'Gesamtbetrag': ['count', 'sum', 'mean'],
            'Produktanzahl': 'mean'
        }).round(2)
        shop_stats.columns = ['Anzahl', 'Gesamt', 'Durchschnitt', 'Produkte/Rechnung']
        shop_stats.to_excel(writer, sheet_name='Shop-Statistik')
    
    # 2. Produktübersicht
    product_report = OUTPUT_REPORT_DIR / f"produktuebersicht_{timestamp}.xlsx"
    with pd.ExcelWriter(product_report, engine='openpyxl') as writer:
        df_products.to_excel(writer, sheet_name='Alle Produkte', index=False)
        
        # Produktstatistik
        product_stats = df_products.groupby('Produkt').agg({
            'Menge': 'sum',
            'Gesamt': 'sum',
            'Rechnung': 'count'
        }).round(2)
        product_stats.columns = ['Gesamtmenge', 'Gesamtkosten', 'Anzahl Rechnungen']
        product_stats = product_stats.sort_values('Gesamtkosten', ascending=False)
        product_stats.to_excel(writer, sheet_name='Produktstatistik')
        
        # Nach Shop
        shop_product_stats = df_products.groupby(['Shop', 'Produkt']).agg({
            'Gesamt': 'sum',
            'Menge': 'sum'
        }).round(2)
        shop_product_stats.to_excel(writer, sheet_name='Nach Shop')
    
    # 3. Interaktive CSV für individuelle Anpassungen
    interactive_csv = OUTPUT_REPORT_DIR / f"interaktive_aufteilung_{timestamp}.csv"
    
    # Füge Spalten für individuelle Aufteilung hinzu
    df_products['Anteil_Bruder'] = 0.5  # Standard: 50/50
    df_products['Anteil_Ich'] = 0.5
    df_products['Betrag_Bruder'] = df_products['Gesamt'] * df_products['Anteil_Bruder']
    df_products['Betrag_Ich'] = df_products['Gesamt'] * df_products['Anteil_Ich']
    
    # Berechne Gesamtsummen
    total_all = df_products['Gesamt'].sum()
    total_brother = df_products['Betrag_Bruder'].sum()
    total_me = df_products['Betrag_Ich'].sum()
    
    # Füge Gesamtsummen hinzu
    total_row = pd.DataFrame([{
        'Rechnung': 'GESAMT',
        'Datum': '',
        'Shop': '',
        'Produkt': 'SUMME ALLER PRODUKTE',
        'Menge': '',
        'Einzelpreis': '',
        'Gesamt': total_all,
        'Betrag_Bruder': total_brother,
        'Betrag_Ich': total_me,
        'Differenz': total_all - (total_brother + total_me)
    }])
    
    df_with_totals = pd.concat([df_products, total_row], ignore_index=True)
    df_with_totals.to_csv(interactive_csv, index=False, encoding='utf-8-sig')
    
    print(f"\nBerichte erstellt:")
    print(f"1. Rechnungsübersicht: {invoice_report}")
    print(f"2. Produktübersicht: {product_report}")
    print(f"3. Interaktive Aufteilung: {interactive_csv}")
    
    print(f"\nGesamtstatistik:")
    print(f"- Rechnungen: {len(df_invoices)}")
    print(f"- Gesamtbetrag: {df_invoices['Gesamtbetrag'].sum():.2f} EUR")
    print(f"- Produkte: {len(df_products)}")
    print(f"- Standardaufteilung (50/50):")
    print(f"  → Bruder: {total_brother:.2f} EUR")
    print(f"  → Ich: {total_me:.2f} EUR")
    
    return {
        'invoices': df_invoices,
        'products': df_products,
        'reports': {
            'invoices': invoice_report,
            'products': product_report,
            'interactive': interactive_csv
        }
    }

def update_split_from_csv(csv_path):
    """
    Liest eine bearbeitete CSV und aktualisiert die Gesamtberechnung
    """
    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
        
        # Entferne Gesamtzeile falls vorhanden
        df = df[df['Rechnung'] != 'GESAMT']
        
        # Berechne neue Summen
        total_all = df['Gesamt'].sum()
        total_brother = df['Betrag_Bruder'].sum()
        total_me = df['Betrag_Ich'].sum()
        
        print(f"\nAktualisierte Aufteilung:")
        print(f"Gesamt: {total_all:.2f} EUR")
        print(f"Bruder: {total_brother:.2f} EUR ({total_brother/total_all*100:.1f}%)")
        print(f"Ich: {total_me:.2f} EUR ({total_me/total_all*100:.1f}%)")
        print(f"Differenz: {(total_all - (total_brother + total_me)):.2f} EUR")
        
        return {
            'total': total_all,
            'brother': total_brother,
            'me': total_me
        }
        
    except Exception as e:
        print(f"Fehler beim Lesen der CSV: {e}")
        return None

# ============ HAUPTMENÜ ============
def main():
    print("=== RECHNUNGS MANAGER ===")
    print(f"Skript-Verzeichnis: {SCRIPT_DIR}")
    print("=" * 50)
    
    while True:
        print("\nWas möchten Sie tun?")
        print("1. Dateien umbenennen (basierend auf extrahierten Daten)")
        print("2. Gesamtbericht erstellen")
        print("3. Aufteilung aus CSV aktualisieren")
        print("4. Beides (1+2)")
        print("5. Beenden")
        
        choice = input("\nIhre Wahl (1-5): ").strip()
        
        if choice == "1":
            rename_invoice_files()
        elif choice == "2":
            create_summary_report()
        elif choice == "3":
            csv_file = input("Pfad zur bearbeiteten CSV-Datei: ").strip()
            if Path(csv_file).exists():
                update_split_from_csv(csv_file)
            else:
                print("Datei existiert nicht.")
        elif choice == "4":
            rename_invoice_files()
            create_summary_report()
        elif choice == "5":
            print("Programm beendet.")
            break
        else:
            print("Ungültige Eingabe.")

if __name__ == "__main__":
    main()