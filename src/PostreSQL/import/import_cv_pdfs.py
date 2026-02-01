"""
Importiert PDF-Dateien in die candidates-Tabelle (cv_pdf BYTEA Spalte)

Verwendet Dateinamen-Konvention:
- {candidate_id}.pdf
- {vorname}_{nachname}.pdf
- Ordnerstruktur: data/db/cvs/
"""

import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

import psycopg
from src.db_config import DB_CONFIG

# --------------------------------------------------
# KONFIGURATION
# --------------------------------------------------

CV_DIR = r"data\db\cvs"


def find_pdf_files():
    """Findet alle PDF-Dateien im CV-Verzeichnis."""
    if not os.path.exists(CV_DIR):
        print(f"✗ Verzeichnis nicht gefunden: {CV_DIR}")
        return []
    
    pdf_files = [f for f in os.listdir(CV_DIR) if f.lower().endswith('.pdf')]
    return pdf_files


def match_pdf_to_candidate(filename, candidates):
    """
    Versucht PDF-Datei einem Kandidaten zuzuordnen.
    
    Matching-Strategien:
    1. Dateiname = ID.pdf (z.B. "42.pdf")
    2. Dateiname = vorname_nachname.pdf (z.B. "Max_Mustermann.pdf")
    """
    basename = os.path.splitext(filename)[0]
    
    # Strategie 1: Direkter ID-Match
    for candidate in candidates:
        if str(candidate['id']) == basename:
            return candidate['id']
    
    # Strategie 2: Vorname_Nachname Match (case-insensitive)
    basename_lower = basename.lower().replace('_', ' ').replace('-', ' ')
    for candidate in candidates:
        first_name = candidate.get('first_name', '').lower()
        last_name = candidate.get('last_name', '').lower()
        
        if first_name and last_name:
            full_name = f"{first_name} {last_name}"
            if basename_lower == full_name:
                return candidate['id']
    
    return None


def import_pdf_to_candidate(candidate_id, pdf_path, conn):
    """Importiert ein PDF in die Datenbank für einen bestimmten Kandidaten."""
    try:
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE candidates SET cv_pdf = %s WHERE id = %s",
                (pdf_data, candidate_id)
            )
        
        file_size = len(pdf_data) / 1024  # KB
        return True, file_size
    
    except Exception as e:
        return False, str(e)


def main():
    print("=" * 60)
    print("CV PDF Import")
    print("=" * 60)
    
    # 1. Prüfe ob cv_pdf Spalte existiert
    try:
        conn = psycopg.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'candidates' 
            AND column_name = 'cv_pdf';
        """)
        
        if not cur.fetchone():
            print("\n✗ Spalte cv_pdf existiert nicht!")
            print("Bitte führen Sie zuerst aus:")
            print("  python src/PostreSQL/Aufbau/add_cv_pdf_column.py")
            cur.close()
            conn.close()
            return 1
        
        print("✓ Spalte cv_pdf vorhanden\n")
        
        # 2. Lade alle Kandidaten
        print("Lade Kandidaten aus Datenbank...")
        cur.execute("SELECT id, first_name, last_name FROM candidates;")
        candidates = [
            {'id': row[0], 'first_name': row[1], 'last_name': row[2]}
            for row in cur.fetchall()
        ]
        print(f"✓ {len(candidates)} Kandidaten gefunden\n")
        
        # 3. Finde PDF-Dateien
        print(f"Suche PDFs in: {CV_DIR}")
        pdf_files = find_pdf_files()
        
        if not pdf_files:
            print(f"✗ Keine PDF-Dateien gefunden in {CV_DIR}")
            cur.close()
            conn.close()
            return 1
        
        print(f"✓ {len(pdf_files)} PDF-Dateien gefunden\n")
        
        # 4. Matching durchführen
        matches = []
        unmatched = []
        
        print("Ordne PDFs Kandidaten zu...")
        for pdf_file in pdf_files:
            candidate_id = match_pdf_to_candidate(pdf_file, candidates)
            if candidate_id:
                matches.append((candidate_id, pdf_file))
            else:
                unmatched.append(pdf_file)
        
        print(f"✓ {len(matches)} PDFs zugeordnet")
        if unmatched:
            print(f"⚠ {len(unmatched)} PDFs nicht zugeordnet:")
            for pdf in unmatched[:5]:
                print(f"  - {pdf}")
            if len(unmatched) > 5:
                print(f"  ... und {len(unmatched) - 5} weitere")
        
        if not matches:
            print("\n✗ Keine PDFs konnten zugeordnet werden")
            cur.close()
            conn.close()
            return 1
        
        # 5. Vorschau
        print("\n" + "=" * 60)
        print("VORSCHAU (erste 5)")
        print("=" * 60)
        for candidate_id, pdf_file in matches[:5]:
            candidate = next(c for c in candidates if c['id'] == candidate_id)
            name = f"{candidate['first_name']} {candidate['last_name']}"
            print(f"ID {candidate_id}: {name} ← {pdf_file}")
        
        if len(matches) > 5:
            print(f"... und {len(matches) - 5} weitere")
        
        # 6. Bestätigung
        print("\n" + "=" * 60)
        response = input(f"\nMöchten Sie {len(matches)} PDFs importieren? (j/n): ")
        
        if response.lower() not in ['j', 'ja', 'y', 'yes']:
            print("\n✗ Import abgebrochen")
            cur.close()
            conn.close()
            return 0
        
        # 7. Import durchführen
        print("\nImportiere PDFs...")
        imported = 0
        errors = 0
        total_size = 0
        
        for candidate_id, pdf_file in matches:
            pdf_path = os.path.join(CV_DIR, pdf_file)
            success, result = import_pdf_to_candidate(candidate_id, pdf_path, conn)
            
            if success:
                imported += 1
                total_size += result
                print(f"  [{imported}/{len(matches)}] ✓ {pdf_file} ({result:.1f} KB)")
            else:
                errors += 1
                print(f"  ✗ {pdf_file}: {result}")
        
        conn.commit()
        cur.close()
        conn.close()
        
        # 8. Zusammenfassung
        print("\n" + "=" * 60)
        print("IMPORT ABGESCHLOSSEN")
        print("=" * 60)
        print(f"✓ {imported} PDFs erfolgreich importiert")
        print(f"  Gesamtgröße: {total_size:.1f} KB ({total_size/1024:.1f} MB)")
        if errors > 0:
            print(f"✗ {errors} Fehler")
        
        return 0
        
    except Exception as e:
        print(f"\n✗ Fehler: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
