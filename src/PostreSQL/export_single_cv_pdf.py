"""
Exportiert das CV eines einzelnen Kandidaten aus der candidates-Tabelle (cv_pdf BYTEA Spalte).

Ablauf:
- Nutzer gibt die Kandidaten-ID an.
- Nutzer gibt einen relativen oder absoluten Zielpfad/Ordner an, z.B. "data\\db\\CV\\export".
- Das Skript lädt Nachname, Vorname und ID aus der Datenbank.
- Es erzeugt einen Dateinamen z.B. "{id}_{vorname}_{nachname}.pdf" im Zielordner.
- Bei Bestätigung wird das PDF dort gespeichert.
"""

import sys
import os

# Projekt-Root ermitteln und zum Python-Pfad hinzufügen
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

import psycopg
from src.db_config import DB_CONFIG


def ensure_cv_pdf_column_exists(conn) -> bool:
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


def sanitize_filename(name: str) -> str:
    """Bereinigt Namen für Dateinamen."""
    if not name:
        return "unbekannt"

    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        " ": "_",
        "/": "_",
        "\\": "_",
        ":": "_",
        "*": "_",
        "?": "_",
        '"': "_",
        "<": "_",
        ">": "_",
        "|": "_",
    }

    for old, new in replacements.items():
        name = name.replace(old, new)

    return name


def main() -> int:
    print("=" * 60)
    print("CV PDF Einzel-Export")
    print("=" * 60)

    try:
        conn = psycopg.connect(**DB_CONFIG)
    except Exception as e:
        print(f"\n✗ Fehler bei der Datenbankverbindung: {e}")
        return 1

    try:
        # 1. Prüfen, ob cv_pdf Spalte existiert
        if not ensure_cv_pdf_column_exists(conn):
            conn.close()
            return 1

        # 2. Kandidaten-ID abfragen (als Text, analog zum Einzel-Import)
        candidate_id = input("\nID des Kandidaten (z.B. 762): ").strip()
        if not candidate_id:
            print("\n✗ Keine ID angegeben – Vorgang abgebrochen.")
            conn.close()
            return 1

        # 3. Kandidaten-Daten inkl. PDF laden
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, first_name, last_name, cv_pdf
                FROM candidates
                WHERE id = %s
                """,
                (candidate_id,),
            )
            row = cur.fetchone()

        if not row:
            print(f"\n✗ Kein Kandidat mit ID {candidate_id} gefunden.")
            conn.close()
            return 1

        cand_id_db, first_name, last_name, pdf_data = row

        if pdf_data is None:
            print(f"\n✗ Kandidat {cand_id_db} ({first_name} {last_name}) hat kein CV in der Datenbank.")
            conn.close()
            return 1

        # 4. Zielpfad/-ordner abfragen
        print("\nBitte geben Sie den Zielordner oder eine Zieldatei an.")
        print("Beispiel Ordner: data\\db\\CV\\export")
        target_input = input("Ziel (Ordner oder Datei): ").strip()

        if not target_input:
            print("\n✗ Kein Ziel angegeben – Vorgang abgebrochen.")
            conn.close()
            return 1

        # Relativ zu project_root, falls nicht absolut
        if os.path.isabs(target_input):
            target_path = target_input
        else:
            target_path = os.path.join(project_root, target_input)
        target_path = os.path.normpath(target_path)

        # Wenn ein Ordner angegeben wurde, Dateinamen erzeugen
        if os.path.isdir(target_path) or target_path.endswith(os.sep):
            # Sicherstellen, dass der Ordner existiert
            if not os.path.exists(target_path):
                os.makedirs(target_path, exist_ok=True)

            first_name_clean = sanitize_filename(first_name or "")
            last_name_clean = sanitize_filename(last_name or "")
            filename = f"{cand_id_db}_{first_name_clean}_{last_name_clean}.pdf"
            full_path = os.path.join(target_path, filename)
        else:
            # target_path ist eine Datei oder ein noch nicht existierender Pfad
            folder = os.path.dirname(target_path)
            if folder and not os.path.exists(folder):
                os.makedirs(folder, exist_ok=True)
            # Falls keine .pdf-Endung, anhängen
            if not target_path.lower().endswith(".pdf"):
                target_path = target_path + ".pdf"
            full_path = target_path

        # 5. Zusammenfassung und Bestätigung
        print("\nZusammenfassung:")
        print(f"- Kandidat: {last_name}, {first_name} (ID {cand_id_db})")
        print(f"- Zieldatei: {full_path}")

        confirm = input("\nMöchten Sie dieses CV wirklich exportieren? (j/n): ").strip().lower()
        if confirm not in ["j", "ja", "y", "yes"]:
            print("\n✗ Export abgebrochen – es wurden keine Dateien geschrieben.")
            conn.close()
            return 0

        # 6. Datei schreiben
        try:
            with open(full_path, "wb") as f:
                f.write(pdf_data)

            size_kb = len(pdf_data) / 1024.0
            print(
                f"\n✓ CV exportiert nach {full_path} "
                f"({size_kb:.1f} KB) für {last_name}, {first_name} (ID {cand_id_db})"
            )
        except Exception as e:
            print(f"\n✗ Fehler beim Schreiben der Datei: {e}")
            conn.close()
            return 1

        conn.close()
        return 0

    except Exception as e:
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
