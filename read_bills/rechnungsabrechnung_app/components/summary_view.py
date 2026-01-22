"""
Zusammenfassungs-Ansicht Komponente
"""
import streamlit as st
import pandas as pd

def render_summary(invoice_data: dict, products: list):
    """
    Rendert die Zusammenfassung der Rechnung
    
    Args:
        invoice_data: Rechnungsdaten
        products: Liste von Produkten
    """
    st.subheader("📊 Zusammenfassung")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Anzahl Positionen", len(products) if products else 0)
    
    with col2:
        if products and "amount" in products[0]:
            subtotal = sum(p.get("amount", 0) for p in products)
            st.metric("Zwischensumme", f"€ {subtotal:.2f}")
    
    with col3:
        total_amount = invoice_data.get("amount", 0)
        st.metric("Gesamtbetrag", f"€ {total_amount:.2f}")
    
    with col4:
        st.metric("Status", invoice_data.get("status", "Unbekannt"))

def render_export_options():
    """
    Rendert Export-Optionen
    """
    st.subheader("💾 Exportieren")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("📥 Als CSV exportieren", key="export_csv"):
            st.info("CSV Export wird vorbereitet...")
    
    with col2:
        if st.button("📊 Als Excel exportieren", key="export_excel"):
            st.info("Excel Export wird vorbereitet...")
    
    with col3:
        if st.button("📄 Als PDF exportieren", key="export_pdf"):
            st.info("PDF Export wird vorbereitet...")
    
    with col4:
        if st.button("📋 Als JSON exportieren", key="export_json"):
            st.info("JSON Export wird vorbereitet...")

def render_statistics(invoices_data: list):
    """
    Rendert Statistiken
    
    Args:
        invoices_data: Liste von Rechnungsdaten
    """
    st.subheader("📈 Statistiken")
    
    if not invoices_data or len(invoices_data) == 0:
        st.info("Keine Daten verfügbar")
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Verarbeitete Rechnungen", len(invoices_data))
    
    with col2:
        if all(isinstance(inv, dict) and "amount" in inv for inv in invoices_data):
            total = sum(inv.get("amount", 0) for inv in invoices_data)
            st.metric("Gesamtumsatz", f"€ {total:.2f}")
    
    with col3:
        st.metric("Durchschnittsbetrag", "€ 0.00")
