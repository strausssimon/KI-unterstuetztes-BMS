""" 
====================================================
Programmname : Skillsextraktion für Jobs
Beschreibung : Extrahiert Skills aus den Spalten job_description und long_note der
jobs-Tabelle unter Verwendung der Skill-Liste in data/skills.csv und
schreibt das Ergebnis in die Spalte sonstiges_anforderungen.

Ablauf:
- Skills aus data/skills.csv laden (Bezeichnung + Abkürzungen).
- Alle Jobs mit vorhandener Beschreibung, aber leerer sonstiges_anforderungen laden.
- Aus job_description und long_note werden Skills extrahiert.
- Vorschau für die ersten Einträge anzeigen.
- Nach Bestätigung wird sonstiges_anforderungen für diese Jobs aktualisiert.

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
        text: Inhalt aus job_description/long_note
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

            # 2) Unscharfe Suche (fuzzy partial ratio)
            score = fuzz.partial_ratio(text_lower, term_lower)
            if score >= fuzzy_threshold:
                found.add(canonical)
                break

    return found


def extract_and_update_job_skills() -> None:
    """Extrahiert Skills aus job_description/long_note und aktualisiert
    die Spalte sonstiges_anforderungen in der jobs-Tabelle."""

    print("\n" + "=" * 80)
    print("Skill-Extraktion für Jobs-Tabelle (sonstiges_anforderungen)")
    print("=" * 80)

    # 1. Skills laden
    try:
        print("\n1. Lade Skills aus data/skills.csv ...")
        skills_map = load_skills()
        print(f"✓ {len(skills_map)} Skill-Bezeichnungen geladen")
    except Exception as e:
        print(f"✗ Fehler beim Laden der Skills: {e}")
        return

    # 2. DB-Verbindung
    try:
        conn = psycopg.connect(**DB_CONFIG)
        cur = conn.cursor()
    except Exception as e:
        print(f"\n✗ Fehler bei der Datenbankverbindung: {e}")
        return

    try:
                # 3. Jobs laden: mit Beschreibung, aber ohne sonstiges_anforderungen
        print("\n2. Lade Jobs aus Datenbank ...")
        cur.execute(
            """
                        SELECT id, position, department, job_description, long_note, sonstiges_anforderungen
            FROM jobs
            WHERE (job_description IS NOT NULL AND job_description <> ''
                   OR long_note IS NOT NULL AND long_note <> '')
                            AND (sonstiges_anforderungen IS NULL OR sonstiges_anforderungen = '')
            ORDER BY id;
            """
        )

        jobs = cur.fetchall()
        print(f"✓ {len(jobs)} Jobs mit Beschreibung geladen")

        if not jobs:
            print("ℹ Keine Jobs zum Aktualisieren")
            cur.close()
            conn.close()
            return

        # 4. Analyse und Vorschau
        print("\n3. Analysiere job_description und long_note ...")
        print("\n" + "=" * 80)
        print("VORSCHAU (erste 10 Einträge)")
        print("=" * 80 + "\n")

        updates = []

        for idx, (job_id, position, department, job_desc, long_note, current_req) in enumerate(jobs):
            text_parts: List[str] = []
            if job_desc:
                text_parts.append(str(job_desc))
            if long_note:
                text_parts.append(str(long_note))

            if not text_parts:
                continue

            combined_text = "\n".join(text_parts)
            found_skills = extract_skills_from_text(combined_text, skills_map)

            if not found_skills:
                continue

            new_requirements = ", ".join(sorted(found_skills))

            updates.append(
                {
                    "id": job_id,
                    "position": position,
                    "department": department,
                    "job_description": job_desc,
                    "long_note": long_note,
                    "alt": current_req,
                    "neu": new_requirements,
                }
            )

            # Vorschau für die ersten 10 Einträge
            if len(updates) <= 10:
                print(f"Job ID {job_id}:")
                print(f"  Position: {position or '(leer)'}")
                print(f"  Department: {department or '(leer)'}")
                if job_desc:
                    jd_preview = str(job_desc)
                    print(
                        f"  job_description: {jd_preview[:80]}{'...' if len(jd_preview) > 80 else ''}"
                    )
                if long_note:
                    ln_preview = str(long_note)
                    print(
                        f"  long_note: {ln_preview[:80]}{'...' if len(ln_preview) > 80 else ''}"
                    )
                print(f"  sonstiges_anforderungen (alt): {current_req or '(leer)'}")
                print(f"  sonstiges_anforderungen (neu): {new_requirements}")
                print()

        if len(updates) > 10:
            print(f"... und {len(updates) - 10} weitere")

        print("\n" + "=" * 80)
        print(f"ZUSAMMENFASSUNG: {len(updates)} Jobs würden aktualisiert")
        print("=" * 80)

        if not updates:
            print("\nℹ Keine Änderungen erforderlich (keine Skills gefunden)")
            cur.close()
            conn.close()
            return

        # 5. Bestätigung
        antwort = input("\nMöchten Sie die Änderungen durchführen? (j/n): ").strip().lower()

        if antwort not in ["j", "ja", "y", "yes"]:
            print("✗ Abgebrochen")
            cur.close()
            conn.close()
            return

        # 6. Updates durchführen
        print("\n4. Führe Updates durch ...")

        erfolg = 0
        fehler = 0

        for update in updates:
            try:
                cur.execute(
                    """
                    UPDATE jobs
                    SET sonstiges_anforderungen = %s
                    WHERE id = %s;
                    """,
                    (update["neu"], update["id"]),
                )
                erfolg += 1
            except Exception as e:
                fehler += 1
                print(f"✗ Fehler bei Job ID {update['id']}: {e}")

        conn.commit()
        cur.close()
        conn.close()

        print("\n" + "=" * 80)
        print("ERGEBNIS")
        print("=" * 80)
        print(f"✓ {erfolg} Jobs erfolgreich aktualisiert")
        if fehler > 0:
            print(f"✗ {fehler} Fehler aufgetreten")
        print("=" * 80)

    except Exception as e:
        print(f"\n✗ Fehler: {e}")
        import traceback

        traceback.print_exc()
        try:
            cur.close()
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    extract_and_update_job_skills()
