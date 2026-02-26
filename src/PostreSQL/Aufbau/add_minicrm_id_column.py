""" 
====================================================
Programmname : KI-unterstütztes BMS - minicrm_id Spalte hinzufügen
Beschreibung : Fügt die minicrm_id Spalte zur jobs-Tabelle hinzu

====================================================
"""

import psycopg
from src.db_config import DB_CONFIG

conn = psycopg.connect(**DB_CONFIG)
cur = conn.cursor()

print("=== Füge minicrm_id Spalte hinzu ===\n")

# Prüfe ob Spalte bereits existiert
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'jobs' AND column_name = 'minicrm_id';
""")

if cur.fetchone():
    print("⚠ Spalte minicrm_id existiert bereits")
else:
    # Füge Spalte hinzu mit UNIQUE constraint für UPSERT
    cur.execute("""
        ALTER TABLE jobs
        ADD COLUMN minicrm_id INTEGER UNIQUE;
    """)
    conn.commit()
    print("✓ Spalte minicrm_id erfolgreich hinzugefügt (INTEGER UNIQUE)")

# Zeige aktualisierte Struktur
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'jobs' AND column_name = 'minicrm_id';
""")

row = cur.fetchone()
if row:
    print(f"✓ Bestätigung: {row[0]} ({row[1]})")

conn.close()
