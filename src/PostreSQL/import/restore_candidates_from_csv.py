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
    """Vergleicht Backup-Daten mit der Tabelle `candidates` und fragt vor dem Überschreiben.

    Verhalten:
    - Es wird NICHT blind importiert.
    - Für jede ID im Backup wird geprüft, ob sie bereits in der DB existiert.
    - Neue Datensätze (nur im Backup) und geänderte Datensätze werden erkannt.
    - Es wird eine Zusammenfassung ausgegeben.
    - Erst nach expliziter Bestätigung werden neue Datensätze per INSERT
      angelegt und geänderte Datensätze per UPDATE überschrieben.
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

    insert_sql = f"INSERT INTO candidates ({col_list_sql}) VALUES ({placeholders})"

    print("Verbinde mit PostgreSQL für Import/Abgleich...")
    with psycopg.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # Optionaler Full-Reset: Wenn explizit gewünscht, Tabelle leeren und
            # wie bisher komplett neu befüllen.
            if TRUNCATE_BEFORE_IMPORT:
                print("Leere Tabelle candidates (TRUNCATE) und importiere alle Datensätze neu...")
                cur.execute("TRUNCATE TABLE candidates RESTART IDENTITY CASCADE;")

                rows = [tuple(None if pd.isna(v) else v for v in row) for row in df.to_numpy()]
                cur.executemany(insert_sql, rows)
                conn.commit()
                print("✓ Vollständiger Neuimport abgeschlossen.")
                return

            # --- Diff-Modus: Unterschiede erkennen ---
            # IDs aus dem Backup einsammeln (als Strings, passend zu varchar/id-Spalte)
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

            # Existierende Datensätze aus der DB holen (nur die Spalten, die auch im Backup stehen)
            # Problem: In der Tabelle können defekte Timestamps liegen (z.B. Jahr 48113),
            # die beim Laden als echte Datumswerte Fehler verursachen. Daher casten wir
            # alle Zeit-/Datums-Spalten zu TEXT, analog zum Backup-Skript.
            cur.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'candidates'
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

            select_existing_sql = (
                "SELECT " + ", ".join(select_parts) + " FROM candidates WHERE id = ANY(%s);"
            )
            cur.execute(select_existing_sql, (backup_ids,))
            existing_rows = cur.fetchall()

            # Mapping: id (als String) -> dict(Spalte -> Wert)
            existing_by_id: dict[str, dict[str, object]] = {}
            for row in existing_rows:
                row_dict = {col: val for col, val in zip(columns, row)}
                raw_db_id = row_dict.get("id")
                if raw_db_id is None:
                    continue
                row_id = str(raw_db_id).strip()
                if not row_id:
                    continue
                existing_by_id[row_id] = row_dict

            new_rows: list[dict[str, object]] = []
            changed_rows: list[tuple[dict[str, object], dict[str, tuple[str, str]]]] = []
            unchanged_count = 0

            def norm_val(v: object) -> str:
                if v is None or (isinstance(v, float) and pd.isna(v)):
                    return ""
                return str(v).strip()

            # Durch alle Backup-Zeilen iterieren und mit DB vergleichen
            for _, row in df.iterrows():
                raw_id = row.get("id")
                if pd.isna(raw_id):
                    continue
                row_id = str(raw_id).strip()
                if not row_id:
                    # Ungültige/leer ID, überspringen
                    continue

                backup_row = {col: (None if pd.isna(row[col]) else str(row[col])) for col in columns}
                existing_row = existing_by_id.get(row_id)

                if existing_row is None:
                    # Neuer Datensatz
                    new_rows.append(backup_row)
                    continue

                # Vergleiche Feld für Feld
                diffs: dict[str, tuple[str, str]] = {}
                for col in columns:
                    backup_val = norm_val(backup_row.get(col))
                    db_val = norm_val(existing_row.get(col))
                    if backup_val != db_val:
                        diffs[col] = (db_val, backup_val)

                if diffs:
                    changed_rows.append((backup_row, diffs))
                else:
                    unchanged_count += 1

            # --- Zusammenfassung ausgeben ---
            total_backup = len(df)
            print("\n=== Vergleich Backup vs. Datenbank (candidates) ===")
            print(f"Gesamt im Backup: {total_backup}")
            print(f"Neue Kandidaten (nur im Backup): {len(new_rows)}")
            print(f"Geänderte Kandidaten (ID existiert, Daten abweichend): {len(changed_rows)}")
            print(f"Unveränderte Kandidaten (identische Daten): {unchanged_count}")

            if new_rows:
                print("\nBeispiele neuer Kandidaten (max. 5):")
                for r in new_rows[:5]:
                    name_preview = " ".join(
                        [
                            str(r.get("first_name", "")).strip(),
                            str(r.get("last_name", "")).strip(),
                        ]
                    ).strip()
                    print(f"- ID {r.get('id')}: {name_preview}")

            if changed_rows:
                print("\nBeispiele geänderter Kandidaten (max. 5):")
                for backup_row, diffs in changed_rows[:5]:
                    name_preview = " ".join(
                        [
                            str(backup_row.get("first_name", "")).strip(),
                            str(backup_row.get("last_name", "")).strip(),
                        ]
                    ).strip()
                    print(f"- ID {backup_row.get('id')}: {name_preview}")
                    for col, (old, new) in list(diffs.items())[:3]:
                        print(f"    {col}: DB='{old}' → Backup='{new}'")

            # Benutzer entscheiden lassen, ob Änderungen übernommen werden sollen
            if not new_rows and not changed_rows:
                print("\nKeine neuen oder geänderten Datensätze – nichts zu tun.")
                return

            answer = input("\nBackup-Daten anwenden? (j/N): ").strip().lower()
            if answer != "j":
                print("\nEs wurden KEINE Änderungen an der Datenbank vorgenommen.")
                conn.rollback()
                return

            # --- Änderungen anwenden ---
            # Neue Datensätze einfügen
            if new_rows:
                print(f"\nFüge {len(new_rows)} neue Kandidaten ein...")
                insert_values = []
                for r in new_rows:
                    insert_values.append(
                        tuple(None if (v is None or v == "") else v for v in (r.get(col) for col in columns))
                    )
                cur.executemany(insert_sql, insert_values)

            # Geänderte Datensätze aktualisieren
            if changed_rows:
                print(f"Aktualisiere {len(changed_rows)} bestehende Kandidaten aus dem Backup...")
                set_clause = ", ".join([f"{col} = %s" for col in columns if col != "id"])
                update_sql = f"UPDATE candidates SET {set_clause} WHERE id = %s"

                update_values = []
                for backup_row, _ in changed_rows:
                    vals = [
                        None if (backup_row.get(col) in (None, "")) else backup_row.get(col)
                        for col in columns if col != "id"
                    ]
                    # ID ans Ende für WHERE-Klausel (als String, passend zu varchar/id)
                    row_id = str(backup_row.get("id")).strip()
                    if not row_id:
                        continue
                    vals.append(row_id)
                    update_values.append(tuple(vals))

                if update_values:
                    cur.executemany(update_sql, update_values)

            conn.commit()
            print("\n✓ Änderungen aus dem Backup wurden erfolgreich übernommen.")


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
