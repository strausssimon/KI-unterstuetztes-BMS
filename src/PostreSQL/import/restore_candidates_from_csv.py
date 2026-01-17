"""
Import-Skript für die candidates-Tabelle

Lädt ein CSV-Backup (aus backup_candidates_to_csv.py) wieder in die
PostgreSQL-Tabelle `candidates`.

Funktionen:
- Nimmt standardmäßig das neueste Backup aus data\\db\\backup_postresql
- Optional kann ein expliziter CSV-Pfad übergeben werden
- Entfernt Hilfsspalten (export_timestamp, export_date), falls vorhanden
- Kann die Tabelle vor dem Import leeren (TRUNCATE)
"""

import os
from datetime import datetime

import psycopg
import pandas as pd

# --------------------------------------------------
# KONFIGURATION
# --------------------------------------------------
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "postgres",
    "user": "postgres",
    "password": "Start123",
}

BACKUP_DIR = r"data\\db\\backup_postresql"

# Wenn True: candidates-Tabelle vor dem Import leeren
TRUNCATE_BEFORE_IMPORT = False


def find_latest_backup() -> str | None:
    """Gibt den Pfad zur neuesten Backup-CSV zurück oder None, wenn keine existiert."""
    if not os.path.exists(BACKUP_DIR):
        return None

    files = [
        f for f in os.listdir(BACKUP_DIR)
        if f.startswith("candidates_backup_") and f.endswith(".csv")
    ]
    if not files:
        return None

    files.sort(reverse=True)
    latest = files[0]
    return os.path.join(BACKUP_DIR, latest)


def load_csv(filepath: str) -> pd.DataFrame:
    """Lädt die Backup-CSV in ein DataFrame und entfernt Hilfsspalten."""
    print(f"Lade CSV: {filepath}")
    df = pd.read_csv(filepath, dtype=str)  # alles zunächst als Text laden

    # Hilfsspalten entfernen, falls vorhanden
    for col in ["export_timestamp", "export_date"]:
        if col in df.columns:
            print(f"Entferne Hilfsspalte: {col}")
            df.drop(columns=[col], inplace=True)

    print(f"Spalten im CSV: {list(df.columns)}")
    print(f"Zeilen im CSV: {len(df)}")
    return df


def import_candidates_from_df(df: pd.DataFrame) -> None:
    """Importiert die Daten aus dem DataFrame in die Tabelle `candidates`."""
    if df.empty:
        print("CSV ist leer, nichts zu importieren.")
        return

    columns = list(df.columns)
    col_list_sql = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))

    insert_sql = f"INSERT INTO candidates ({col_list_sql}) VALUES ({placeholders})"

    print("Verbinde mit PostgreSQL für Import...")
    with psycopg.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            if TRUNCATE_BEFORE_IMPORT:
                print("Leere Tabelle candidates (TRUNCATE)...")
                cur.execute("TRUNCATE TABLE candidates RESTART IDENTITY CASCADE;")

            print("Starte Import in candidates...")
            rows = [tuple(None if pd.isna(v) else v for v in row) for row in df.to_numpy()]

            cur.executemany(insert_sql, rows)
            conn.commit()

    print("✓ Import abgeschlossen.")


def restore_candidates(csv_path: str | None = None) -> None:
    """High-Level-Funktion: CSV-Pfad bestimmen, laden und importieren."""
    if csv_path is None:
        csv_path = find_latest_backup()
        if not csv_path:
            print("✗ Kein Backup gefunden in:", BACKUP_DIR)
            return
        print("Verwende neuestes Backup:", csv_path)
    else:
        if not os.path.exists(csv_path):
            print("✗ Angegebene CSV nicht gefunden:", csv_path)
            return

    df = load_csv(csv_path)
    import_candidates_from_df(df)


if __name__ == "__main__":
    print("=== Restore candidates from CSV ===")
    print("Zeit:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print()

    # Standard: letztes Backup verwenden
    restore_candidates()
