""" 
====================================================
Programmname : Extrahiere Skills aus long_note
Beschreibung : Extrahiert Skills aus der Spalte long_note eines Kandidaten
und schreibt das Ergebnis in die Spalte skills der Tabelle candidates.

Ablauf:
- Nutzer gibt Kandidaten-ID an.
- Skript lädt long_note und aktuelle skills aus der DB.
- Aus long_note werden Skills anhand von Bezeichnung und Abkürzungen
  aus data/skills.csv extrahiert.
- Gefundene Skills werden angezeigt, zusammen mit Kandidatenname und ID.
- Nach Bestätigung wird die Spalte skills für diesen Kandidaten aktualisiert.

====================================================
"""

import sys
import os
import re
from typing import Dict, List, Set

# Projekt-Root zum Python-Pfad hinzufügen
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

import psycopg
import pandas as pd
from fuzzywuzzy import fuzz
from src.db_config import DB_CONFIG

# Pfad zur Skills-CSV (relativ zum Projekt-Root)
SKILLS_CSV = r"data\skills.csv"


def load_skills() -> Dict[str, List[str]]:
    """Lädt Skills aus data/skills.csv.

    Rückgabe:
        dict: {canonical_skill_name: [suchbegriffe...]}
    """
    csv_path = os.path.join(project_root, SKILLS_CSV)
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Skills-CSV nicht gefunden: {csv_path}")

    df = pd.read_csv(csv_path)

    # Erwartete Spaltennamen: "Bezeichnung", "Gängige Abkürzungen"
    if "Bezeichnung" not in df.columns:
        raise ValueError("Spalte 'Bezeichnung' fehlt in skills.csv")

    search_map: Dict[str, List[str]] = {}

    for _, row in df.iterrows():
        name = str(row["Bezeichnung"]).strip()
        if not name:
            continue

        # Basis-Suchbegriffe: Bezeichnung selbst
        terms: List[str] = [name]

        # Optionale Abkürzungen / Synonyme
        abbrev_col = row.get("Gängige Abkürzungen")
        if isinstance(abbrev_col, str) and abbrev_col.strip():
            # Komma-separierte Liste
            for part in abbrev_col.split(","):
                term = part.strip()
                if term:
                    terms.append(term)

        # Alles in Kleinbuchstaben für die Suche
        lower_terms = sorted({t.lower() for t in terms})
        if lower_terms:
            search_map[name] = lower_terms

    return search_map


def extract_skills_from_text(
    text: str,
    skills_map: Dict[str, List[str]],
    fuzzy_threshold: int = 85,
) -> Set[str]:
    """Extrahiert Skills aus einem Freitext.

    Args:
        text: Inhalt aus long_note
        skills_map: {canonical_name: [suchbegriffe...]}

    Returns:
        Set mit gefundenen canonical skill names
    """
    if not text or pd.isna(text):
        return set()

    text_lower = str(text).lower()

    found: Set[str] = set()

    for canonical, terms in skills_map.items():
        for term in terms:
            term_lower = term.lower()
            # 1) Exakte Wort-Treffer (schnell und präzise)
            pattern = r"\b" + re.escape(term_lower) + r"\b"
            if re.search(pattern, text_lower):
                found.add(canonical)
                break  # für dieses canonical reicht ein Treffer

            # 2) Unscharfe Suche analog search.py (fuzzy partial ratio)
            score = fuzz.partial_ratio(text_lower, term_lower)
            if score >= fuzzy_threshold:
                found.add(canonical)
                break

    return found


def main() -> int:
    print("=" * 80)
    print("Skills aus long_note extrahieren (ein Kandidat)")
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

        # 4. Kandidaten-Daten laden
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, first_name, last_name, long_note, skills
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

        cand_id_db, first_name, last_name, long_note, current_skills = row

        print("\nKandidat:")
        print(f"- ID:        {cand_id_db}")
        print(f"- Name:      {first_name} {last_name}")
        print(f"- Aktuelle Skills: {current_skills or '(leer)'}")

        preview = (long_note or "").strip()
        if preview:
            print("\nAuszug aus long_note (max. 300 Zeichen):")
            print(preview[:300] + ("..." if len(preview) > 300 else ""))
        else:
            print("\nlong_note ist leer – keine Skills zu extrahieren.")
            conn.close()
            return 0

        # 5. Skills extrahieren
        print("\n2. Extrahiere Skills aus long_note ...")
        found_skills = extract_skills_from_text(long_note, skills_map)

        if not found_skills:
            print("✗ Keine Skills in long_note gefunden. Spalte skills bleibt unverändert.")
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

        # Sortiert und kommasepariert
        new_skills = ", ".join(sorted(all_skills))

        print("\nGefundene Skills (Vorschlag, inkl. bereits vorhandener Skills):")
        print(f"{new_skills}")

        # 6. Bestätigung
        confirm = input("\nNeue Skills in der DB speichern? (j/n): ").strip().lower()
        if confirm not in ["j", "ja", "y", "yes"]:
            print("\n✗ Abgebrochen – es wurden keine Änderungen vorgenommen.")
            conn.close()
            return 0

        # 7. Update in der DB
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
