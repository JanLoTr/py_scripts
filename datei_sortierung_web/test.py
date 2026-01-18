import sys
import importlib

required_packages = [
    ('pdfplumber', 'pdfplumber'),
    ('PIL', 'Pillow'),
    ('pytesseract', 'pytesseract'),
    ('docx', 'python-docx'),
    ('pdf2image', 'pdf2image'),
    ('pandas', 'pandas'),
    ('pygments', 'pygments')
]

print("🔍 Teste Installation...")
print("=" * 50)

all_ok = True
for display_name, package_name in required_packages:
    try:
        importlib.import_module(package_name if package_name != 'PIL' else 'PIL')
        print(f"✅ {display_name:20} ... OK")
    except ImportError as e:
        print(f"❌ {display_name:20} ... FEHLT")
        print(f"   → pip install {package_name}")
        all_ok = False

print("=" * 50)
if all_ok:
    print("✅ Alle Pakete installiert! Du kannst starten.")
    print("\nStarten mit: python file_organizer.py")
else:
    print("⚠️  Einige Pakete fehlen. Bitte oben installieren.")