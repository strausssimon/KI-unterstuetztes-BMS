import psycopg
import pandas as pd
import math
import re

# --------------------------------------------------
# KONFIGURATION
# --------------------------------------------------
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "postgres",
    "user": "postgres",
    "password": "Start123"
}

CSV_PATH = r"C:\Users\Angler1000\Desktop\Masterstudium\4. Semester\Big-Data-Consultingprojekt\Entfernungsbestimmung\Städte_Deutschland.csv"

WEIGHT_SALARY = 0.7
WEIGHT_DRIVE = 0.3
MAX_SCORE_COMPONENTS = 2

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
        SELECT id, position, fachbereich, ort, gehalt_von, gehalt_bis
        FROM jobs WHERE id = %s
    """, (job_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    job = dict(zip(
        ["id", "position", "fachbereich", "ort", "gehalt_von", "gehalt_bis"], row
    ))

    job["position"] = normalize(job["position"])
    job["fachbereich"] = normalize(job["fachbereich"])
    job["ort"] = extract_city(job["ort"])
    return job

def load_candidates():
    conn = psycopg.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, first_name, last_name, status, position_now, department,
               gehalt, wohnort, wunscharbeitsort, regionale_verfuegbarkeit
        FROM candidates_test
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
            k["gehalt"] = int(str(k.get("gehalt")).replace(".", "").replace(",", ""))
        except:
            k["gehalt"] = None

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

# --------------------------------------------------
# MATCHING
# --------------------------------------------------
def match_candidates(job, candidates):
    matches = []

    for c in candidates:
        if not career_match(c.get("position_now"), job["position"]):
            continue

        fachbereiche = [f.strip() for f in (c.get("department") or "").split(",")]
        if job["fachbereich"] not in fachbereiche:
            continue

        sal = salary_score(c.get("gehalt"), job["gehalt_von"], job["gehalt_bis"])
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

        avg = round(summe / gewicht, 2) if gewicht else None
        voll = comps / MAX_SCORE_COMPONENTS

        fehlend = []
        if sal is None: fehlend.append("Gehalt")
        if drv is None: fehlend.append("Fahrtweg")

        matches.append({
            "id": c["id"],
            "name": f"{c.get('first_name')} {c.get('last_name')}",
            "position_now": c.get("position_now"),
            "gehalt": c.get("gehalt"),
            "gehalts_score": sal,
            "fahrtweg_score": drv,
            "fahrtweg_km": dist,
            "gesamt_score": avg,
            "datenvollstaendigkeit": voll,
            "fehlende_daten": fehlend
        })

    matches.sort(
        key=lambda x: (x["gesamt_score"] is None, -(x["gesamt_score"] or 0))
    )
    return matches

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
        print(f"{job['position']} | {job['fachbereich']} | {job['ort']} | "
              f"{job['gehalt_von']} – {job['gehalt_bis']} EUR\n")

        candidates = load_candidates()
        results = match_candidates(job, candidates)

        print(f"\nGefundene Kandidaten: {len(results)}\n")

        for i, r in enumerate(results[:10], 1):
            print(f"{i}. {r['name']} (ID {r['id']})")
            print(f"   Aktuelle Position: {r['position_now']}")
            print(f"   Gehalt: {r['gehalt']}")
            print(f"   Scores: Gehalt {r['gehalts_score']} | Fahrtweg {r['fahrtweg_score']} ({r['fahrtweg_km']} km)")
            print(f"   Gesamt-Score: {r['gesamt_score']} ({int(r['datenvollstaendigkeit']*2)}/2 Kriterien)")
            if r["fehlende_daten"]:
                print(f"   ⚠️ Fehlende Daten: {', '.join(r['fehlende_daten'])}")
            print()