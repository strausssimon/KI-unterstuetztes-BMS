""" 
====================================================
Programmname : Extrahiere Skills aus cv_pdf (PDF)
Beschreibung : Extrahiert Skills aus dem in der Spalte cv_pdf gespeicherten PDF eines
Kandidaten (BYTEA) und schreibt das Ergebnis in die Spalte skills der
Tabelle candidates.

Ablauf:
- Nutzer gibt Kandidaten-ID an.
- Skript lädt cv_pdf (PDF-Bytes) und aktuelle skills aus der DB.
- PDF wird zu Text extrahiert.
- Aus dem Text werden Skills anhand von Bezeichnung und Abkürzungen
  aus data/skills.csv extrahiert (mit exakter + unscharfer Suche).
- Gefundene Skills werden angezeigt, zusammen mit Kandidatenname und ID.
- Nach Bestätigung wird die Spalte skills für diesen Kandidaten aktualisiert.

====================================================
"""

import sys
import os
import io
import re
from typing import Dict, List, Set

# Projekt-Root zum Python-Pfad hinzufügen
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

import psycopg
import pandas as pd
from fuzzywuzzy import fuzz
from PyPDF2 import PdfReader
from src.db_config import DB_CONFIG

# Pfad zur Skills-CSV (relativ zum Projekt-Root)
SKILLS_CSV = r"data\\skills.csv"


def load_skills() -> Dict[str, List[str]]:
    """Lädt Skills aus data/skills.csv.

    Rückgabe:
        dict: {canonical_skill_name: [suchbegriffe...]}
    """
    csv_path = os.path.join(project_root, SKILLS_CSV)
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Skills-CSV nicht gefunden: {csv_path}")

    df = pd.read_csv(csv_path)

    if "Bezeichnung" not in df.columns:
        raise ValueError("Spalte 'Bezeichnung' fehlt in skills.csv")

    search_map: Dict[str, List[str]] = {}

    for _, row in df.iterrows():
        name = str(row["Bezeichnung"]).strip()
        if not name:
            continue

        terms: List[str] = [name]

        abbrev_col = row.get("Gängige Abkürzungen")
        if isinstance(abbrev_col, str) and abbrev_col.strip():
            for part in abbrev_col.split(","):
                term = part.strip()
                if term:
                    terms.append(term)

        lower_terms = sorted({t.lower() for t in terms})
        if lower_terms:
            search_map[name] = lower_terms

    return search_map


def extract_skills_from_text(
    text: str,
    skills_map: Dict[str, List[str]],
    fuzzy_threshold: int = 85,
) -> Set[str]:
    """Extrahiert Skills aus einem Freitext (analog long_note-Skript)."""
    if not text or pd.isna(text):
        return set()

    text_lower = str(text).lower()

    found: Set[str] = set()

    for canonical, terms in skills_map.items():
        for term in terms:
            term_lower = term.lower()
            # 1) Exakte Wort-Treffer
            pattern = r"\b" + re.escape(term_lower) + r"\b"
            if re.search(pattern, text_lower):
                found.add(canonical)
                break

            # 2) Unscharfe Suche via fuzzywuzzy
            score = fuzz.partial_ratio(text_lower, term_lower)
            if score >= fuzzy_threshold:
                found.add(canonical)
                break

    return found


def pdf_bytes_to_text(pdf_bytes: bytes) -> str:
    """Extrahiert Text aus PDF-Bytes mittels PyPDF2."""
    if not pdf_bytes:
        return ""

    try:
        with io.BytesIO(pdf_bytes) as bio:
            reader = PdfReader(bio)
            pages_text: List[str] = []
            for page in reader.pages:
                try:
                    page_text = page.extract_text() or ""
                except Exception:
                    page_text = ""
                pages_text.append(page_text)
        return "\n".join(pages_text)
    except Exception:
        return ""


def main() -> int:
    print("=" * 80)
    print("Skills aus cv_pdf (PDF) extrahieren (ein Kandidat)")
    print("=" * 80)

    # 1. Skills laden
    try:
        print("\n1. Lade Skills aus data/skills.csv ...")
        skills_map = load_skills()
        print(f"✓ {len(skills_map)} Skill-Bezeichnungen geladen")
    except Exception as e:
        print(f"✗ Fehler beim Laden der Skills: {e}")
        return 1

    # 2. DB-Verbindung
    try:
        conn = psycopg.connect(**DB_CONFIG)
    except Exception as e:
        print(f"\n✗ Fehler bei der Datenbankverbindung: {e}")
        return 1

    try:
        # 3. Kandidaten-ID abfragen (als Text, passend zu VARCHAR-ID)
        candidate_id = input("\nID des Kandidaten (z.B. 762): ").strip()
        if not candidate_id:
            print("\n✗ Keine ID angegeben – Vorgang abgebrochen.")
            conn.close()
            return 1

        # 4. Kandidaten-Daten laden (inkl. cv_pdf)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, first_name, last_name, cv_pdf, skills
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

        cand_id_db, first_name, last_name, cv_pdf, current_skills = row

        print("\nKandidat:")
        print(f"- ID:        {cand_id_db}")
        print(f"- Name:      {first_name} {last_name}")
        print(f"- Aktuelle Skills: {current_skills or '(leer)'}")

        if cv_pdf is None:
            print("\n✗ Kein CV in cv_pdf gespeichert – keine Skills zu extrahieren.")
            conn.close()
            return 0

        # 5. PDF in Text umwandeln
        print("\n2. Extrahiere Text aus cv_pdf ...")
        text = pdf_bytes_to_text(cv_pdf)

        if not text.strip():
            print("✗ Konnte keinen Text aus dem PDF extrahieren.")
            conn.close()
            return 0

        preview = text.strip()
        print("\nAuszug aus CV-Text (max. 500 Zeichen):")
        print(preview[:500] + ("..." if len(preview) > 500 else ""))

        # 6. Skills extrahieren
        print("\n3. Extrahiere Skills aus CV-Text ...")
        found_skills = extract_skills_from_text(text, skills_map)

        if not found_skills:
            print("✗ Keine Skills im CV-Text gefunden. Spalte skills bleibt unverändert.")
            conn.close()
            return 0

        # Bisherige Skills aus der DB in ein Set umwandeln
        existing_set = set()
        if current_skills:
            for part in str(current_skills).split(","):
                name = part.strip()
                if name:
                    existing_set.add(name)

        # Vereinigung aus bestehenden und neu gefundenen Skills bilden
        all_skills = existing_set.union(found_skills)

        # Wenn sich nichts ändert, Hinweis ausgeben und abbrechen
        if all_skills == existing_set:
            print("ℹ Alle gefundenen Skills sind bereits eingetragen. Keine Aktualisierung notwendig.")
            conn.close()
            return 0

        new_skills = ", ".join(sorted(all_skills))

        print("\nGefundene Skills (Vorschlag, inkl. bereits vorhandener Skills):")
        print(new_skills)

        # 7. Bestätigung
        confirm = input("\nNeue Skills in der DB speichern? (j/n): ").strip().lower()
        if confirm not in ["j", "ja", "y", "yes"]:
            print("\n✗ Abgebrochen – es wurden keine Änderungen vorgenommen.")
            conn.close()
            return 0

        # 8. Update in der DB
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE candidates SET skills = %s WHERE id = %s",
                (new_skills, cand_id_db),
            )
        conn.commit()

        print("\n✓ Skills aktualisiert.")
        print(f"- Kandidat: {first_name} {last_name} (ID {cand_id_db})")
        print(f"- Neue Skills: {new_skills}")

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
