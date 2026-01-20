# modules/file_handling.py - Dateiverarbeitung
import os
import json
import shutil
import tempfile
import zipfile
import io
import re
import time
from pathlib import Path
import streamlit as st

# Externe Bibliotheken
import pdfplumber
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
from docx import Document

class FileProcessor:
    """Klasse für Dateiverarbeitungsoperationen"""
    
    def __init__(self):
        self.temp_dir = None
        self.not_processed_dir = None
        self.executables_dir = None
        
    # -------------------- Temporäre Verzeichnisse --------------------
    def create_temp_directory(self):
        """Erstellt temporäres Verzeichnis"""
        if st.session_state.temp_dir is None:
            temp_dir = tempfile.mkdtemp(prefix="ki_sort_")
            st.session_state.temp_dir = Path(temp_dir)
            self.temp_dir = st.session_state.temp_dir
            
            # Erstelle Unterverzeichnisse für nicht verarbeitete Dateien
            self.not_processed_dir = self.temp_dir / "_nicht_verarbeitet"
            self.executables_dir = self.not_processed_dir / "ausführbare_datein"
            
            self.not_processed_dir.mkdir(exist_ok=True)
            self.executables_dir.mkdir(exist_ok=True)
            
        return st.session_state.temp_dir
    
    def cleanup_temp_directory(self):
        """Räumt temporäres Verzeichnis auf"""
        if st.session_state.temp_dir and st.session_state.temp_dir.exists():
            try:
                shutil.rmtree(st.session_state.temp_dir)
            except:
                pass
            st.session_state.temp_dir = None
            self.temp_dir = None
            self.not_processed_dir = None
            self.executables_dir = None
    
    # -------------------- ZIP Verarbeitung --------------------
    def safe_extract_zip(self, zip_bytes, extract_to):
        """
        Extrahiert ZIP sicher, überspringt verschlüsselte Dateien
        """
        extracted_files = []
        skipped_files = []
        
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zip_ref:
                for zip_info in zip_ref.infolist():
                    # Prüfe auf Verschlüsselung
                    if zip_info.flag_bits & 0x1:
                        if st.session_state.skip_encrypted_zips:
                            skipped_files.append(zip_info.filename)
                            continue
                    
                    try:
                        zip_ref.extract(zip_info, extract_to)
                        extracted_files.append(zip_info.filename)
                    except RuntimeError as e:
                        if "encrypted" in str(e):
                            skipped_files.append(zip_info.filename)
                        else:
                            st.warning(f"Konnte {zip_info.filename} nicht extrahieren: {e}")
                    except Exception as e:
                        st.warning(f"Fehler bei {zip_info.filename}: {e}")
            
            return extracted_files, skipped_files
            
        except zipfile.BadZipFile:
            st.error("Beschädigte ZIP-Datei")
            return [], []
        except Exception as e:
            st.error(f"ZIP-Fehler: {e}")
            return [], []
    
    # -------------------- Dateinamen Bereinigung --------------------
    def clean_filename(self, filename):
        """Bereinigt Dateinamen von Sonderzeichen"""
        if not st.session_state.clean_filenames:
            return filename
        
        # Entferne problematische Zeichen
        cleaned = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # Ersetze Umlaute
        replacements = {
            'ä': 'ae', 'ö': 'oe', 'ü': 'ue',
            'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
            'ß': 'ss'
        }
        
        for old, new in replacements.items():
            cleaned = cleaned.replace(old, new)
        
        # Bereinige
        cleaned = re.sub(r'_+', '_', cleaned)
        cleaned = cleaned.strip('._')
        
        return cleaned if cleaned else "unnamed_file"
    
    def rename_files_in_directory(self, directory):
        """Benennt alle Dateien im Verzeichnis um"""
        renamed = []
        for file_path in Path(directory).rglob("*"):
            if file_path.is_file():
                old_name = file_path.name
                new_name = self.clean_filename(old_name)
                
                if old_name != new_name:
                    new_path = file_path.parent / new_name
                    counter = 1
                    while new_path.exists():
                        name_parts = new_name.rsplit('.', 1)
                        if len(name_parts) == 2:
                            new_name_with_counter = f"{name_parts[0]}_{counter}.{name_parts[1]}"
                        else:
                            new_name_with_counter = f"{new_name}_{counter}"
                        new_path = file_path.parent / new_name_with_counter
                        counter += 1
                    
                    try:
                        file_path.rename(new_path)
                        renamed.append((old_name, new_path.name))
                    except Exception as e:
                        st.warning(f"Konnte {old_name} nicht umbenennen: {e}")
        
        st.session_state.renamed_files = renamed
        return renamed
    
    # -------------------- Dateiinhalt Extraktion --------------------
    def extract_text_from_file(self, file_path):
        """Extrahiert Text aus verschiedenen Dateitypen"""
        try:
            ext = file_path.suffix.lower()
            
            # Prüfe auf ausführbare Dateien
            executable_extensions = ['.exe', '.msi', '.dll', '.bat', '.cmd', '.ps1', '.sh']
            if ext in executable_extensions:
                # Verschiebe in ausführbare Dateien Ordner
                if st.session_state.move_executables and self.executables_dir:
                    try:
                        target_path = self.executables_dir / file_path.name
                        shutil.copy2(file_path, target_path)
                    except:
                        pass
                return f"AUSFÜHRBARE DATEI - NICHT VERARBEITET ({ext})"
            
            # Prüfe auf sehr große Dateien (>50MB)
            file_size = file_path.stat().st_size
            if file_size > 50 * 1024 * 1024:
                # Verschiebe in nicht verarbeitet Ordner
                if self.not_processed_dir:
                    try:
                        target_path = self.not_processed_dir / file_path.name
                        shutil.copy2(file_path, target_path)
                    except:
                        pass
                return f"DATEI ZU GROSS - NICHT VERARBEITET ({file_size//(1024*1024)} MB)"
            
            # Programmiersprachen
            code_extensions = [".py", ".java", ".cpp", ".c", ".js", ".html", ".css"]
            if ext in code_extensions:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(3000)
                    return f"Code ({ext[1:].upper()}):\n{content}"
            
            # PDF
            elif ext == ".pdf":
                try:
                    text = ""
                    with pdfplumber.open(file_path) as pdf:
                        for i, page in enumerate(pdf.pages[:2]):
                            page_text = page.extract_text()
                            if page_text:
                                text += f"\n--- Seite {i+1} ---\n{page_text[:800]}"
                    return text.strip() or "PDF (kein Text)"
                except:
                    return "PDF-Datei"
            
            # Word
            elif ext == ".docx":
                try:
                    doc = Document(file_path)
                    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                    return "\n".join(paragraphs[:10])
                except:
                    return "Word-Dokument"
            
            # Textdateien
            elif ext in [".txt", ".md", ".csv", ".json"]:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read(2000).strip()
            
            # Bilder
            elif ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"]:
                try:
                    img = Image.open(file_path)
                    if file_size < 2 * 1024 * 1024:  # < 2 MB
                        try:
                            text = pytesseract.image_to_string(img)
                            if text.strip():
                                return f"Bild mit Text:\n{text[:500]}"
                        except:
                            pass
                    return f"Bilddatei ({ext})"
                except:
                    return f"Bilddatei ({ext})"
            
            # Andere unterstützte Formate
            elif ext in [".xlsx", ".pptx", ".mp3", ".mp4", ".zip"]:
                return f"Datei ({ext})"
            
            # Nicht unterstützte Formate
            else:
                # Verschiebe in nicht verarbeitet Ordner
                if self.not_processed_dir:
                    try:
                        target_path = self.not_processed_dir / file_path.name
                        shutil.copy2(file_path, target_path)
                    except:
                        pass
                return f"NICHT UNTERSTÜTZT - NICHT VERARBEITET ({ext})"
                
        except Exception as e:
            # Verschiebe fehlerhafte Dateien
            if self.not_processed_dir:
                try:
                    target_path = self.not_processed_dir / file_path.name
                    shutil.copy2(file_path, target_path)
                except:
                    pass
            return f"FEHLER BEIM LESEN: {str(e)[:100]}"
    
    # -------------------- Batch Verarbeitung --------------------
    def extract_all_files(self, input_dir, max_files=50):
        """Extrahiert alle Dateien im Verzeichnis"""
        files_data = []
        file_types = {}
        skipped_files = []
        
        input_path = Path(input_dir)
        
        # Finde alle Dateien
        all_files = []
        for file_path in input_path.rglob("*"):
            if file_path.is_file():
                all_files.append(file_path)
        
        # Begrenze auf max_files
        all_files = all_files[:max_files]
        
        # Fortschrittsanzeige
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, file_path in enumerate(all_files):
            # Fortschritt
            progress = (idx + 1) / len(all_files)
            progress_bar.progress(progress)
            display_name = file_path.name[:30] + "..." if len(file_path.name) > 30 else file_path.name
            status_text.text(f"Verarbeite: {display_name} ({idx+1}/{len(all_files)})")
            
            try:
                # Text extrahieren
                text = self.extract_text_from_file(file_path)
                
                # Statistik
                ext = file_path.suffix.lower() or "(keine Endung)"
                file_types[ext] = file_types.get(ext, 0) + 1
                
                # Prüfe ob Datei verarbeitet wurde
                is_processed = "NICHT VERARBEITET" not in text and "AUSFÜHRBARE DATEI" not in text
                
                files_data.append({
                    "filename": file_path.name,
                    "clean_name": self.clean_filename(file_path.name),
                    "path": str(file_path),
                    "extension": ext,
                    "size_kb": file_path.stat().st_size // 1024,
                    "is_processed": is_processed,
                    "text_preview": text[:1000] if isinstance(text, str) else str(text)[:1000]
                })
                
            except Exception as e:
                skipped_files.append(f"{file_path.name} (Fehler: {str(e)[:50]})")
        
        progress_bar.empty()
        status_text.empty()
        
        # Ergebnis
        result = {
            "metadata": {
                "total_files": len(files_data),
                "file_types": dict(sorted(file_types.items())),
                "skipped_files": skipped_files,
                "processed_date": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "files": files_data
        }
        
        return result
    
    # -------------------- Dateiorganisation --------------------
    def organize_files(self, files_data, categories, source_dir, target_dir):
        """Organisiert Dateien nach Kategorien"""
        stats = {
            'moved': 0,
            'not_found': 0,
            'errors': 0,
            'categories': {}
        }
        
        target_path = Path(target_dir)
        target_path.mkdir(parents=True, exist_ok=True)
        
        # Dateizuordnung
        file_map = {f["filename"]: f for f in files_data}
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, item in enumerate(categories["results"]):
            filename = item["filename"]
            category = item["category"]
            
            # Überspringe nicht verarbeitete Dateien
            if filename in file_map and not file_map[filename].get("is_processed", True):
                continue
            
            # Kategorie bereinigen
            safe_category = re.sub(r'[<>:"/\\|?*]', '-', category)
            safe_category = safe_category.replace('/', '-')
            
            progress = (i + 1) / len(categories["results"])
            progress_bar.progress(progress)
            status_text.text(f"Sortiere: {filename[:40]}...")
            
            if safe_category not in stats['categories']:
                stats['categories'][safe_category] = 0
            
            source_path = Path(source_dir) / filename
            
            try:
                if source_path.exists():
                    target_category_dir = target_path / safe_category
                    target_category_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Verwende bereinigten Namen
                    if filename in file_map and "clean_name" in file_map[filename]:
                        target_name = file_map[filename]["clean_name"]
                    else:
                        target_name = self.clean_filename(filename)
                    
                    target_file = target_category_dir / target_name
                    
                    # Konflikt vermeiden
                    counter = 1
                    while target_file.exists():
                        name_parts = target_name.rsplit('.', 1)
                        if len(name_parts) == 2:
                            target_name = f"{name_parts[0]}_{counter}.{name_parts[1]}"
                        else:
                            target_name = f"{target_name}_{counter}"
                        target_file = target_category_dir / target_name
                        counter += 1
                    
                    shutil.move(str(source_path), str(target_file))
                    stats['moved'] += 1
                    stats['categories'][safe_category] += 1
                else:
                    stats['not_found'] += 1
                    
            except Exception as e:
                stats['errors'] += 1
                st.warning(f"Fehler bei {filename}: {str(e)[:100]}")
        
        progress_bar.empty()
        status_text.empty()
        
        return stats
    
    # -------------------- Helper Functions --------------------
    def copy_not_processed_files(self, target_base_dir):
        """Kopiert nicht verarbeitete Dateien in Zielverzeichnis"""
        if not self.not_processed_dir or not self.not_processed_dir.exists():
            return 0
        
        target_dir = Path(target_base_dir) / "_nicht_verarbeitet"
        target_dir.mkdir(parents=True, exist_ok=True)
        
        copied_count = 0
        
        # Kopiere alle Dateien aus nicht_verarbeitet
        for file_path in self.not_processed_dir.rglob("*"):
            if file_path.is_file():
                try:
                    relative_path = file_path.relative_to(self.not_processed_dir)
                    target_path = target_dir / relative_path
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file_path, target_path)
                    copied_count += 1
                except:
                    pass
        
        return copied_count