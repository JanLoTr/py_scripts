"""
Produkttabellen-Komponente
"""
import streamlit as st
import pandas as pd

def render_product_table(products: list):
    """
    Rendert eine Tabelle mit Produkten
    
    Args:
        products: Liste von Produkten
    """
    st.subheader("📦 Rechnungspositionen")
    
    if not products or len(products) == 0:
        st.info("Keine Produkte gefunden")
        return
    
    # Konvertiere zu DataFrame
    df = pd.DataFrame(products)
    
    # Zeige Tabelle an
    st.dataframe(df, use_container_width=True)
    
    # Zusammenfassung
    if "amount" in df.columns:
        total = df["amount"].sum()
        st.metric("Gesamtbetrag", f"€ {total:.2f}")

def add_product_row():
    """
    Rendert ein Formular zum Hinzufügen einer Produktreihe
    """
    st.subheader("➕ Position hinzufügen")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        description = st.text_input("Beschreibung", key="desc_input")
    
    with col2:
        quantity = st.number_input("Menge", value=1, min_value=0, key="qty_input")
    
    with col3:
        unit_price = st.number_input("Einzelpreis", value=0.0, min_value=0.0, key="price_input")
    
    with col4:
        if st.button("Hinzufügen", key="add_button"):
            amount = quantity * unit_price
            return {
                "description": description,
                "quantity": quantity,
                "unit_price": unit_price,
                "amount": amount
            }
    
    return None
