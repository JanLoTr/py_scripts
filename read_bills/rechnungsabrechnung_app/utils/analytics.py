"""
Statistik-Dashboard und Visualisierungen
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, List, Optional
from datetime import datetime, timedelta

def render_statistics_dashboard(stats: Dict, person1_name: str, person2_name: str):
    """Rendert das Hauptstatistik-Dashboard"""
    
    if stats["total_invoices"] == 0:
        st.info("📊 Noch keine Rechnungen vorhanden für Statistiken")
        return
    
    # Top-Level Metriken
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📋 Rechnungen", stats["total_invoices"])
    
    with col2:
        st.metric("💰 Gesamtausgaben", f"€ {stats['total_spent']:.2f}")
    
    with col3:
        st.metric("📈 Ø pro Rechnung", f"€ {stats['average_per_invoice']:.2f}")
    
    with col4:
        if stats["total_spent"] > 0:
            diff = stats["person1_total"] - stats["person2_total"]
            st.metric("💸 Differenz", f"€ {abs(diff):.2f}")

def render_pie_chart(person1_name: str, person2_name: str, person1_total: float, person2_total: float):
    """Rendert Pie-Chart: Wer zahlt wie viel?"""
    
    st.subheader("👥 Wer zahlt wie viel?")
    
    if person1_total == 0 and person2_total == 0:
        st.info("Keine Aufteilungsdaten vorhanden")
        return
    
    total = person1_total + person2_total
    
    fig = go.Figure(data=[go.Pie(
        labels=[person1_name, person2_name],
        values=[person1_total, person2_total],
        marker=dict(colors=["#1f77b4", "#ff7f0e"]),
        textposition="inside",
        textinfo="label+percent+value"
    )])
    
    fig.update_layout(
        title=f"Ausgaben-Verteilung (Total: € {total:.2f})",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Differenz berechnen
    if person1_total > person2_total:
        diff = person1_total - person2_total
        st.warning(f"💸 {person2_name} schuldet {person1_name} **€ {diff:.2f}**")
    elif person2_total > person1_total:
        diff = person2_total - person1_total
        st.warning(f"💸 {person1_name} schuldet {person2_name} **€ {diff:.2f}**")
    else:
        st.success("✅ Perfekt ausgeglichen!")

def render_shops_chart(shops: Dict):
    """Rendert Shop-Frequenz & Ausgaben"""
    
    st.subheader("🏪 Einkaufsläden")
    
    if not shops:
        st.info("Keine Shop-Daten vorhanden")
        return
    
    shop_data = []
    for shop_name, shop_info in shops.items():
        shop_data.append({
            "Shop": shop_name,
            "Besuche": shop_info["count"],
            "Gesamtausgaben": shop_info["total"]
        })
    
    df_shops = pd.DataFrame(shop_data)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Balkendiagramm - Besuche
        fig1 = px.bar(
            df_shops,
            x="Shop",
            y="Besuche",
            title="Besuche pro Shop",
            color="Besuche",
            color_continuous_scale="Blues"
        )
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        # Balkendiagramm - Ausgaben
        fig2 = px.bar(
            df_shops,
            x="Shop",
            y="Gesamtausgaben",
            title="Ausgaben pro Shop",
            color="Gesamtausgaben",
            color_continuous_scale="Oranges"
        )
        fig2.update_yaxes(title_text="€")
        st.plotly_chart(fig2, use_container_width=True)
    
    # Tabelle
    st.dataframe(df_shops.sort_values("Gesamtausgaben", ascending=False), use_container_width=True)

def render_product_insights(product_patterns: Dict, person1_name: str, person2_name: str):
    """Rendert Produkt-Analyse"""
    
    st.subheader("📦 Produkt-Muster")
    
    if not product_patterns:
        st.info("Noch keine Muster erkannt")
        return
    
    # Top Produkte nach Häufigkeit
    top_products = sorted(
        product_patterns.items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )[:10]
    
    product_names = [p[0] for p in top_products]
    counts = [p[1]["count"] for p in top_products]
    
    fig = px.bar(
        x=product_names,
        y=counts,
        title="Top 10 - Meist gekaufte Produkte",
        labels={"x": "Produkt", "y": "Häufigkeit"},
        color=counts,
        color_continuous_scale="Viridis"
    )
    fig.update_xaxes(tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)
    
    # Muster-Tabelle
    st.write("### 🔍 Aufteilungs-Muster")
    
    pattern_data = []
    for product_name, pattern in sorted(
        product_patterns.items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )[:15]:
        
        total = pattern["count"]
        p1_ratio = pattern["person1_100"] / total * 100 if total > 0 else 0
        p2_ratio = pattern["person2_100"] / total * 100 if total > 0 else 0
        split_ratio = pattern["split_50_50"] / total * 100 if total > 0 else 0
        
        # Bestimme Muster
        if p1_ratio >= 80:
            pattern_type = f"🔴 {person1_name} (100%)"
        elif p2_ratio >= 80:
            pattern_type = f"🔵 {person2_name} (100%)"
        elif split_ratio == 100:
            pattern_type = "🤝 Immer 50/50"
        else:
            pattern_type = f"🔀 Gemischt ({p1_ratio:.0f}/{100-p1_ratio:.0f})"
        
        pattern_data.append({
            "Produkt": product_name,
            "Mal gekauft": total,
            "Muster": pattern_type,
            "Preis": f"€{pattern['price_range']['min']:.2f}-{pattern['price_range']['max']:.2f}" 
                    if pattern['price_range'] else "N/A"
        })
    
    st.dataframe(pattern_data, use_container_width=True)

def render_solo_buyers(solo_data: Dict, person1_name: str, person2_name: str):
    """Rendert Solo-Käufer Analyse"""
    
    st.subheader("🎯 Persönliche Produkte")
    st.write("Produkte die eine Person meistens für sich allein kauft (>80%):")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"### 🔴 {person1_name}'s Solo-Produkte")
        p1_solos = solo_data.get("person1_solo", [])
        
        if p1_solos:
            for solo in sorted(p1_solos, key=lambda x: x["solo_ratio"], reverse=True):
                st.write(f"• **{solo['produkt']}** ({solo['solo_ratio']:.0f}% allein, {solo['mal_gekauft']}x)")
        else:
            st.info("Keine persönlichen Produkte")
    
    with col2:
        st.write(f"### 🔵 {person2_name}'s Solo-Produkte")
        p2_solos = solo_data.get("person2_solo", [])
        
        if p2_solos:
            for solo in sorted(p2_solos, key=lambda x: x["solo_ratio"], reverse=True):
                st.write(f"• **{solo['produkt']}** ({solo['solo_ratio']:.0f}% allein, {solo['mal_gekauft']}x)")
        else:
            st.info("Keine persönlichen Produkte")
    
    # Insights
    st.divider()
    st.write("### 💡 Erkenntnisse")
    insights = solo_data.get("insights", [])
    
    if insights:
        for insight in insights[:10]:  # Top 10
            st.write(insight)
    else:
        st.info("Noch nicht genug Daten für Erkenntnisse")
