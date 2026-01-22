"""
Aufrechnung zwischen zwei Brüdern
Verwaltet die Aufteilung von Rechnungen zwischen zwei Personen
"""
import streamlit as st
import pandas as pd
from pathlib import Path
from config import PROCESSED_DIR
import json
from datetime import datetime
from utils.groq_utils import (
    initialize_groq_client,
    suggest_split_distribution,
    categorize_products,
    validate_prices_and_detect_anomalies,
    generate_receipt_summary
)
from utils.data_manager import DataManager
from utils.analytics import (
    render_statistics_dashboard,
    render_pie_chart,
    render_shops_chart,
    render_product_insights,
    render_solo_buyers
)

# Seitenkonfiguration
st.set_page_config(
    page_title="Rechnungsaufrechnung",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Session State initialisieren
if "brother1_name" not in st.session_state:
    st.session_state.brother1_name = "Bruder 1"
if "brother2_name" not in st.session_state:
    st.session_state.brother2_name = "Bruder 2"
if "loaded_invoices" not in st.session_state:
    st.session_state.loaded_invoices = {}
if "splits" not in st.session_state:
    st.session_state.splits = {}
if "api_key" not in st.session_state:
    st.session_state.api_key = ""
if "ai_suggestions" not in st.session_state:
    st.session_state.ai_suggestions = {}

def load_invoices():
    """Lädt alle gespeicherten CSV-Rechnungen"""
    invoices = {}
    if PROCESSED_DIR.exists():
        csv_files = list(PROCESSED_DIR.glob("*.csv"))
        for csv_file in csv_files:
            # Ignoriere Dateien die mit _Scan enden
            if "_Scan" not in csv_file.name:
                try:
                    df = pd.read_csv(csv_file, sep=";")
                    invoice_name = csv_file.stem
                    invoices[invoice_name] = {
                        "path": csv_file,
                        "data": df
                    }
                except Exception as e:
                    st.error(f"Fehler beim Laden von {csv_file.name}: {e}")
    return invoices

def get_invoice_total(df):
    """Berechnet die Gesamtsumme einer Rechnung"""
    if "preis" in df.columns:
        return df["preis"].astype(float).sum()
    return 0.0

def render_sidebar():
    """Rendert die Seitenleiste"""
    with st.sidebar:
        st.title("⚙️ Einstellungen")
        st.divider()
        
        # Namen eingeben
        st.subheader("👥 Beteiligte Personen")
        
        brother1_name = st.text_input(
            "Name Bruder 1",
            value=st.session_state.brother1_name,
            help="Name der ersten Person"
        )
        st.session_state.brother1_name = brother1_name
        
        brother2_name = st.text_input(
            "Name Bruder 2",
            value=st.session_state.brother2_name,
            help="Name der zweiten Person"
        )
        st.session_state.brother2_name = brother2_name
        
        st.divider()
        
        # Groq API Key für KI-Features
        st.subheader("🤖 KI-Features")
        api_key = st.text_input(
            "Groq API Key (optional)",
            type="password",
            value=st.session_state.api_key,
            help="Für intelligente Aufteilungsvorschläge"
        )
        st.session_state.api_key = api_key
        
        if api_key:
            st.success("✅ KI-Features aktiviert")
        else:
            st.info("ℹ️ Ohne API Key: Manuelle Aufteilung")
        
        st.divider()
        
        # Statistiken
        st.subheader("📊 Statistiken")
        
        if st.session_state.loaded_invoices:
            total_invoices = len(st.session_state.loaded_invoices)
            total_amount = sum(get_invoice_total(inv["data"]) for inv in st.session_state.loaded_invoices.values())
            st.metric("Rechnungen geladen", total_invoices)
            st.metric("Gesamtbetrag", f"€ {total_amount:.2f}")

def calculate_summaries():
    """Berechnet die drei Zusammenfassungstabellen"""
    # Tabelle 1: Alle Rechnungen
    all_invoices_data = []
    
    # Tabelle 2 & 3: Pro Bruder
    brother1_data = []
    brother2_data = []
    
    for invoice_name, invoice_info in st.session_state.loaded_invoices.items():
        df = invoice_info["data"]
        invoice_total = 0.0
        brother1_total = 0.0
        brother2_total = 0.0
        
        # Verarbeite jedes Produkt
        for idx, row in df.iterrows():
            product_price = float(row["preis"])
            product_key = f"{invoice_name}_{idx}"
            
            # Hole die Aufteilung
            if product_key in st.session_state.splits:
                b1_percent, b2_percent = st.session_state.splits[product_key]
            else:
                # Standard: 50/50
                b1_percent, b2_percent = 50, 50
            
            b1_amount = product_price * (b1_percent / 100)
            b2_amount = product_price * (b2_percent / 100)
            
            invoice_total += product_price
            brother1_total += b1_amount
            brother2_total += b2_amount
        
        # Füge zur Gesamttabelle hinzu
        all_invoices_data.append({
            "Rechnung": invoice_name,
            "Gesamtpreis": round(invoice_total, 2)
        })
        
        # Füge zu Bruder-Tabellen hinzu
        brother1_data.append({
            "Rechnung": invoice_name,
            f"Preis {st.session_state.brother1_name}": round(brother1_total, 2)
        })
        
        brother2_data.append({
            "Rechnung": invoice_name,
            f"Preis {st.session_state.brother2_name}": round(brother2_total, 2)
        })
    
    return (
        pd.DataFrame(all_invoices_data),
        pd.DataFrame(brother1_data),
        pd.DataFrame(brother2_data)
    )

def main():
    st.title("💰 Rechnungsaufrechnung zwischen Brüdern")
    st.write("Verwalte die Aufteilung von gemeinsamen Rechnungen")
    
    # Seitenleiste rendern
    render_sidebar()
    
    st.divider()
    
    # Lade DataManager für Persistenz
    data_manager = DataManager(PROCESSED_DIR.parent)
    
    # Lade Rechnungen
    st.session_state.loaded_invoices = load_invoices()
    
    if not st.session_state.loaded_invoices:
        st.warning("❌ Keine Rechnungen gefunden. Bitte verwende zuerst die 'Rechnungsabrechnung App' um Rechnungen zu verarbeiten.")
        st.info("💡 Tipp: Starte `streamlit run app.py` um Rechnungen hochzuladen und zu verarbeiten.")
        return
    
    st.success(f"✅ {len(st.session_state.loaded_invoices)} Rechnungen geladen")
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        ["📝 Aufteilung", "🤖 KI-Vorschläge", "📊 Statistik-Dashboard", "📈 Produktanalyse", "💵 Detailansicht", "📥 Export"]
    )
    
    with tab1:
        st.subheader("Aufteilung der Produkte")
        st.write(f"Bestimme für jedes Produkt, wer wie viel zahlt:")
        
        for invoice_name, invoice_info in st.session_state.loaded_invoices.items():
            with st.expander(f"📄 {invoice_name}"):
                df = invoice_info["data"]
                
                for idx, row in df.iterrows():
                    product_name = row["produkt"]
                    product_price = float(row["preis"])
                    product_key = f"{invoice_name}_{idx}"
                    
                    # Hole aktuelle Aufteilung
                    if product_key in st.session_state.splits:
                        b1_percent, b2_percent = st.session_state.splits[product_key]
                    else:
                        b1_percent, b2_percent = 50, 50
                    
                    col1, col2, col3 = st.columns([2, 2, 2])
                    
                    with col1:
                        st.write(f"**{product_name}** (€ {product_price:.2f})")
                    
                    with col2:
                        b1_percent_new = st.slider(
                            f"{st.session_state.brother1_name} %",
                            0, 100, b1_percent,
                            key=f"b1_{product_key}"
                        )
                    
                    with col3:
                        b2_percent_new = 100 - b1_percent_new
                        st.write(f"{st.session_state.brother2_name}: {b2_percent_new}%")
                        b1_amount = product_price * (b1_percent_new / 100)
                        b2_amount = product_price * (b2_percent_new / 100)
                        st.write(f"💶 {b1_amount:.2f}€ | {b2_amount:.2f}€")
                    
                    # Speichere Aufteilung
                    st.session_state.splits[product_key] = (b1_percent_new, b2_percent_new)
                
                st.divider()
        
        # Speichern-Button
        if st.button("💾 Aufteilung speichern & zu History hinzufügen", use_container_width=True, type="primary"):
            # Speichere alle Rechnungen mit ihren Splits zur History
            data_manager = DataManager(PROCESSED_DIR.parent)
            for invoice_name, invoice_info in st.session_state.loaded_invoices.items():
                data_manager.save_invoice({
                    "filename": invoice_name,
                    "shop": invoice_info.get("shop", "Unknown"),
                    "total_amount": get_invoice_total(invoice_info["data"]),
                    "products": invoice_info["data"].to_dict("records"),
                    "splits": st.session_state.splits
                })
            st.success("✅ Aufteilung und History gespeichert!")
    
    with tab2:
        st.subheader("🤖 KI-unterstützte Vorschläge")
        
        if not st.session_state.api_key:
            st.warning("⚠️ Bitte gib einen Groq API Key in der Seitenleiste ein um KI-Features zu nutzen")
        else:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("💡 Aufteilungsvorschläge", use_container_width=True, type="primary"):
                    with st.spinner("🤖 Analysiere Produkte mit KI..."):
                        client = initialize_groq_client(st.session_state.api_key)
                        
                        # Sammle alle Produkte
                        all_products = []
                        for inv_name, inv_info in st.session_state.loaded_invoices.items():
                            for idx, row in inv_info["data"].iterrows():
                                all_products.append({
                                    "produkt": row["produkt"],
                                    "preis": float(row["preis"])
                                })
                        
                        suggestions = suggest_split_distribution(
                            client,
                            all_products,
                            st.session_state.brother1_name,
                            st.session_state.brother2_name
                        )
                        
                        if suggestions:
                            st.session_state.ai_suggestions = suggestions
                            st.success("✅ Vorschläge generiert!")
                            st.rerun()
            
            with col2:
                if st.button("🏷️ Kategorisierung", use_container_width=True):
                    with st.spinner("🤖 Kategorisiere Produkte..."):
                        client = initialize_groq_client(st.session_state.api_key)
                        
                        all_products = []
                        for inv_name, inv_info in st.session_state.loaded_invoices.items():
                            for idx, row in inv_info["data"].iterrows():
                                all_products.append({
                                    "produkt": row["produkt"],
                                    "preis": float(row["preis"])
                                })
                        
                        categories = categorize_products(client, all_products)
                        
                        if categories:
                            st.session_state.ai_suggestions["categories"] = categories
                            st.success("✅ Kategorisierung abgeschlossen!")
            
            with col3:
                if st.button("⚠️ Preis-Check", use_container_width=True):
                    with st.spinner("🤖 Prüfe Preise auf Anomalien..."):
                        client = initialize_groq_client(st.session_state.api_key)
                        
                        all_products = []
                        for inv_name, inv_info in st.session_state.loaded_invoices.items():
                            for idx, row in inv_info["data"].iterrows():
                                all_products.append({
                                    "produkt": row["produkt"],
                                    "preis": float(row["preis"])
                                })
                        
                        anomalies = validate_prices_and_detect_anomalies(client, all_products)
                        
                        if anomalies and anomalies.get("anomalies"):
                            st.session_state.ai_suggestions["anomalies"] = anomalies
                            st.warning(f"⚠️ {len(anomalies['anomalies'])} anomale Einträge gefunden!")
                        else:
                            st.success("✅ Alle Preise wirken plausibel!")
            
            st.divider()
            
            # Zeige Ergebnisse
            if "suggestions" in st.session_state.ai_suggestions:
                st.subheader("💡 Aufteilungsvorschläge der KI")
                
                suggestions_df = pd.DataFrame(st.session_state.ai_suggestions["suggestions"])
                
                if "reasoning" in suggestions_df.columns:
                    suggestions_display = suggestions_df[["produkt", "person1_percent", "person2_percent", "reasoning"]]
                else:
                    suggestions_display = suggestions_df[["produkt", "person1_percent", "person2_percent"]]
                
                st.dataframe(suggestions_display, use_container_width=True)
                
                if st.button("✅ KI-Vorschläge übernehmen"):
                    for suggestion in st.session_state.ai_suggestions["suggestions"]:
                        for inv_name, inv_info in st.session_state.loaded_invoices.items():
                            for idx, row in inv_info["data"].iterrows():
                                if row["produkt"] == suggestion["produkt"]:
                                    product_key = f"{inv_name}_{idx}"
                                    st.session_state.splits[product_key] = (
                                        suggestion["person1_percent"],
                                        suggestion["person2_percent"]
                                    )
                    st.success("✅ Vorschläge übernommen!")
            
            if "categories" in st.session_state.ai_suggestions:
                st.subheader("🏷️ Produktkategorien")
                categories_df = pd.DataFrame(st.session_state.ai_suggestions["categories"])
                st.dataframe(categories_df, use_container_width=True)
            
            if "anomalies" in st.session_state.ai_suggestions:
                anomalies = st.session_state.ai_suggestions["anomalies"].get("anomalies", [])
                if anomalies:
                    st.subheader("⚠️ Erkannte Anomalien")
                    for anomaly in anomalies:
                        severity = anomaly.get("severity", "medium")
                        emoji = "🔴" if severity == "high" else "🟡" if severity == "medium" else "🟢"
                        st.warning(f"{emoji} **{anomaly['produkt']}**: {anomaly['issue']}")
    
    with tab3:
        st.subheader("📊 Statistik-Dashboard")
        
        # Generiere Statistiken
        stats = data_manager.get_statistics()
        product_patterns = data_manager.get_product_patterns(
            st.session_state.brother1_name,
            st.session_state.brother2_name
        )
        solo_data = data_manager.get_solo_buyer_products(
            st.session_state.brother1_name,
            st.session_state.brother2_name
        )
        
        # Render Dashboard
        render_statistics_dashboard(
            stats,
            st.session_state.brother1_name,
            st.session_state.brother2_name
        )
        
        st.divider()
        
        # Pie Chart
        render_pie_chart(
            st.session_state.brother1_name,
            st.session_state.brother2_name,
            stats["person1_total"],
            stats["person2_total"]
        )
    
    with tab4:
        st.subheader("📈 Produkt-Analyse")
        
        product_patterns = data_manager.get_product_patterns(
            st.session_state.brother1_name,
            st.session_state.brother2_name
        )
        
        # Shop-Chart
        stats = data_manager.get_statistics()
        render_shops_chart(stats.get("shops", {}))
        
        st.divider()
        
        # Produkt-Muster
        render_product_insights(
            product_patterns,
            st.session_state.brother1_name,
            st.session_state.brother2_name
        )
        
        st.divider()
        
        # Solo-Käufer Analyse - DAS IST DIE COOLE NEUE FEATURE!
        solo_data = data_manager.get_solo_buyer_products(
            st.session_state.brother1_name,
            st.session_state.brother2_name
        )
        render_solo_buyers(
            solo_data,
            st.session_state.brother1_name,
            st.session_state.brother2_name
        )
    
    with tab5:
        st.subheader("📊 Zusammenfassung")
        
        # Berechne Zusammenfassungen
        all_df, b1_df, b2_df = calculate_summaries()
        
        # Gesamttabelle
        st.write("### Alle Rechnungen")
        st.dataframe(all_df, use_container_width=True)
        all_total = all_df["Gesamtpreis"].sum()
        st.metric("Gesamtsumme", f"€ {all_total:.2f}")
        
        st.divider()
        
        # Bruder 1 Tabelle
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"### {st.session_state.brother1_name}")
            st.dataframe(b1_df, use_container_width=True)
            b1_total = b1_df[f"Preis {st.session_state.brother1_name}"].sum()
            st.metric(f"Summe {st.session_state.brother1_name}", f"€ {b1_total:.2f}")
        
        with col2:
            st.write(f"### {st.session_state.brother2_name}")
            st.dataframe(b2_df, use_container_width=True)
            b2_total = b2_df[f"Preis {st.session_state.brother2_name}"].sum()
            st.metric(f"Summe {st.session_state.brother2_name}", f"€ {b2_total:.2f}")
        
        st.divider()
        
        # Ausgleichsbetrag berechnen
        st.subheader("💸 Ausgleich")
        if b1_total > b2_total:
            ausgleich = b1_total - b2_total
            st.warning(f"{st.session_state.brother2_name} schuldet {st.session_state.brother1_name} **€ {ausgleich:.2f}**")
        elif b2_total > b1_total:
            ausgleich = b2_total - b1_total
            st.warning(f"{st.session_state.brother1_name} schuldet {st.session_state.brother2_name} **€ {ausgleich:.2f}**")
        else:
            st.success("✅ Alles ausgeglichen - beide haben gleich viel bezahlt!")
    
    with tab3:
        st.subheader("📋 Detailierte Ansicht")
        st.write("Alle Produkte mit Aufteilung:")
        
        detail_data = []
        
        for invoice_name, invoice_info in st.session_state.loaded_invoices.items():
            df = invoice_info["data"]
            
            for idx, row in df.iterrows():
                product_name = row["produkt"]
                product_price = float(row["preis"])
                product_key = f"{invoice_name}_{idx}"
                
                if product_key in st.session_state.splits:
                    b1_percent, b2_percent = st.session_state.splits[product_key]
                else:
                    b1_percent, b2_percent = 50, 50
                
                b1_amount = product_price * (b1_percent / 100)
                b2_amount = product_price * (b2_percent / 100)
                
                detail_data.append({
                    "Rechnung": invoice_name,
                    "Produkt": product_name,
                    "Gesamtpreis": round(product_price, 2),
                    f"Anteil {st.session_state.brother1_name}": f"{b1_percent}%",
                    f"{st.session_state.brother1_name}": round(b1_amount, 2),
                    f"Anteil {st.session_state.brother2_name}": f"{b2_percent}%",
                    f"{st.session_state.brother2_name}": round(b2_amount, 2)
                })
        
        detail_df = pd.DataFrame(detail_data)
        st.dataframe(detail_df, use_container_width=True)
    
    with tab6:
        st.subheader("📥 Exportieren")
        
        all_df, b1_df, b2_df = calculate_summaries()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Gesamttabelle exportieren
            csv_all = all_df.to_csv(index=False, sep=";")
            st.download_button(
                label="📥 Alle Rechnungen (CSV)",
                data=csv_all,
                file_name=f"alle_rechnungen_{datetime.now().strftime('%Y-%m-%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col2:
            # Bruder 1 exportieren
            csv_b1 = b1_df.to_csv(index=False, sep=";")
            st.download_button(
                label=f"📥 {st.session_state.brother1_name} (CSV)",
                data=csv_b1,
                file_name=f"{st.session_state.brother1_name.lower()}_{datetime.now().strftime('%Y-%m-%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col3:
            # Bruder 2 exportieren
            csv_b2 = b2_df.to_csv(index=False, sep=";")
            st.download_button(
                label=f"📥 {st.session_state.brother2_name} (CSV)",
                data=csv_b2,
                file_name=f"{st.session_state.brother2_name.lower()}_{datetime.now().strftime('%Y-%m-%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        st.divider()
        
        # Detailansicht exportieren
        st.write("### Detailansicht exportieren")
        
        detail_data = []
        for invoice_name, invoice_info in st.session_state.loaded_invoices.items():
            df = invoice_info["data"]
            
            for idx, row in df.iterrows():
                product_name = row["produkt"]
                product_price = float(row["preis"])
                product_key = f"{invoice_name}_{idx}"
                
                if product_key in st.session_state.splits:
                    b1_percent, b2_percent = st.session_state.splits[product_key]
                else:
                    b1_percent, b2_percent = 50, 50
                
                b1_amount = product_price * (b1_percent / 100)
                b2_amount = product_price * (b2_percent / 100)
                
                detail_data.append({
                    "Rechnung": invoice_name,
                    "Produkt": product_name,
                    "Gesamtpreis": round(product_price, 2),
                    f"Anteil {st.session_state.brother1_name}": f"{b1_percent}%",
                    f"{st.session_state.brother1_name}": round(b1_amount, 2),
                    f"Anteil {st.session_state.brother2_name}": f"{b2_percent}%",
                    f"{st.session_state.brother2_name}": round(b2_amount, 2)
                })
        
        detail_df = pd.DataFrame(detail_data)
        csv_detail = detail_df.to_csv(index=False, sep=";")
        
        st.download_button(
            label="📥 Alle Produkte mit Aufteilung (CSV)",
            data=csv_detail,
            file_name=f"detail_aufrechnung_{datetime.now().strftime('%Y-%m-%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

if __name__ == "__main__":
    main()
