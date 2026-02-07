import sys
import os
# Füge Projekt-Root zum Python-Pfad hinzu
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

import psycopg
import pandas as pd
import math
import re
from datetime import datetime
from src.db_config import DB_CONFIG

# --------------------------------------------------
# KONFIGURATION
# --------------------------------------------------

RESULTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "results"
)

CSV_PATH = r"data\Staedte_Deutschland.csv"

WEIGHT_SALARY = 0.7
WEIGHT_DRIVE = 0.3
MAX_SCORE_COMPONENTS = 2
WEIGHT_SKILL = 0.3

# --------------------------------------------------
# KARRIEREL0GIK
# --------------------------------------------------
KARRIERE_PFADE = {
    "assistenzarzt": {"assistenzarzt", "facharzt"},
    "facharzt": {"facharzt", "oberarzt", "standortleiter", "gesellschafter"},
    "oberarzt": {"oberarzt", "leitender oberarzt", "standortleiter", "gesellschafter"},
    "leitender oberarzt": {"leitender oberarzt", "chefarzt", "standortleiter", "gesellschafter"},
    "chefarzt": {"chefarzt", "standortleiter", "gesellschafter"},
    "standortleiter": {"standortleiter", "gesellschafter"},
    "gesellschafter": {"gesellschafter"}
}

def normalize(text):
    return text.lower().strip() if text else ""

def extract_level(text):
    text = normalize(text)
    for lvl in KARRIERE_PFADE:
        if lvl in text:
            return lvl
    return None

def career_match(candidate_pos, job_pos):
    cand = extract_level(candidate_pos)
    job = extract_level(job_pos)
    if not cand or not job:
        return False
    return job in KARRIERE_PFADE.get(cand, set())

# --------------------------------------------------
# GEO
# --------------------------------------------------
df_cities = pd.read_csv(CSV_PATH)
df_cities["place"] = df_cities["place"].str.lower().str.strip()

def extract_city(text):
    if not text:
        return None
    return text.lower().split(",")[0].strip()

def get_coords(city):
    if not city:
        return None, None
    row = df_cities[df_cities["place"] == city]
    if row.empty:
        return None, None
    return row.iloc[0]["latitude"], row.iloc[0]["longitude"]

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# --------------------------------------------------
# DATABASE
# --------------------------------------------------
def load_job(job_id):
    conn = psycopg.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, position, department, ort, gehalt_von, gehalt_bis, sonstiges_anforderungen
        FROM jobs WHERE id = %s
    """, (job_id,))
    row = cur.fetchone()
    
    if not row:
        cur.close()
        conn.close()
        raise ValueError(f"Job mit ID {job_id} nicht gefunden")
    
    cur.close()
    conn.close()

    job = dict(zip(
        ["id", "position", "department", "ort", "gehalt_von", "gehalt_bis", "sonstiges_anforderungen"], row
    ))
    
    # Debug-Ausgabe der geladenen Rohdaten
    print(f"\n[DEBUG] Geladene Job-Daten (roh):")
    for key, value in job.items():
        print(f"  {key}: '{value}' (Type: {type(value).__name__})")

    job["position"] = normalize(job["position"]) if job["position"] else ""
    job["department"] = normalize(job["department"]) if job["department"] else ""
    job["ort"] = extract_city(job["ort"]) if job["ort"] else None
    return job

def load_candidates():
    conn = psycopg.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, first_name, last_name, status, position_now, department,
               gehaltswunsch, wohnort, wunscharbeitsort, regionale_verfuegbarkeit, skills
        FROM candidates
        WHERE status != 'not interested'
    """)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    cur.close()
    conn.close()

    kandidaten = []
    for r in rows:
        k = dict(zip(cols, r))
        for f in ["position_now", "department", "wohnort", "wunscharbeitsort"]:
            k[f] = normalize(k.get(f))
        try:
            k["gehaltswunsch"] = int(str(k.get("gehaltswunsch")).replace(".", "").replace(",", ""))
        except:
            k["gehaltswunsch"] = None

        rv = normalize(k.get("regionale_verfuegbarkeit"))
        if "deutschland" in rv:
            k["regionale_verfuegbarkeit"] = 1000
        else:
            nums = re.findall(r"\d+", rv)
            k["regionale_verfuegbarkeit"] = int(nums[0]) if nums else 50

        kandidaten.append(k)

    print(f"✓ {len(kandidaten)} Kandidaten geladen")
    return kandidaten

