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
        'skip_encrypted_zips': True,
        'move_executables': True,
        'api_key': "",
        'detail_level': "mittel",
        'max_files': 50
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