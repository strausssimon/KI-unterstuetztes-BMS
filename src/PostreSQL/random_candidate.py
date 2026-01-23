import sys
import os
# Füge Projekt-Root zum Python-Pfad hinzu
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

import psycopg
from psycopg import sql
from src.db_config import DB_CONFIG


def show_random_candidate() -> None:
    """Wählt zufällig einen Kandidaten aus der Tabelle 'candidates' und gibt ihn im Terminal aus."""

    print("=" * 80)
    print("Zufälliger Kandidat aus 'candidates'")
    print("=" * 80 + "\n")

    try:
        with psycopg.connect(**DB_CONFIG, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                # Existenz der Tabelle prüfen
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_name = 'candidates'
                    );
                    """
                )
                exists = cur.fetchone()[0]
                if not exists:
                    print("✗ Tabelle 'candidates' existiert nicht in der Datenbank.")
                    print("  Bitte zuerst 'new_table_candidates.py' unter 'src/PostreSQL/Aufbau' ausführen.\n")
                    return

                # Prüfen, ob Einträge vorhanden sind
                cur.execute("SELECT COUNT(*) FROM candidates;")
                total = cur.fetchone()[0]
                if total == 0:
                    print("Keine Einträge in 'candidates' vorhanden.\n")
                    return

                # Genau einen zufälligen Eintrag holen
                cur.execute(
                    sql.SQL(
                        """
                        SELECT *
                        FROM candidates
                        ORDER BY random()
                        LIMIT 1;
                        """
                    )
                )

                row = cur.fetchone()
                col_names = [d[0] for d in cur.description]
                record = dict(zip(col_names, row))

                print(f"Gesamtanzahl Kandidaten: {total}\n")
                print("Ausgewählter Kandidat:\n")

                # Wichtige Felder zuerst ausgeben, falls vorhanden
                for key in [
                    "id",
                    "first_name",
                    "last_name",
                    "position_now",
                    "department",
                    "wohnort",
                    "wunscharbeitsort",
                    "status",
                    "letzter_kontakt",
                ]:
                    if key in record and record[key] is not None:
                        print(f"{key:16s}: {record[key]}")

                # Optional alle übrigen Felder anzeigen
                print("\nWeitere Felder:")
                for key, value in record.items():
                    if key in [
                        "id",
                        "first_name",
                        "last_name",
                        "position_now",
                        "department",
                        "wohnort",
                        "wunscharbeitsort",
                        "status",
                        "letzter_kontakt",
                    ]:
                        continue
                    if value is not None:
                        print(f"{key:16s}: {value}")

                print("\n✓ Ausgabe abgeschlossen.\n")

    except psycopg.OperationalError as e:
        print("✗ Verbindungsfehler zur Datenbank:")
        print(f"  {e}\n")
        print("Bitte Docker/PostgreSQL und DB_CONFIG prüfen.")
    except Exception as e:
        print(f"✗ Unerwarteter Fehler: {e}\n")


if __name__ == "__main__":
    show_random_candidate()
