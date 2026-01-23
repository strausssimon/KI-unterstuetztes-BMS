import sys
import os
# Füge Projekt-Root zum Python-Pfad hinzu
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

import psycopg
from psycopg import sql
from src.db_config import DB_CONFIG


def test_candidates_random(limit: int = 3) -> None:
    """Prüft Zugriff auf die Tabelle 'candidates' und gibt zufällig einige Einträge aus."""

    print("=" * 80)
    print("Test: Zugriff auf Tabelle 'candidates' und zufällige Auswahl")
    print("=" * 80 + "\n")

    try:
        with psycopg.connect(**DB_CONFIG, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                # Verbindungsinformationen ausgeben zur Kontrolle (DB, User, Host, Port, Schema)
                cur.execute(
                    """
                    SELECT
                        current_database(),
                        current_user,
                        inet_server_addr(),
                        inet_server_port()
                    """
                )
                db_name, db_user, db_host, db_port = cur.fetchone()

                cur.execute("SELECT current_schemas(true);")
                (schemas,) = cur.fetchone()

                print("Aktuelle Verbindung:")
                print(f"  Datenbank : {db_name}")
                print(f"  Benutzer  : {db_user}")
                print(f"  Host/Port : {db_host}:{db_port}")
                print(f"  Schemas   : {schemas}\n")

                # Prüfen, ob Tabelle existiert
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
                    print("  Bitte zuerst das Setup-Skript 'new_table_candidates.py' unter 'src/PostreSQL/Aufbau' ausführen.\n")
                    return

                print("✓ Tabelle 'candidates' gefunden.\n")

                # Prüfen, wie viele Einträge vorhanden sind
                cur.execute("SELECT COUNT(*) FROM candidates;")
                total = cur.fetchone()[0]
                print(f"Gesamtanzahl Kandidaten: {total}")

                if total == 0:
                    print("Keine Einträge in 'candidates' vorhanden.\n")
                    return

                # Zufällige Auswahl von max. 'limit' Einträgen
                cur.execute(
                    sql.SQL(
                        """
                        SELECT *
                        FROM candidates
                        ORDER BY random()
                        LIMIT %s;
                        """
                    ),
                    (limit,),
                )
                rows = cur.fetchall()
                col_names = [d[0] for d in cur.description]

                print(f"\nZufällige Auswahl von bis zu {limit} Einträgen (alle Spalten):\n")
                for idx, row in enumerate(rows, start=1):
                    record = dict(zip(col_names, row))
                    print(f"--- Kandidat {idx} ---")
                    for key, value in record.items():
                        if value is not None:
                            print(f"{key:25s}: {value}")
                    print()

                print("\n✓ Test erfolgreich abgeschlossen.\n")

    except psycopg.OperationalError as e:
        print("✗ Verbindungsfehler zur Datenbank:")
        print(f"  {e}\n")
        print("Bitte prüfen Sie Docker/PostgreSQL und die Zugangsdaten in DB_CONFIG.")
    except Exception as e:
        print(f"✗ Unerwarteter Fehler: {e}\n")


if __name__ == "__main__":
    test_candidates_random(limit=3)
