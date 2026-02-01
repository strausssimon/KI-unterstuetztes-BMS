"""
Exportiert PDF-Dateien aus der candidates-Tabelle (cv_pdf BYTEA Spalte)

Speichert PDFs als: {candidate_id}_{vorname}_{nachname}.pdf
Zielordner: data/db/cvs_export/
"""

import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

import psycopg
from src.db_config import DB_CONFIG

# --------------------------------------------------
# KONFIGURATION
# --------------------------------------------------

EXPORT_DIR = r"data\db\cvs_export"


def ensure_export_directory():
    """Stellt sicher, dass das Export-Verzeichnis existiert."""
    if not os.path.exists(EXPORT_DIR):
        os.makedirs(EXPORT_DIR)
        print(f"✓ Export-Verzeichnis erstellt: {EXPORT_DIR}")
    else:
        print(f"✓ Export-Verzeichnis existiert: {EXPORT_DIR}")


def sanitize_filename(name):
    """Bereinigt Namen für Dateinamen."""
    if not name:
        return "unbekannt"
    
    # Ersetze problematische Zeichen
    replacements = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
        'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
        ' ': '_', '/': '_', '\\': '_', ':': '_',
        '*': '_', '?': '_', '"': '_', '<': '_',
        '>': '_', '|': '_'
    }
    
    for old, new in replacements.items():
        name = name.replace(old, new)
    
    return name


def export_cv_pdfs():
    """Exportiert alle CV PDFs aus der Datenbank."""
    print("\n=== CV PDF Export ===\n")
    
    try:
        conn = psycopg.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Prüfe ob cv_pdf Spalte existiert
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'candidates' 
            AND column_name = 'cv_pdf';
        """)
        
        if not cur.fetchone():
            print("✗ Spalte cv_pdf existiert nicht!")
            print("Bitte führen Sie zuerst aus:")
            print("  python src/PostreSQL/Aufbau/add_cv_pdf_column.py")
            cur.close()
            conn.close()
            return 1
        
        # Hole alle Kandidaten mit PDFs
        print("Lade Kandidaten mit CVs aus Datenbank...")
        cur.execute("""
            SELECT id, first_name, last_name, cv_pdf 
            FROM candidates 
            WHERE cv_pdf IS NOT NULL;
        """)
        
        candidates = cur.fetchall()
        
        if not candidates:
            print("✗ Keine Kandidaten mit CVs gefunden")
            cur.close()
            conn.close()
            return 0
        
        print(f"✓ {len(candidates)} Kandidaten mit CVs gefunden\n")
        
        # Export-Verzeichnis vorbereiten
        ensure_export_directory()
        
        # Bestätigung
        print("=" * 60)
        response = input(f"\nMöchten Sie {len(candidates)} PDFs exportieren? (j/n): ")
        
        if response.lower() not in ['j', 'ja', 'y', 'yes']:
            print("\n✗ Export abgebrochen")
            cur.close()
            conn.close()
            return 0
        
        # Export durchführen
        print("\nExportiere PDFs...")
        exported = 0
        errors = 0
        total_size = 0
        
        for candidate_id, first_name, last_name, pdf_data in candidates:
            # Dateinamen erstellen
            first_name_clean = sanitize_filename(first_name or "")
            last_name_clean = sanitize_filename(last_name or "")
            filename = f"{candidate_id}_{first_name_clean}_{last_name_clean}.pdf"
            filepath = os.path.join(EXPORT_DIR, filename)
            
            try:
                with open(filepath, 'wb') as f:
                    f.write(pdf_data)
                
                file_size = len(pdf_data) / 1024  # KB
                exported += 1
                total_size += file_size
                print(f"  [{exported}/{len(candidates)}] ✓ {filename} ({file_size:.1f} KB)")
                
            except Exception as e:
                errors += 1
                print(f"  ✗ {filename}: {e}")
        
        cur.close()
        conn.close()
        
        # Zusammenfassung
        print("\n" + "=" * 60)
        print("EXPORT ABGESCHLOSSEN")
        print("=" * 60)
        print(f"✓ {exported} PDFs erfolgreich exportiert")
        print(f"  Gesamtgröße: {total_size:.1f} KB ({total_size/1024:.1f} MB)")
        print(f"  Zielordner: {EXPORT_DIR}")
        if errors > 0:
            print(f"✗ {errors} Fehler")
        
        return 0
        
    except Exception as e:
        print(f"\n✗ Fehler: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(export_cv_pdfs())
