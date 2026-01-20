# modules/file_handling.py - Dateiverarbeitung (korrigierte Namensbereinigung)
import os
import json
import shutil
import tempfile
import zipfile
import io
import re
import time
import unicodedata
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
    
    # -------------------- VERBESSERTE DATEINAMEN BEREINIGUNG --------------------
    def clean_filename(self, filename):
        """Bereinigt Dateinamen von Sonderzeichen - ROBUSTE Version"""
        if not st.session_state.clean_filenames:
            return filename
        
        # Fall 1: Kodierungsprobleme (wie "TrauÃŸnigg")
        if 'Ã' in filename:
            try:
                # Versuche UTF-8 Reparatur
                filename_bytes = filename.encode('latin-1')
                filename = filename_bytes.decode('utf-8')
            except:
                pass
        
        # Unicode normalisieren
        filename = unicodedata.normalize('NFKC', filename)
        
        # Spezielle Ersetzungen für häufige Kodierungsprobleme
        replacements = [
            ('ÃŸ', 'ß'),  # UTF-8 Problem
            ('Ã¼', 'ü'),
            ('Ã¤', 'ä'),
            ('Ã¶', 'ö'),
            ('Ãœ', 'Ü'),
            ('Ã„', 'Ä'),
            ('Ã–', 'Ö'),
            ('Ã©', 'é'),
            ('Ã¨', 'è'),
            ('Ã¡', 'á'),
            ('Ã ', 'à'),
            ('Ã±', 'ñ'),
            ('Ã§', 'ç'),
            ('â‚¬', '€'),
            ('â€š', ','),
            ('â€ž', '"'),
            ('â€œ', '"'),
            ('â€', "'"),
            ('â€“', '-'),
            ('â€”', '-'),
            ('â€¢', '•'),
            ('â€¦', '…'),
        ]
        
        for old, new in replacements:
            filename = filename.replace(old, new)
        
        # Standard Sonderzeichen ersetzen
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # Ersetze Umlaute (optional, kann deaktiviert werden)
        if st.session_state.get('replace_umlauts', True):
            umlaut_replacements = {
                'ä': 'ae', 'ö': 'oe', 'ü': 'ue',
                'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
                'ß': 'ss',
            }
            for old, new in umlaut_replacements.items():
                filename = filename.replace(old, new)
        
        # Entferne nicht-druckbare Zeichen
        filename = ''.join(char for char in filename if char.isprintable())
        
        # Mehrfache Unterstriche reduzieren
        filename = re.sub(r'_+', '_', filename)
        
        # Entferne führende/nachgestellte Punkte und Unterstriche
        filename = filename.strip('._ ')
        
        # Stelle sicher, dass der Name nicht leer ist
        if not filename:
            return "unnamed_file"
        
        # Maximale Länge begrenzen (Windows: 255 Zeichen)
        if len(filename) > 200:
            name_part = filename[:150]
            ext_part = ""
            if '.' in filename:
                name_part, ext_part = filename.rsplit('.', 1)
                name_part = name_part[:150]
                filename = f"{name_part}.{ext_part}"
            else:
                filename = name_part[:150]
        
        return filename
    
    def rename_files_in_directory(self, directory):
        """Benennt alle Dateien im Verzeichnis um"""
        renamed = []
        directory_path = Path(directory)
        
        if not directory_path.exists():
            return renamed
        
        for file_path in directory_path.rglob("*"):
            if file_path.is_file():
                old_name = file_path.name
                new_name = self.clean_filename(old_name)
                
                if old_name != new_name:
                    new_path = file_path.parent / new_name
                    counter = 1
                    
                    # Vermeide Überschreibungen
                    while new_path.exists():
                        name_parts = new_name.rsplit('.', 1)
                        if len(name_parts) == 2:
                            base_name = name_parts[0]
                            extension = name_parts[1]
                            # Entferne bereits vorhandene Nummerierung
                            base_name = re.sub(r'_\d+$', '', base_name)
                            new_name_with_counter = f"{base_name}_{counter}.{extension}"
                        else:
                            base_name = re.sub(r'_\d+$', '', new_name)
                            new_name_with_counter = f"{base_name}_{counter}"
                        
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
                        target_path = self.executables_dir / self.clean_filename(file_path.name)
                        shutil.copy2(file_path, target_path)
                    except:
                        pass
                return f"AUSFÜHRBARE DATEI - NICHT VERARBEITET ({ext})"
            
            # Prüfe auf sehr große Dateien (>50MB)
            try:
                file_size = file_path.stat().st_size
                if file_size > 50 * 1024 * 1024:
                    # Verschiebe in nicht verarbeitet Ordner
                    if self.not_processed_dir:
                        try:
                            target_path = self.not_processed_dir / self.clean_filename(file_path.name)
                            shutil.copy2(file_path, target_path)
                        except:
                            pass
                    return f"DATEI ZU GROSS - NICHT VERARBEITET ({file_size//(1024*1024)} MB)"
            except:
                file_size = 0
            
            # Programmiersprachen
            code_extensions = [".py", ".java", ".cpp", ".c", ".js", ".html", ".css", ".php", ".rb", ".go", ".rs"]
            if ext in code_extensions:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(3000)
                        return f"Code ({ext[1:].upper()}):\n{content}"
                except:
                    return f"Code-Datei ({ext})"
            
            # PDF
            elif ext == ".pdf":
                try:
                    text = ""
                    with pdfplumber.open(file_path) as pdf:
                        for i, page in enumerate(pdf.pages[:2]):
                            page_text = page.extract_text()
                            if page_text:
                                text += f"\n--- Seite {i+1} ---\n{page_text[:800]}"
                    return text.strip() or "PDF (kein Text extrahierbar)"
                except Exception as e:
                    return f"PDF-Datei"
            
            # Word
            elif ext == ".docx":
                try:
                    doc = Document(file_path)
                    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                    return "\n".join(paragraphs[:10])
                except:
                    return "Word-Dokument"
            
            # Textdateien
            elif ext in [".txt", ".md", ".csv", ".json", ".xml", ".yaml", ".yml"]:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        return f.read(2000).strip()
                except:
                    return f"Textdatei ({ext})"
            
            # Bilder
            elif ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".gif", ".webp", ".svg"]:
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
            
            # Tabellen
            elif ext in [".xlsx", ".xls", ".ods"]:
                return f"Tabellendatei ({ext})"
            
            # Präsentationen
            elif ext in [".pptx", ".ppt", ".odp"]:
                return f"Präsentation ({ext})"
            
            # Audio/Video
            elif ext in [".mp3", ".wav", ".flac", ".aac", ".mp4", ".avi", ".mov", ".mkv", ".opus"]:
                return f"Media-Datei ({ext})"
            
            # Archive (werden nicht extrahiert)
            elif ext in [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"]:
                return f"Archiv ({ext})"
            
            # Ausführbare Dateien (bereits oben behandelt)
            elif ext in [".exe", ".msi", ".dmg", ".app", ".deb", ".rpm"]:
                return f"Programmdatei ({ext})"
            
            # Sonstige
            else:
                # Verschiebe in nicht verarbeitet Ordner
                if self.not_processed_dir:
                    try:
                        target_path = self.not_processed_dir / self.clean_filename(file_path.name)
                        shutil.copy2(file_path, target_path)
                    except:
                        pass
                return f"NICHT UNTERSTÜTZT - NICHT VERARBEITET ({ext})"
                
        except Exception as e:
            # Verschiebe fehlerhafte Dateien
            if self.not_processed_dir:
                try:
                    target_path = self.not_processed_dir / self.clean_filename(file_path.name)
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
        
        if not input_path.exists():
            st.error(f"Verzeichnis existiert nicht: {input_path}")
            return {
                "metadata": {
                    "total_files": 0,
                    "file_types": {},
                    "skipped_files": ["Verzeichnis existiert nicht"],
                    "processed_date": time.strftime("%Y-%m-%d %H:%M:%S")
                },
                "files": []
            }
        
        # Finde alle Dateien
        all_files = []
        for file_path in input_path.rglob("*"):
            if file_path.is_file():
                # Überspringe sehr große Dateien (>100MB)
                try:
                    if file_path.stat().st_size > 100 * 1024 * 1024:
                        skipped_files.append(f"{file_path.name} (zu groß >100MB)")
                        continue
                except:
                    pass
                
                all_files.append(file_path)
        
        # Begrenze auf max_files
        all_files = all_files[:max_files]
        
        if not all_files:
            st.warning("Keine Dateien im Verzeichnis gefunden")
            return {
                "metadata": {
                    "total_files": 0,
                    "file_types": {},
                    "skipped_files": ["Keine Dateien gefunden"],
                    "processed_date": time.strftime("%Y-%m-%d %H:%M:%S")
                },
                "files": []
            }
        
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
                    "original_name": file_path.name,  # Originalname speichern
                    "path": str(file_path),
                    "extension": ext,
                    "size_kb": file_path.stat().st_size // 1024 if file_path.exists() else 0,
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
                "processed_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "renamed_files": st.session_state.get('renamed_files', [])
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
            
            # Kategorie bereinigen für Dateisystem
            safe_category = self._clean_category_name(category)
            
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
                    
                    # Existenz prüfen und ggf. nummerieren
                    counter = 1
                    while target_file.exists():
                        name_parts = target_name.rsplit('.', 1)
                        if len(name_parts) == 2:
                            base_name = re.sub(r'_\d+$', '', name_parts[0])
                            target_name = f"{base_name}_{counter}.{name_parts[1]}"
                        else:
                            base_name = re.sub(r'_\d+$', '', target_name)
                            target_name = f"{base_name}_{counter}"
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
    
    def _clean_category_name(self, category):
        """Bereinigt Kategorienamen für Dateisystem"""
        # Entferne problematische Zeichen
        cleaned = re.sub(r'[<>:"/\\|?*]', '-', category)
        cleaned = cleaned.replace('/', '-').replace('\\', '-')
        
        # Mehrfache Bindestriche reduzieren
        cleaned = re.sub(r'-+', '-', cleaned)
        
        # Trimmen
        cleaned = cleaned.strip('.-_ ')
        
        return cleaned if cleaned else "Unkategorisiert"
    
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
                    
                    # Bereinige auch den Zielnamen
                    if target_path.name != self.clean_filename(target_path.name):
                        clean_name = self.clean_filename(target_path.name)
                        target_path = target_path.parent / clean_name
                    
                    shutil.copy2(file_path, target_path)
                    copied_count += 1
                except Exception as e:
                    st.warning(f"Konnte {file_path.name} nicht kopieren: {e}")
        
        return copied_count
    
    def get_renamed_files_info(self):
        """Gibt Informationen über umbenannte Dateien zurück"""
        renamed = st.session_state.get('renamed_files', [])
        return renamed