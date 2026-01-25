"""Ändere minicrm_id von INTEGER zu VARCHAR"""
import psycopg
from src.db_config import DB_CONFIG

conn = psycopg.connect(**DB_CONFIG)
cur = conn.cursor()

print("=== Ändere minicrm_id Datentyp ===\n")

# Ändere Datentyp von INTEGER zu VARCHAR
try:
    cur.execute("""
        ALTER TABLE jobs
        ALTER COLUMN minicrm_id TYPE VARCHAR(50);
    """)
    conn.commit()
    print("✓ minicrm_id Datentyp geändert von INTEGER zu VARCHAR(50)")
except Exception as e:
    print(f"✗ Fehler: {e}")
    conn.rollback()

# Bestätige Änderung
cur.execute("""
    SELECT column_name, data_type, character_maximum_length
    FROM information_schema.columns
    WHERE table_name = 'jobs' AND column_name = 'minicrm_id';
""")

row = cur.fetchone()
if row:
    type_str = row[1]
    if row[2]:
        type_str = f"{row[1]}({row[2]})"
    print(f"✓ Bestätigung: {row[0]} ist jetzt {type_str}")

conn.close()
