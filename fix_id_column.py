"""Prüfe und korrigiere ID-Spalte"""
import psycopg
from src.db_config import DB_CONFIG

conn = psycopg.connect(**DB_CONFIG)
cur = conn.cursor()

print("=== Prüfe ID-Spalte ===\n")

# Prüfe aktuelle Definition
cur.execute("""
    SELECT column_name, column_default, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'jobs' AND column_name = 'id';
""")

row = cur.fetchone()
if row:
    print(f"Spalte: {row[0]}")
    print(f"Default: {row[1]}")
    print(f"Nullable: {row[2]}")
else:
    print("ID-Spalte nicht gefunden!")

# Prüfe Sequence
cur.execute("""
    SELECT pg_get_serial_sequence('jobs', 'id');
""")
seq_row = cur.fetchone()
print(f"\nSequence: {seq_row[0] if seq_row else 'Keine'}")

# Korrektur: Füge eine Sequence hinzu und setze als Default
print("\n=== Korrektur ===\n")

try:
    # 1. Erstelle eine Sequence falls nicht vorhanden
    cur.execute("""
        CREATE SEQUENCE IF NOT EXISTS jobs_id_seq START WITH 1000;
    """)
    
    # 2. Setze Default für id
    cur.execute("""
        ALTER TABLE jobs
        ALTER COLUMN id SET DEFAULT nextval('jobs_id_seq');
    """)
    
    # 3. Verknüpfe Sequence mit Spalte
    cur.execute("""
        ALTER SEQUENCE jobs_id_seq OWNED BY jobs.id;
    """)
    
    conn.commit()
    print("✓ ID-Spalte konfiguriert mit auto-increment (Start: 1000)")
    
except Exception as e:
    print(f"✗ Fehler: {e}")
    conn.rollback()

# Bestätige
cur.execute("""
    SELECT column_default
    FROM information_schema.columns
    WHERE table_name = 'jobs' AND column_name = 'id';
""")
row = cur.fetchone()
print(f"✓ Neuer Default: {row[0]}")

conn.close()