# --------------------------------------------------
# SCORING
# --------------------------------------------------
def salary_score(s, jmin, jmax):
    if s is None or jmin is None or jmax is None:
        return None
    if s < jmin: return 5
    if jmin <= s <= jmax: return 4
    if s <= jmax * 1.05: return 3
    if s <= jmax * 1.10: return 2
    return 1

def fahrtweg_score(c, job_city):
    job_lat, job_lon = get_coords(job_city)
    if not job_lat:
        return None, None

    best = None
    for f in ["wohnort", "wunscharbeitsort"]:
        city = extract_city(c.get(f))
        lat, lon = get_coords(city)
        if lat:
            d = haversine(job_lat, job_lon, lat, lon)
            best = d if best is None else min(best, d)

    if best is None:
        return None, None

    max_km = c.get("regionale_verfuegbarkeit", 50)
    if best <= 10: score = 5
    elif best <= max_km * 0.5: score = 4
    elif best <= max_km: score = 3
    elif best <= max_km * 1.5: score = 2
    else: score = 1

    return score, round(best, 1)


def _parse_skill_list(text):
    """Hilfsfunktion: wandelt eine kommaseparierte Skill-Liste in ein Set um."""
    if not text:
        return set()
    return {
        part.strip().lower()
        for part in str(text).split(",")
        if part.strip()
    }


def skill_overlap(job_requirements, candidate_skills):
    """Berechnet die Überlappung zwischen Job-Skills und Kandidaten-Skills.

    Rückgabewert:
        float in [0, 1]: Anteil der Job-Skills, die beim Kandidaten vorhanden sind.
        0.0, wenn keine oder leere Listen.
    """
    req_set = _parse_skill_list(job_requirements)
    cand_set = _parse_skill_list(candidate_skills)

    if not req_set or not cand_set:
        return 0.0

    inter = req_set & cand_set
    if not inter:
        return 0.0

    return len(inter) / len(req_set)

# --------------------------------------------------
# MATCHING
# --------------------------------------------------
def match_candidates(job, candidates):
    matches = []

    for c in candidates:
        if not career_match(c.get("position_now"), job["position"]):
            continue

        fachbereiche = [f.strip() for f in (c.get("department") or "").split(",")]
        if job["department"] not in fachbereiche:
            continue

        # Skill-Matching: nur Kandidaten behalten, bei denen sich
        # mindestens ein Skill mit den Job-Anforderungen überschneidet
        skill_match_score = None
        skill_score = None
        skills_job = None
        skills_kandidat = None
        skills_gemeinsam = None
        skills_fehlend = None

        if job.get("sonstiges_anforderungen"):
            job_reqs = job.get("sonstiges_anforderungen")
            cand_skills = c.get("skills")

            job_set = _parse_skill_list(job_reqs)
            cand_set = _parse_skill_list(cand_skills)

            # Berechne Schnittmenge und fehlende Skills (case-insensitiv)
            inter_lower = job_set & cand_set
            if not inter_lower:
                # Kein einziger Skill überschneidet sich -> Kandidat überspringen
                continue

            missing_lower = job_set - cand_set

            # Original-Schreibweise aus den Strings rekonstruieren
            job_list = [p.strip() for p in str(job_reqs).split(",") if p.strip()]
            cand_list = [p.strip() for p in str(cand_skills).split(",") if p.strip()] if cand_skills else []

            job_map = {p.lower(): p for p in job_list}

            skills_job = ", ".join(job_list) if job_list else None
            skills_kandidat = ", ".join(cand_list) if cand_list else None
            skills_gemeinsam = ", ".join(
                sorted({job_map.get(s, s) for s in inter_lower})
            ) if inter_lower else None
            skills_fehlend = ", ".join(
                sorted({job_map.get(s, s) for s in missing_lower})
            ) if missing_lower else None

            # Overlap-Ratio und abgeleiteter Skill-Score (1-5)
            skill_match_score = len(inter_lower) / len(job_set) if job_set else 0.0
            # Mappe (0,1] auf [1,5]
            skill_score = 1 + int(skill_match_score * 4) if skill_match_score > 0 else None

        sal = salary_score(c.get("gehaltswunsch"), job["gehalt_von"], job["gehalt_bis"])
        drv, dist = fahrtweg_score(c, job["ort"])

        gewicht = 0
        summe = 0
        comps = 0

        if sal is not None:
            summe += sal * WEIGHT_SALARY
            gewicht += WEIGHT_SALARY
            comps += 1
        if drv is not None:
            summe += drv * WEIGHT_DRIVE
            gewicht += WEIGHT_DRIVE
            comps += 1
        if skill_score is not None:
            summe += skill_score * WEIGHT_SKILL
            gewicht += WEIGHT_SKILL

        avg = round(summe / gewicht, 2) if gewicht else None
        voll = comps / MAX_SCORE_COMPONENTS

        fehlend = []
        if sal is None: fehlend.append("Gehalt")
        if drv is None: fehlend.append("Fahrtweg")

        matches.append({
            "id": c["id"],
            "name": f"{c.get('first_name')} {c.get('last_name')}",
            "position_now": c.get("position_now"),
            "gehaltswunsch": c.get("gehaltswunsch"),
            "gehalts_score": sal,
            "fahrtweg_score": drv,
            "fahrtweg_km": dist,
            "gesamt_score": avg,
            "skill_match": skill_match_score,
            "skill_score": skill_score,
            "skills_job": skills_job,
            "skills_kandidat": skills_kandidat if skills_kandidat is not None else c.get("skills"),
            "skills_gemeinsam": skills_gemeinsam,
            "skills_fehlend": skills_fehlend,
            "datenvollstaendigkeit": voll,
            "fehlende_daten": fehlend
        })

    # Sortierung: 
    # 1. Kandidaten MIT Score vor Kandidaten OHNE Score
    # 2. Bei gleichem Score-Status: Höhere Datenvollständigkeit bevorzugt
    # 3. Dann höherer Gesamt-Score
    matches.sort(
        key=lambda x: (
            x["gesamt_score"] is None,           # Kandidaten ohne Score ans Ende
            -x["datenvollstaendigkeit"],          # Mehr Daten = besser
            -(x["gesamt_score"] or 0)             # Höherer Score = besser
        )
    )
    return matches

