# streamlit_app.py
import streamlit as st
from file_organizer import FileOrganizer

st.title("📁 Intelligenter Datei-Organizer")

# 1. Verzeichnisauswahl
input_dir = st.text_input("Quellverzeichnis", value="~/Downloads")
output_dir = st.text_input("Zielverzeichnis", value="~/Documents/Organized")

# 2. Einstellungen
col1, col2 = st.columns(2)
with col1:
    clean_names = st.checkbox("Dateinamen bereinigen", True)
    interactive = st.checkbox("Interaktive Bestätigung", True)
    
with col2:
    ai_enabled = st.checkbox("KI-Unterstützung", True)
    preserve_structure = st.checkbox("Ordnerstruktur erhalten", True)

# 3. Analyse starten
if st.button("🔍 Dateien analysieren"):
    with st.spinner("Analysiere Dateien..."):
        organizer = FileOrganizer({
            'input_dir': input_dir,
            'output_dir': output_dir,
            'clean_filenames': clean_names,
            'interactive': interactive,
            'ai_provider': 'openai' if ai_enabled else None,
            'preserve_folder_structure': preserve_structure
        })
        
        analysis = organizer.analyze_files()
        
    # Ergebnisse anzeigen
    st.success(f"{analysis['stats']['processed']} Dateien analysiert")
    
    # KI-Vorschläge
    if ai_enabled and analysis.get('ai_suggestions'):
        st.subheader("🤖 KI-Vorschläge")
        categories = {}
        for suggestion in analysis['ai_suggestions']:
            cat = suggestion['suggested_category']
            categories[cat] = categories.get(cat, 0) + 1
        
        for cat, count in categories.items():
            st.write(f"**{cat}** ({count} Dateien)")