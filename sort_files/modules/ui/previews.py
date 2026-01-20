# modules/ui/previews.py - Vorschauen
import streamlit as st
from modules.state import get_state
from .components import get_file_icon, show_file_details

def render_previews(file_processor):
    """Rendert Datei- und Kategorievorschauen"""
    files_data = get_state('files_data')
    categories = get_state('categories')
    
    if files_data:
        render_file_preview_compact(files_data["files"])
    
    if categories:
        render_categories_preview(categories)

def render_file_preview_compact(files):
    """Rendert KOMPAKTE Dateivorschau"""
    if not files or len(files) == 0:
        return
    
    with st.expander(f"📋 Dateivorschau ({len(files)} Dateien)", expanded=False):
        # Statistik
        processed = sum(1 for f in files if f.get("is_processed", True))
        not_processed = len(files) - processed
        
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        
        with col_stat1:
            st.metric("Gesamt", len(files))
        
        with col_stat2:
            st.metric("Verarbeitet", processed, delta=f"+{processed}")
        
        with col_stat3:
            st.metric("Nicht verarbeitet", not_processed, delta=f"-{not_processed}" if not_processed > 0 else "0")
        
        st.markdown("---")
        
        # Dateiliste mit "Mehr ansehen" Dropdown
        for i, file_data in enumerate(files[:15]):
            with st.container():
                col_icon, col_name, col_info, col_action = st.columns([0.5, 3, 2, 1])
                
                with col_icon:
                    ext = file_data["extension"]
                    icon = get_file_icon(ext)
                    status = "✅" if file_data.get("is_processed", True) else "⏸️"
                    st.write(f"{status} {icon}")
                
                with col_name:
                    display_name = file_data['filename']
                    if len(display_name) > 30:
                        display_name = display_name[:27] + "..."
                    
                    if file_data.get('clean_name') != file_data['filename']:
                        clean_display = file_data['clean_name']
                        if len(clean_display) > 20:
                            clean_display = clean_display[:17] + "..."
                        st.write(f"**{display_name}**")
                        st.caption(f"→ {clean_display}")
                    else:
                        st.write(f"**{display_name}**")
                
                with col_info:
                    ext_display = ext if ext else "(ohne)"
                    size_info = f"{file_data.get('size_kb', 0)} KB" if file_data.get('size_kb', 0) > 0 else ""
                    st.write(f"`{ext_display}`")
                    if size_info:
                        st.caption(size_info)
                
                with col_action:
                    with st.popover("🔍"):
                        show_file_details(file_data, i)
        
        # "Weitere Dateien anzeigen" Option
        if len(files) > 15:
            st.markdown("---")
            if st.button(f"📄 Weitere {len(files) - 15} Dateien anzeigen...", key="show_more_files"):
                for i, file_data in enumerate(files[15:30]):
                    with st.container():
                        col_icon2, col_name2, col_info2 = st.columns([0.5, 3, 2])
                        
                        with col_icon2:
                            ext = file_data["extension"]
                            icon = get_file_icon(ext)
                            status = "✅" if file_data.get("is_processed", True) else "⏸️"
                            st.write(f"{status} {icon}")
                        
                        with col_name2:
                            display_name = file_data['filename']
                            if len(display_name) > 25:
                                display_name = display_name[:22] + "..."
                            st.write(display_name)
                        
                        with col_info2:
                            ext_display = ext if ext else "(ohne)"
                            st.write(f"`{ext_display}`")

def render_categories_preview(categories):
    """Rendert Kategorievorschau"""
    if not categories or "results" not in categories:
        return
    
    with st.expander("📊 KI-Kategorisierung", expanded=False):
        # Kategorie-Statistik
        cat_stats = {}
        confidences = []
        
        for item in categories["results"]:
            cat = item["category"]
            cat_stats[cat] = cat_stats.get(cat, 0) + 1
            if "confidence" in item:
                confidences.append(item["confidence"])
        
        st.write(f"**{len(cat_stats)} Kategorien erkannt**")
        
        # Durchschnitts-Confidence
        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            st.write(f"Durchschnittliche Confidence: **{avg_conf:.1%}**")
        
        # Top Kategorien
        top_cats = sorted(cat_stats.items(), key=lambda x: x[1], reverse=True)
        
        col_cat1, col_cat2 = st.columns(2)
        
        with col_cat1:
            for cat, count in top_cats[:len(top_cats)//2]:
                st.write(f"• **{cat}**: {count} Dateien")
        
        with col_cat2:
            for cat, count in top_cats[len(top_cats)//2:]:
                st.write(f"• **{cat}**: {count} Dateien")
        
        # Beispiele
        with st.expander("📝 Beispieldateien pro Kategorie"):
            for cat, count in top_cats[:8]:
                with st.expander(f"{cat} ({count} Dateien)"):
                    examples = [
                        item["filename"] 
                        for item in categories["results"] 
                        if item["category"] == cat
                    ][:5]
                    
                    for ex in examples:
                        st.write(f"• {ex}")