# --------------------------------------------------
# EXCEL EXPORT
# --------------------------------------------------
def export_to_excel(job, candidates_data, results, output_dir=RESULTS_DIR):
    """
    Exportiert Matching-Ergebnisse als Excel-Datei mit vollständigen Kandidaten- und Job-Daten
    """
    # Erstelle Verzeichnis falls nicht vorhanden
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Dateiname mit Timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"matching_job_{job['id']}_{timestamp}.xlsx"
    filepath = os.path.join(output_dir, filename)
    
    # Lade vollständige Kandidatendaten aus DB
    conn = psycopg.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Hole IDs der gematchten Kandidaten
    candidate_ids = [r['id'] for r in results]
    
    if not candidate_ids:
        print("⚠ Keine Kandidaten zum Exportieren")
        cur.close()
        conn.close()
        return None
    
    # Lade vollständige Kandidatendaten
    placeholders = ','.join(['%s'] * len(candidate_ids))
    cur.execute(f"""
        SELECT id, first_name, last_name, e_mail, tel, position_now, 
               department, gehaltswunsch, wohnort, wunscharbeitsort, 
               regionale_verfuegbarkeit, status, qualification, 
               next_career_step, short_note, skills
        FROM candidates
        WHERE id IN ({placeholders});
    """, candidate_ids)
    
    candidates_full = cur.fetchall()
    cols_candidates = [desc[0] for desc in cur.description]
    
    # Lade vollständige Job-Daten
    cur.execute("""
        SELECT id, position, department, ort, gehalt_von, gehalt_bis,
               job_description, long_note, klinik
        FROM jobs
        WHERE id = %s;
    """, (job['id'],))
    
    job_full = cur.fetchone()
    cols_job = [desc[0] for desc in cur.description]
    
    cur.close()
    conn.close()
    
    # Erstelle DataFrames
    df_candidates = pd.DataFrame(candidates_full, columns=cols_candidates)
    df_job = pd.DataFrame([job_full], columns=cols_job)
    
    # Erstelle Matching-Ergebnisse DataFrame
    matching_results = []
    for r in results:
        matching_results.append({
            'kandidat_id': r['id'],
            'kandidat_name': r['name'],
            'gesamt_score': r['gesamt_score'],
            'gehalts_score': r['gehalts_score'],
            'fahrtweg_score': r['fahrtweg_score'],
            'fahrtweg_km': r['fahrtweg_km'],
            'skill_match': r.get('skill_match'),
            'skill_score': r.get('skill_score'),
            'skills_gemeinsam': r.get('skills_gemeinsam'),
            'skills_fehlend': r.get('skills_fehlend'),
            'datenvollstaendigkeit': f"{int(r['datenvollstaendigkeit']*100)}%",
            'fehlende_daten': ', '.join(r['fehlende_daten']) if r['fehlende_daten'] else 'Keine'
        })
    
    df_matching = pd.DataFrame(matching_results)
    
    # Merge Kandidaten mit Matching-Ergebnissen
    df_export = df_matching.merge(
        df_candidates, 
        left_on='kandidat_id', 
        right_on='id', 
        how='left'
    )
    
    # Speichere als Excel mit mehreren Sheets
    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        # Sheet 1: Matching-Übersicht
        df_export.to_excel(writer, sheet_name='Matching_Ergebnisse', index=False)
        
        # Sheet 2: Job-Details
        df_job.to_excel(writer, sheet_name='Job_Details', index=False)
        
        # Sheet 3: Nur Matching-Scores
        df_matching.to_excel(writer, sheet_name='Scores', index=False)
    
    print(f"\n✓ Excel-Datei erstellt: {filepath}")
    print(f"  Sheets: Matching_Ergebnisse, Job_Details, Scores")
    print(f"  Anzahl Kandidaten: {len(df_export)}")
    
    return filepath

