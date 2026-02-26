""" 
====================================================
Programmname : Fehlende Skills Spalte hinzufügen
Beschreibung : Fügt fehlende Spalte Skills zur candidates-Tabelle hinzu

====================================================
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.db_config import DB_CONFIG
import psycopg

def main():
    print("\n=== Füge Spalte 'skills' zu candidates hinzu ===\n")
    
    try:
        conn = psycopg.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Prüfe ob Spalte bereits existiert
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'candidates' AND column_name = 'skills';
        """)
        
        if cur.fetchone():
            print("⚠ Spalte 'skills' existiert bereits")
        else:
            # Füge Spalte hinzu
            cur.execute("ALTER TABLE candidates ADD COLUMN skills CHARACTER VARYING(2500);")
            conn.commit()
            print("✓ Spalte 'skills' hinzugefügt")
        
        # Zeige Info
        cur.execute("""
            SELECT column_name, data_type, character_maximum_length 
            FROM information_schema.columns 
            WHERE table_name = 'candidates' AND column_name = 'skills';
        """)
        
        result = cur.fetchone()
        if result:
            print(f"\nSpalten-Info:")
            print(f"  Name: {result[0]}")
            print(f"  Typ: {result[1]}({result[2]})")
        
        # Zähle Kandidaten
        cur.execute("SELECT COUNT(*) FROM candidates;")
        count = cur.fetchone()[0]
        print(f"\n✓ Anzahl Kandidaten in Tabelle: {count}")
        print(f"  (Alle haben skills = NULL)")
        
        cur.close()
        conn.close()
        
        print("\n✓ Fertig!")
        
    except Exception as e:
        print(f"✗ Fehler: {e}")
        raise

if __name__ == "__main__":
    main()
