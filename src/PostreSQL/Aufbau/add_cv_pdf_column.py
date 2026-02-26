""" 
====================================================
Programmname : CV PDF Spalte hinzufügen  
Beschreibung :  Fügt die cv_pdf Spalte (BYTEA) zur candidates-Tabelle hinzu

====================================================
"""


import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

import psycopg
from src.db_config import DB_CONFIG


def add_cv_pdf_column():
    """
    Fügt cv_pdf BYTEA Spalte zur candidates-Tabelle hinzu.
    """
    print("\n=== CV PDF Spalte hinzufügen ===\n")
    
    try:
        conn = psycopg.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Prüfe ob Spalte bereits existiert
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'candidates' 
            AND column_name = 'cv_pdf';
        """)
        
        if cur.fetchone():
            print("✓ Spalte cv_pdf existiert bereits")
            cur.close()
            conn.close()
            return
        
        # Füge Spalte hinzu
        print("Füge Spalte cv_pdf (BYTEA) hinzu...")
        cur.execute("""
            ALTER TABLE candidates 
            ADD COLUMN cv_pdf BYTEA;
        """)
        
        conn.commit()
        print("✓ Spalte cv_pdf erfolgreich hinzugefügt")
        
        # Zeige Spalten-Info
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'candidates' 
            ORDER BY ordinal_position;
        """)
        
        print("\nAlle Spalten in candidates:")
        for col_name, data_type in cur.fetchall():
            print(f"  - {col_name}: {data_type}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n✗ Fehler: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(add_cv_pdf_column())
