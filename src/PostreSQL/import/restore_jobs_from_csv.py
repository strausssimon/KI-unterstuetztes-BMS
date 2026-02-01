"""
Import-Skript für die jobs-Tabelle

Lädt ein CSV-Backup (aus backup_jobs_to_csv.py) wieder in die
PostgreSQL-Tabelle `jobs`.

Funktionen:
- Nimmt standardmäßig das neueste Backup aus data\\db\\backup_postresql
- Optional kann ein expliziter CSV-Pfad übergeben werden
- Kann die Tabelle vor dem Import leeren (TRUNCATE)
- Vergleicht Backup mit aktuellen Daten und zeigt Unterschiede an
"""

import sys
import os
# Füge Projekt-Root zum Python-Pfad hinzu
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from datetime import datetime
import psycopg
import pandas as pd
from src.db_config import DB_CONFIG

# --------------------------------------------------
# KONFIGURATION
# --------------------------------------------------

BACKUP_DIR = r"data\db\backup_postresql"

# Wenn True: jobs-Tabelle vor dem Import leeren
TRUNCATE_BEFORE_IMPORT = False


def find_latest_backup() -> str | None:
    """Gibt den Pfad zur neuesten Backup-CSV zurück oder None, wenn keine existiert."""
    if not os.path.exists(BACKUP_DIR):
        return None

    files = [
        f for f in os.listdir(BACKUP_DIR)
        if f.startswith("jobs_backup_") and f.endswith(".csv")
    ]
    if not files:
        return None

    files.sort(reverse=True)
    latest = files[0]
    return os.path.join(BACKUP_DIR, latest)


def load_csv(filepath: str) -> pd.DataFrame:
    """Lädt die Backup-CSV in ein DataFrame."""
    print(f"Lade CSV: {filepath}")
    df = pd.read_csv(filepath, dtype=str)  # alles zunächst als Text laden

    print(f"Spalten im CSV: {list(df.columns)}")
    print(f"Zeilen im CSV: {len(df)}")
    return df


