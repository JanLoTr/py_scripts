# modules/ui/components.py - Hilfskomponenten
import streamlit as st

def get_file_icon(extension):
    """Gibt passendes Icon für Dateityp zurück"""
    ext = extension.lower()
    
    icons = {
        ".pdf": "📕",
        ".docx": "📘", ".doc": "📘",
        ".txt": "📄", ".md": "📄", ".rtf": "📄",
        ".jpg": "🖼️", ".jpeg": "🖼️", ".png": "🖼️", ".gif": "🖼️", ".webp": "🖼️",
        ".py": "🐍", ".java": "☕", ".js": "📜", ".html": "🌐", ".css": "🎨",
        ".xlsx": "📊", ".csv": "📈",
        ".zip": "📦", ".rar": "📦",
        ".mp3": "🎵", ".mp4": "🎬",
        ".exe": "⚙️", ".msi": "⚙️"
    }
    
    return icons.get(ext, "📄")

def show_file_details(file_data, index):
    """Zeigt detaillierte Dateiinformationen in Popover"""
    st.write(f"**Datei:** {file_data['filename']}")
    
    if file_data.get('original_name') and file_data['original_name'] != file_data['filename']:
        st.write(f"**Original:** {file_data['original_name']}")
    
    st.write(f"**Typ:** {file_data['extension']}")
    
    if file_data.get('size_kb', 0) > 0:
        st.write(f"**Größe:** {file_data['size_kb']} KB")
    
    # Vorschau des Inhalts
    preview = file_data["text_preview"]
    if preview and len(preview) > 50:
        st.write("**Vorschau:**")
        st.text_area(
            "Inhalt",
            preview[:500] + ("..." if len(preview) > 500 else ""),
            height=150,
            disabled=True,
            label_visibility="collapsed",
            key=f"preview_detail_{index}"
        )
    
    # Status
    status = "✅ Verarbeitet" if file_data.get("is_processed", True) else "⏸️ Nicht verarbeitet"
    st.write(f"**Status:** {status}")