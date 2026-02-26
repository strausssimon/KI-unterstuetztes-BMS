""" 
====================================================
Programmname : Fehlende Spalten hinzufügen
Beschreibung : Fügt fehlende Spalten zur jobs-Tabelle hinzu

====================================================
"""

import psycopg
from src.db_config import DB_CONFIG

conn = psycopg.connect(**DB_CONFIG)
cur = conn.cursor()

print("=== Füge fehlende Spalten hinzu ===\n")

# Liste der hinzuzufügenden Spalten
new_columns = [
    ('job_name', 'VARCHAR(200)'),
    ('responsible', 'VARCHAR(100)')
]

for col_name, col_type in new_columns:
    # Prüfe ob Spalte bereits existiert
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'jobs' AND column_name = %s;
    """, (col_name,))
    
    if cur.fetchone():
        print(f"⚠ Spalte {col_name} existiert bereits")
    else:
        # Füge Spalte hinzu
        cur.execute(f"""
            ALTER TABLE jobs
            ADD COLUMN {col_name} {col_type};
        """)
        conn.commit()
        print(f"✓ Spalte {col_name} ({col_type}) erfolgreich hinzugefügt")

# Zeige aktualisierte Struktur
print("\n=== Aktuelle jobs-Tabelle Struktur ===\n")
cur.execute("""
    SELECT column_name, data_type, character_maximum_length
    FROM information_schema.columns
    WHERE table_name = 'jobs'
    ORDER BY ordinal_position;
""")

for col_name, data_type, max_len in cur.fetchall():
    type_str = data_type
    if max_len:
        type_str = f"{data_type}({max_len})"
    print(f"  {col_name}: {type_str}")

conn.close()
