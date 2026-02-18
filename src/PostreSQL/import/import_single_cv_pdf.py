r"""
Interaktiver Import einer einzelnen PDF-Datei in die candidates-Tabelle (cv_pdf BYTEA Spalte).

Ablauf:
- Nutzer gibt relativen oder absoluten Pfad zur PDF an, z.B. "data\db\CV\CV 1.pdf".
- Nutzer gibt die Kandidaten-ID an, z.B. 762.
- Das Skript lädt Nachname, Vorname und ID aus der Datenbank,
  fasst alles zusammen und fragt zur Sicherheit noch einmal nach.
- Bei Bestätigung wird das PDF in die Spalte cv_pdf des Kandidaten geschrieben.
"""

import sys
import os

# Projekt-Root zum Python-Pfad hinzufügen
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

import psycopg
from src.db_config import DB_CONFIG


def ensure_cv_pdf_column_exists(conn):
    """Prüft, ob die Spalte cv_pdf in candidates existiert."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'candidates'
              AND column_name = 'cv_pdf';
            """
        )
        if not cur.fetchone():
            print("\n✗ Spalte cv_pdf existiert nicht!")
            print("Bitte führen Sie zuerst aus:")
            print("  python src/PostreSQL/Aufbau/add_cv_pdf_column.py")
            return False
    return True


def import_pdf_to_candidate(candidate_id: str, pdf_path: str, conn) -> tuple[bool, float | str]:
    """Importiert ein PDF in die Datenbank für einen bestimmten Kandidaten.

    Rückgabe: (success, file_size_kb_oder_fehlermeldung)
    """
    try:
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE candidates SET cv_pdf = %s WHERE id = %s",
                (pdf_data, candidate_id),
            )

        file_size_kb = len(pdf_data) / 1024.0
        return True, file_size_kb
    except Exception as e:  # pragma: no cover - reine I/O-Fehlerbehandlung
        return False, str(e)


def main() -> int:
    print("=" * 60)
    print("CV PDF Einzel-Import")
    print("=" * 60)

    try:
        conn = psycopg.connect(**DB_CONFIG)
    except Exception as e:
        print(f"\n✗ Fehler bei der Datenbankverbindung: {e}")
        return 1

    try:
        # 1. Prüfe, ob cv_pdf Spalte existiert
        if not ensure_cv_pdf_column_exists(conn):
            conn.close()
            return 1

        # 2. Pfad zur PDF-Datei abfragen
        print("\nBitte geben Sie den Pfad zur PDF-Datei an.")
        print("Beispiel: data\\db\\CV\\CV 1.pdf")
        pdf_input = input("Pfad zur PDF-Datei: ").strip()

        if not pdf_input:
            print("\n✗ Kein Pfad angegeben – Vorgang abgebrochen.")
            conn.close()
            return 1

        # Relativen Pfad in absoluten Pfad umwandeln
        if os.path.isabs(pdf_input):
            pdf_path = pdf_input
        else:
            pdf_path = os.path.join(project_root, pdf_input)
        pdf_path = os.path.normpath(pdf_path)

        if not os.path.exists(pdf_path):
            print(f"\n✗ Datei nicht gefunden: {pdf_path}")
            conn.close()
            return 1

        if not pdf_path.lower().endswith(".pdf"):
            print(f"\n✗ Datei ist keine PDF: {pdf_path}")
            conn.close()
            return 1

        # 3. Kandidaten-ID abfragen (als Text, damit sie zu einer VARCHAR-ID-Spalte passt)
        candidate_id = input("\nID des Kandidaten (z.B. 762): ").strip()
        if not candidate_id:
            print("\n✗ Keine ID angegeben – Vorgang abgebrochen.")
            conn.close()
            return 1

        # 4. Kandidaten-Daten laden
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, first_name, last_name FROM candidates WHERE id = %s",
                (candidate_id,),
            )
            row = cur.fetchone()

        if not row:
            print(f"\n✗ Kein Kandidat mit ID {candidate_id} gefunden.")
            conn.close()
            return 1

        cand_id_db, first_name, last_name = row

        # 5. Zusammenfassung und Bestätigung
        print("\nZusammenfassung:")
        print("- Datei:   ", pdf_input)
        print("- Pfad:    ", pdf_path)
        print(f"- Kandidat: {last_name}, {first_name} (ID {cand_id_db})")

        confirm = input("\nMöchten Sie dieses PDF wirklich zuordnen? (j/n): ").strip().lower()
        if confirm not in ["j", "ja", "y", "yes"]:
            print("\n✗ Import abgebrochen – es wurden keine Änderungen vorgenommen.")
            conn.close()
            return 0

        # 6. Import durchführen
        success, result = import_pdf_to_candidate(cand_id_db, pdf_path, conn)
        if success:
            conn.commit()
            print(
                f"\n✓ PDF erfolgreich importiert für {last_name}, {first_name} (ID {cand_id_db}) "
                f"– Größe: {result:.1f} KB"
            )
            conn.close()
            return 0
        else:
            conn.rollback()
            print(f"\n✗ Fehler beim Import: {result}")
            conn.close()
            return 1

    except Exception as e:  # pragma: no cover - generische Fehlerbehandlung
        print(f"\n✗ Unerwarteter Fehler: {e}")
        import traceback

        traceback.print_exc()
        try:
            conn.close()
        except Exception:
            pass
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
