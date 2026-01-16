#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_short_note_length.py

Ändert die Länge der short_note Spalte auf CHARACTER VARYING(1500)
"""

import pandas as pd
import psycopg

# Excel-Datei aktualisieren
excel_path = 'data/db/candidates_master.xlsx'

print("=" * 60)
print("Update Short Note zu CHARACTER VARYING(1500)")
print("=" * 60)

# 1. Excel-Datei aktualisieren
print("\n1. Aktualisiere Excel-Datei...")
df = pd.read_excel(excel_path, header=None)

# Finde die Spalte "Short Note"
spalte_idx = None
for idx, col_name in enumerate(df.iloc[0]):
    if pd.notna(col_name) and str(col_name).strip() == 'Short Note':
        spalte_idx = idx
        break

if spalte_idx is not None:
    # Zeile 2 (Index 1) enthält die Datentypen
    alter_typ = df.iloc[1, spalte_idx]
    df.iloc[1, spalte_idx] = 'character varying(1500)'
    
    # Speichern
    df.to_excel(excel_path, index=False, header=False)
    print(f"✓ Short Note Datentyp geändert: {alter_typ} → character varying(1500)")
else:
    print("✗ Spalte 'Short Note' nicht gefunden")

# 2. Datenbank aktualisieren
print("\n2. Aktualisiere Datenbank...")

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'postgres',
    'user': 'postgres',
    'password': 'bigdataconsulting'
}

try:
    with psycopg.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # Prüfe ob Tabelle existiert
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'candidates'
                );
            """)
            
            if not cur.fetchone()[0]:
                print("ℹ Tabelle 'candidates' existiert nicht - nur Excel wurde aktualisiert")
            else:
                # Prüfe aktuellen Typ
                cur.execute("""
                    SELECT character_maximum_length 
                    FROM information_schema.columns 
                    WHERE table_name = 'candidates' 
                    AND column_name = 'short_note';
                """)
                
                result = cur.fetchone()
                if result:
                    alter_laenge = result[0]
                    
                    if alter_laenge == 1500:
                        print("✓ short_note hat bereits CHARACTER VARYING(1500)")
                    else:
                        print(f"   Aktuelle Länge: {alter_laenge}")
                        print("   Ändere auf 1500...")
                        
                        cur.execute("""
                            ALTER TABLE candidates 
                            ALTER COLUMN short_note TYPE CHARACTER VARYING(1500);
                        """)
                        conn.commit()
                        
                        print("✓ short_note erfolgreich auf CHARACTER VARYING(1500) geändert")
                else:
                    print("⚠ Spalte short_note nicht gefunden in der Datenbank")
        
        print("\n" + "=" * 60)
        print("✓ Update abgeschlossen!")
        print("=" * 60)
        
except psycopg.Error as e:
    print(f"\n✗ Datenbankfehler: {e}")
    print("Excel wurde aktualisiert, aber Datenbank konnte nicht geändert werden")
except Exception as e:
    print(f"\n✗ Fehler: {e}")