def import_jobs_from_df(df: pd.DataFrame) -> None:
    """Importiert Jobs aus DataFrame in die PostgreSQL-Tabelle.

    Verhalten:
    - Für jede ID im Backup wird geprüft, ob sie bereits in der DB existiert.
    - Neue Datensätze und geänderte Datensätze werden erkannt.
    - Es wird eine Zusammenfassung ausgegeben.
    - Erst nach expliziter Bestätigung werden Änderungen vorgenommen.
    """
    if df.empty:
        print("CSV ist leer, nichts zu importieren.")
        return

    if "id" not in df.columns:
        print("✗ CSV enthält keine Spalte 'id' – Import/Abgleich nicht möglich.")
        return

    columns = list(df.columns)
    col_list_sql = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))

    insert_sql = f"INSERT INTO jobs ({col_list_sql}) VALUES ({placeholders})"

    print("\nVerbinde mit PostgreSQL für Import/Abgleich...")
    with psycopg.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # Optionaler Full-Reset
            if TRUNCATE_BEFORE_IMPORT:
                print("\nLeere Tabelle jobs (TRUNCATE) und importiere alle Datensätze neu...")
                cur.execute("TRUNCATE TABLE jobs RESTART IDENTITY CASCADE;")

                rows = [tuple(None if pd.isna(v) else v for v in row) for row in df.to_numpy()]
                cur.executemany(insert_sql, rows)
                conn.commit()
                print("✓ Vollständiger Neuimport abgeschlossen.")
                return

            # --- Diff-Modus: Unterschiede erkennen ---
            backup_ids: list[str] = []
            for raw_id in df["id"]:
                if pd.isna(raw_id):
                    continue
                id_str = str(raw_id).strip()
                if not id_str:
                    continue
                backup_ids.append(id_str)

            if not backup_ids:
                print("✗ Keine gültigen IDs im Backup gefunden.")
                return

            # Existierende Datensätze aus der DB holen
            cur.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'jobs'
                """
            )
            col_type_rows = cur.fetchall()
            col_types = {name: dtype for name, dtype in col_type_rows}

            select_parts = []
            for col in columns:
                dtype = col_types.get(col)
                if dtype in [
                    "timestamp without time zone",
                    "timestamp with time zone",
                    "date",
                    "time without time zone",
                    "time with time zone",
                ]:
                    select_parts.append(f"{col}::TEXT as {col}")
                else:
                    select_parts.append(col)

            select_statement = "SELECT " + ", ".join(select_parts) + " FROM jobs;"
            cur.execute(select_statement)
            db_rows = cur.fetchall()

            db_df = pd.DataFrame(db_rows, columns=columns)
            db_df = db_df.astype(str)

            # Backup-IDs, die nicht in der DB sind (neue Datensätze)
            db_ids = set(db_df["id"].values)
            new_ids = [bid for bid in backup_ids if bid not in db_ids]

            # Datensätze, die in beiden vorhanden sind
            common_ids = [bid for bid in backup_ids if bid in db_ids]

            # Prüfe auf Änderungen bei gemeinsamen IDs
            changed_ids = []
            for cid in common_ids:
                backup_row = df[df["id"] == cid].iloc[0]
                db_row = db_df[db_df["id"] == cid].iloc[0]

                # Normalisiere beide Zeilen (NaN → None)
                backup_vals = {
                    k: (None if pd.isna(v) else str(v).strip())
                    for k, v in backup_row.items()
                }
                db_vals = {
                    k: (None if pd.isna(v) or str(v) == "nan" else str(v).strip())
                    for k, v in db_row.items()
                }

                if backup_vals != db_vals:
                    changed_ids.append(cid)

            # IDs, die nur in der DB sind (werden gelöscht, wenn TRUNCATE aktiv)
            only_in_db_ids = [did for did in db_ids if did not in backup_ids]

            # Ausgabe der Analyse
            print("\n" + "=" * 60)
            print("IMPORT-ANALYSE")
            print("=" * 60)
            print(f"Jobs im Backup:        {len(backup_ids)}")
            print(f"Jobs in der DB:        {len(db_ids)}")
            print(f"Neue Jobs (INSERT):    {len(new_ids)}")
            print(f"Geänderte Jobs (UPDATE): {len(changed_ids)}")
            print(f"Nur in DB (keine Änderung): {len(only_in_db_ids)}")

            if new_ids:
                print(f"\nNeue Jobs (IDs): {new_ids[:10]}" + ("..." if len(new_ids) > 10 else ""))

            if changed_ids:
                print(f"\nGeänderte Jobs (IDs): {changed_ids[:10]}" + ("..." if len(changed_ids) > 10 else ""))

            if only_in_db_ids:
                print(f"\nNur in DB (IDs): {only_in_db_ids[:10]}" + ("..." if len(only_in_db_ids) > 10 else ""))

            # Wenn keine Änderungen, abbrechen
            if not new_ids and not changed_ids:
                print("\n✓ Keine Änderungen erforderlich. Datenbank ist bereits aktuell.")
                return

            # Bestätigung einholen
            print("\n" + "=" * 60)
            response = input(f"\nMöchten Sie {len(new_ids)} neue und {len(changed_ids)} geänderte Jobs importieren? (j/n): ")

            if response.lower() not in ["j", "ja", "y", "yes"]:
                print("\n✗ Import abgebrochen.")
                return

            # INSERT für neue Datensätze
            inserted = 0
            for new_id in new_ids:
                row = df[df["id"] == new_id].iloc[0]
                values = tuple(None if pd.isna(v) else v for v in row.values)
                try:
                    cur.execute(insert_sql, values)
                    inserted += 1
                except Exception as e:
                    print(f"✗ Fehler beim INSERT von ID {new_id}: {e}")

            # UPDATE für geänderte Datensätze
            updated = 0
            for changed_id in changed_ids:
                row = df[df["id"] == changed_id].iloc[0]
                set_parts = ", ".join([f"{col} = %s" for col in columns if col != "id"])
                update_sql = f"UPDATE jobs SET {set_parts} WHERE id = %s"

                values = tuple(
                    None if pd.isna(v) else v for col, v in row.items() if col != "id"
                ) + (changed_id,)

                try:
                    cur.execute(update_sql, values)
                    updated += 1
                except Exception as e:
                    print(f"✗ Fehler beim UPDATE von ID {changed_id}: {e}")

            conn.commit()

            print("\n" + "=" * 60)
            print("IMPORT ABGESCHLOSSEN")
            print("=" * 60)
            print(f"✓ {inserted} Jobs neu eingefügt")
            print(f"✓ {updated} Jobs aktualisiert")


def main():
    print("=" * 60)
    print("Jobs CSV Import/Restore")
    print("=" * 60)

    # 1. Backup-Datei finden/wählen
    latest = find_latest_backup()
    if latest:
        print(f"\nNeuestes Backup gefunden: {os.path.basename(latest)}")
        response = input("Dieses Backup verwenden? (j/n): ")
        if response.lower() in ["j", "ja", "y", "yes"]:
            csv_path = latest
        else:
            csv_path = input("Geben Sie den Pfad zur CSV-Datei ein: ").strip()
    else:
        print("\nKein Backup gefunden.")
        csv_path = input("Geben Sie den Pfad zur CSV-Datei ein: ").strip()

    if not os.path.exists(csv_path):
        print(f"\n✗ Datei nicht gefunden: {csv_path}")
        return 1

    # 2. CSV laden
    try:
        df = load_csv(csv_path)
    except Exception as e:
        print(f"\n✗ Fehler beim Laden der CSV: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # 3. Import durchführen
    try:
        import_jobs_from_df(df)
    except Exception as e:
        print(f"\n✗ Fehler beim Import: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