# --------------------------------------------------
# MAIN
# --------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("JOB → KANDIDATEN MATCHING")
    print("=" * 70)

    while True:
        job_id = input("Stellen-ID eingeben (oder 'exit'): ").strip()
        if job_id.lower() == "exit":
            break

        job = load_job(job_id)
        print("\nSTELLE:")
        print(f"{job['position']} | {job['department']} | {job['ort']} | "
              f"{job['gehalt_von']} – {job['gehalt_bis']} EUR\n")

        candidates = load_candidates()
        results = match_candidates(job, candidates)

        print(f"\nGefundene Kandidaten: {len(results)}\n")

        for i, r in enumerate(results[:10], 1):
            print(f"{i}. {r['name']} (ID {r['id']})")
            print(f"   Aktuelle Position: {r['position_now']}")
            print(f"   Gehaltswunsch: {r['gehaltswunsch']}")
            print(f"   Scores: Gehalt {r['gehalts_score']} | Fahrtweg {r['fahrtweg_score']} ({r['fahrtweg_km']} km)")
            print(f"   Gesamt-Score: {r['gesamt_score']} ({int(r['datenvollstaendigkeit']*2)}/2 Kriterien)")
            if r.get("skill_match") is not None:
                print(f"   Übereinstimmende Skills: {r.get('skills_gemeinsam') or '(keine)'}")
                print(f"   Fehlende Job-Skills: {r.get('skills_fehlend') or '(keine)'}")
            if r["fehlende_daten"]:
                print(f"   ⚠️ Fehlende Daten: {', '.join(r['fehlende_daten'])}")
            print()
        
        # Frage nach Excel-Export
        if results:
            export = input("\nMöchten Sie die Ergebnisse als Excel exportieren? (j/n): ").strip().lower()
            if export in ['j', 'ja', 'y', 'yes']:
                # Frage nach Anzahl der zu exportierenden Kandidaten
                print(f"\nInsgesamt {len(results)} Kandidaten gefunden.")
                anzahl_input = input(f"Wie viele Kandidaten exportieren? (Enter = alle {len(results)}): ").strip()
                
                if anzahl_input:
                    try:
                        anzahl = int(anzahl_input)
                        if anzahl < 1:
                            print("⚠ Ungültige Anzahl, exportiere alle Kandidaten")
                            anzahl = len(results)
                        elif anzahl > len(results):
                            print(f"⚠ Nur {len(results)} Kandidaten verfügbar, exportiere alle")
                            anzahl = len(results)
                        else:
                            print(f"✓ Exportiere Top {anzahl} Kandidaten")
                    except ValueError:
                        print("⚠ Ungültige Eingabe, exportiere alle Kandidaten")
                        anzahl = len(results)
                else:
                    anzahl = len(results)
                
                # Limitiere results auf gewünschte Anzahl
                results_to_export = results[:anzahl]
                
                # Lade vollständige Kandidatendaten
                conn = psycopg.connect(**DB_CONFIG)
                cur = conn.cursor()
                candidate_ids = [r['id'] for r in results_to_export]
                placeholders = ','.join(['%s'] * len(candidate_ids))
                cur.execute(f"""
                    SELECT *
                    FROM candidates
                    WHERE id IN ({placeholders});
                """, candidate_ids)
                candidates_full = cur.fetchall()
                cur.close()
                conn.close()
                
                excel_file = export_to_excel(job, candidates_full, results_to_export)
                if excel_file:
                    print(f"\n✓ Excel-Datei kann nun für E-Mail-Versand verwendet werden")
                    print(f"  Pfad: {excel_file}")