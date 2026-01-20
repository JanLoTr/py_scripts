# modules/ui/downloads.py - Download-Funktionalität
import streamlit as st
import json
import time
from modules.state import get_state, update_state

def render_persistent_downloads():
    """Rendert persistente Download-Buttons"""
    if not get_state('show_download_buttons', False):
        return
    
    st.markdown("---")
    st.subheader("💾 Ergebnisse herunterladen")
    
    col1, col2 = st.columns(2)
    
    with col1:
        categories_json = get_state('download_categories_json')
        categories_filename = get_state('download_categories_filename', "kategorien.json")
        
        if categories_json:
            st.download_button(
                label="📥 Kategorien als JSON",
                data=categories_json,
                file_name=categories_filename,
                mime="application/json",
                key="persistent_download_categories",
                use_container_width=True
            )
        else:
            st.button(
                "📥 Kategorien (nicht verfügbar)",
                disabled=True,
                use_container_width=True
            )
    
    with col2:
        files_json = get_state('download_files_json')
        files_filename = get_state('download_files_filename', "dateiliste.json")
        
        if files_json:
            st.download_button(
                label="📥 Dateiliste als JSON",
                data=files_json,
                file_name=files_filename,
                mime="application/json",
                key="persistent_download_files",
                use_container_width=True
            )
        else:
            st.button(
                "📥 Dateiliste (nicht verfügbar)",
                disabled=True,
                use_container_width=True
            )
    
    # Umbenannte Dateien
    renamed_files = get_state('renamed_files', [])
    if renamed_files:
        with st.expander(f"📝 Umbenannte Dateien ({len(renamed_files)})", expanded=False):
            for old_name, new_name in renamed_files[:8]:
                col_old, col_arrow, col_new = st.columns([4, 1, 4])
                
                with col_old:
                    st.write(f"`{old_name[:40]}{'...' if len(old_name) > 40 else ''}`")
                
                with col_arrow:
                    st.write("→")
                
                with col_new:
                    st.write(f"`{new_name[:40]}{'...' if len(new_name) > 40 else ''}`")
            
            if len(renamed_files) > 8:
                st.info(f"Und {len(renamed_files) - 8} weitere...")
            
            # Download der Umbenennungsliste
            renamed_data = json.dumps(renamed_files, indent=2, ensure_ascii=False)
            st.download_button(
                label="📥 Umbenennungsliste herunterladen",
                data=renamed_data,
                file_name=f"umbenennungen_{time.strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key="download_renamed",
                use_container_width=True
            )

def prepare_download_data(categories_data, files_data):
    """Bereitet Download-Daten vor"""
    if categories_data:
        categories_json = json.dumps(categories_data, indent=2, ensure_ascii=False)
        categories_filename = f"kategorien_{time.strftime('%Y%m%d_%H%M%S')}.json"
        
        update_state('download_categories_json', categories_json)
        update_state('download_categories_filename', categories_filename)
    
    if files_data:
        files_json = json.dumps(files_data, indent=2, ensure_ascii=False)
        files_filename = f"dateiliste_{time.strftime('%Y%m%d_%H%M%S')}.json"
        
        update_state('download_files_json', files_json)
        update_state('download_files_filename', files_filename)
    
    update_state('show_download_buttons', True)