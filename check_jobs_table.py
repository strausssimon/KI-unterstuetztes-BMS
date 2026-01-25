"""Prüfe jobs-Tabelle Struktur"""
import psycopg
from src.db_config import DB_CONFIG

conn = psycopg.connect(**DB_CONFIG)
cur = conn.cursor()

# Prüfe aktuelle Spalten
cur.execute("""
    SELECT column_name, data_type, character_maximum_length
    FROM information_schema.columns
    WHERE table_name = 'jobs'
    ORDER BY ordinal_position;
""")

print("=== Aktuelle Spalten in jobs-Tabelle ===\n")
for col_name, data_type, max_len in cur.fetchall():
    type_str = data_type
    if max_len:
        type_str = f"{data_type}({max_len})"
    print(f"{col_name}: {type_str}")

conn.close()
