# modules/state.py - Session State Management
import streamlit as st

def init_session_state():
    """Initialisiert alle Session State Variablen"""
    defaults = {
        'files_data': None,
        'categories': None,
        'processing_step': 1,
        'temp_dir': None,
        'renamed_files': [],
        'clean_filenames': True,
        'replace_umlauts': False,  # Neue Option: Umlaute ersetzen?
        'skip_encrypted_zips': True,
        'move_executables': True,
        'api_key': "",
        'detail_level': "mittel",
        'max_files': 50,
        # Download-Daten persistieren
        'download_categories_json': None,
        'download_files_json': None,
        'download_categories_filename': "kategorien.json",
        'download_files_filename': "dateiliste.json",
        'show_download_buttons': False
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def update_state(key, value):
    """Aktualisiert einen Session State Wert"""
    st.session_state[key] = value

def get_state(key, default=None):
    """Holt einen Session State Wert"""
    return st.session_state.get(key, default)

def prepare_download_data(categories_data, files_data):
    """Bereitet Download-Daten vor und speichert sie im Session State"""
    if categories_data:
        st.session_state.download_categories_json = json.dumps(categories_data, indent=2, ensure_ascii=False)
        st.session_state.download_categories_filename = "kategorien_" + time.strftime("%Y%m%d_%H%M%S") + ".json"
    
    if files_data:
        st.session_state.download_files_json = json.dumps(files_data, indent=2, ensure_ascii=False)
        st.session_state.download_files_filename = "dateiliste_" + time.strftime("%Y%m%d_%H%M%S") + ".json"
    
    st.session_state.show_download_buttons = True