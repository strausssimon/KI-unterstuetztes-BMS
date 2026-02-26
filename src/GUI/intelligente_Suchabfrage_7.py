""" 
====================================================
Programmname : KI-unterstütztes BMS – Intelligente Suchabfrage
Beschreibung : Interpretiert Suchanfragen (via Ollama) und
               matcht passende Kandidaten aus der Datenbank; inkl. Export.

====================================================
"""
import sys
import os
# Füge Projekt-Root zum Python-Pfad hinzu
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

import psycopg
import requests
import json
import pandas as pd
import math
import re
from datetime import datetime
from difflib import SequenceMatcher
from src.db_config import DB_CONFIG

# --------------------------------------------------
# KONFIGURATION
# --------------------------------------------------

RESULTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "results"
)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "phi3:mini"

# Pfad zur Städte-CSV - bitte anpassen falls vorhanden
CSV_PATH = r"data\Staedte_Deutschland.csv"

MATCH_THRESHOLD = 0.8  # für Position und Fachbereich

# --------------------------------------------------
# POSITIONEN UND FACHBEREICHE
# --------------------------------------------------
POSITIONEN = [
    "assistenzarzt",
    "facharzt",
    "oberarzt",
    "leitender oberarzt",
    "chefarzt",
    "standortleiter",
    "gesellschafter"
]

FACHAUSWAHL = [
    "anästhesie",
    "chirurgie",
    "gynäkologie",
    "innere medizin",
    "kinderradiologie",
    "mammographie",
    "neuroradiologie",
    "nuklearmedizin",
    "orthopädie & uch",
    "pädiatrie/kindermedizin",
    "psychiatrie",
    "radiologie",
    "strahlentherapie"
]

# --------------------------------------------------
# KARRIEREPFADE
# --------------------------------------------------
KARRIERE_PFADE = {
    "assistenzarzt": {"assistenzarzt", "facharzt"},
    "facharzt": {"facharzt", "oberarzt", "leitender oberarzt", "chefarzt", "standortleiter"},
    "oberarzt": {"oberarzt", "leitender oberarzt", "chefarzt", "standortleiter"},
    "leitender oberarzt": {"leitender oberarzt", "chefarzt", "standortleiter", "gesellschafter"},
    "chefarzt": {"chefarzt", "standortleiter", "gesellschafter"},
    "standortleiter": {"standortleiter", "gesellschafter"},
    "gesellschafter": {"gesellschafter"}
}

# --------------------------------------------------
# LÄNDER (Name -> Abkürzungen)
# --------------------------------------------------
LAENDER = {
    "deutschland": ["deutschland", "de", "ger", "germany"],
    "schweiz": ["schweiz", "ch", "switzerland"],
    "österreich": ["österreich", "oesterreich", "at", "austria"],
    "frankreich": ["frankreich", "fr", "france"],
    "belgien": ["belgien", "be", "belgium"],
    "niederlande": ["niederlande", "nl", "netherlands", "holland"],
    "luxemburg": ["luxemburg", "lu", "luxembourg"],
    "dänemark": ["dänemark", "daenemark", "dk", "denmark"],
    "polen": ["polen", "pl", "poland"],
    "tschechien": ["tschechien", "cz", "czech", "tschechische republik"]
}

# Erstelle Reverse-Mapping für schnelle Suche
LAND_LOOKUP = {}
for land, varianten in LAENDER.items():
    for variante in varianten:
        LAND_LOOKUP[variante.lower()] = land

# --------------------------------------------------
# HILFSFUNKTIONEN
# --------------------------------------------------
def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

def tokenize(text):
    return re.findall(r"\b\w+\b", text.lower())

def best_fuzzy_match(terms, candidates):
    best_candidate = None
    best_score = 0.0

    for candidate in candidates:
        candidate_terms = tokenize(candidate)
        scores = []
        for t in terms:
            for ct in candidate_terms:
                scores.append(similarity(t, ct))
        if scores:
            score = max(scores)
            if score > best_score:
                best_score = score
                best_candidate = candidate
    return best_candidate, best_score


def slugify(value):
    value = value.lower().strip()
    replacements = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
    for src, tgt in replacements.items():
        value = value.replace(src, tgt)
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value

# --------------------------------------------------
# STÄDTE + STATES LADEN
# --------------------------------------------------
df_cities = pd.read_csv(CSV_PATH)
df_cities["place"] = df_cities["place"].str.lower().str.strip()
df_cities["state"] = df_cities["state"].fillna("").str.lower().str.strip()

STADTEN = set(df_cities["place"])
STATES = set(filter(None, df_cities["state"]))

# --------------------------------------------------
# HAVERSINE
# --------------------------------------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def get_coords_and_state(city):
    city = city.lower().strip()
    row = df_cities[df_cities["place"] == city]
    if row.empty:
        raise ValueError(f"Stadt nicht gefunden: {city}")
    return row.iloc[0]["latitude"], row.iloc[0]["longitude"], row.iloc[0]["state"]

# --------------------------------------------------
# INTENT EXTRAKTION
# --------------------------------------------------
def extract_intent(question):
    terms = tokenize(question)
    pos_match, pos_score = best_fuzzy_match(terms, POSITIONEN)
    fach_match, fach_score = best_fuzzy_match(terms, FACHAUSWAHL)

    question_lower = question.lower()
    ort_match = None
    state_match = None
    land_match = None

    # Sortiere nach Länge (längste zuerst), damit "hamburg" vor "burg" gefunden wird
    staedte_sortiert = sorted(STADTEN, key=len, reverse=True)
    states_sortiert = sorted(STATES, key=len, reverse=True)

    # Suche nach Ländern (prüfe alle Varianten)
    for variante, land in LAND_LOOKUP.items():
        pattern = r'\b' + re.escape(variante) + r'\b'
        if re.search(pattern, question_lower):
            land_match = land
            break

    # Suche mit Word Boundaries (ganze Wörter)
    for stadt in staedte_sortiert:
        pattern = r'\b' + re.escape(stadt) + r'\b'
        if re.search(pattern, question_lower):
            ort_match = stadt
            break

    for st in states_sortiert:
        pattern = r'\b' + re.escape(st) + r'\b'
        if re.search(pattern, question_lower):
            state_match = st
            break

    intent = {}
    print("\nErmittelte Suchkriterien:")

    # Position
    if pos_score >= MATCH_THRESHOLD:
        intent["position"] = pos_match
        print(f"Position: {pos_match} ({pos_score:.2f})")
    else:
        print("Position: nicht angegeben")

    # Fachbereich
    if fach_score >= MATCH_THRESHOLD:
        intent["fachbereich"] = fach_match
        print(f"Fachbereich: {fach_match} ({fach_score:.2f})")
    else:
        print("Fachbereich: nicht angegeben")

    # Stadt/State
    if ort_match or state_match:
        intent["ort"] = ort_match
        intent["state"] = state_match
        st = ort_match if ort_match else "nicht angegeben"
        stt = state_match if state_match else "nicht angegeben"
        print(f"Stadt: {st}")
        print(f"Bundesland: {stt}")
    else:
        print("Stadt: nicht angegeben")
        print("Bundesland: nicht angegeben")

    # Land
    if land_match:
        intent["land"] = land_match
        print(f"Land: {land_match}")
    else:
        print("Land: nicht angegeben")

    return intent

# --------------------------------------------------
# KANDIDATEN LADEN
# --------------------------------------------------
def load_candidates():
    """
    Lädt Kandidaten aus der candidates-Tabelle.
    Passt Spaltennamen an (mit Unterstrichen statt Leerzeichen).
    Behandelt fehlerhafte Timestamps durch Text-Konvertierung.
    """
    conn = psycopg.connect(**DB_CONFIG)
    
    # Verwende text_format für Timestamps um Fehler zu vermeiden
    # Alle Timestamps werden als Text geladen
    conn.execute("""
        SET datestyle = 'ISO, YMD';
    """)
    
    cur = conn.cursor()
    
    # Hole zuerst die Spaltennamen
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'candidates'
        ORDER BY ordinal_position;
    """)
    
    columns_info = cur.fetchall()
    if not columns_info:
        print("Fehler: Tabelle 'candidates' existiert nicht.")
        print("Bitte zuerst das Setup-Skript 'new_table_candidates.py' unter 'src/PostreSQL/Aufbau' ausführen.")
        cur.close()
        conn.close()
        return []

    timestamp_columns = [col for col, dtype in columns_info if 'timestamp' in dtype.lower() or 'date' in dtype.lower()]
    
    # Baue SELECT mit CAST für Timestamp-Spalten
    select_parts = []
    for col, dtype in columns_info:
        if col in timestamp_columns:
            # Konvertiere Timestamps zu Text, setze fehlerhafte auf NULL
            select_parts.append(f"""
                CASE 
                    WHEN {col} IS NOT NULL 
                         AND EXTRACT(YEAR FROM {col}) BETWEEN 1900 AND 9999 
                    THEN {col}::text 
                    ELSE NULL 
                END as {col}
            """)
        else:
            select_parts.append(col)
    
    select_clause = ', '.join(select_parts)
    
    try:
        cur.execute(f"SELECT {select_clause} FROM candidates")
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
    except Exception as e:
        print(f"Fehler beim Laden der Kandidaten: {e}")
        print("Versuche Fallback ohne Timestamp-Konvertierung...")
        try:
            # Fallback: Lade alle Spalten außer problematischen Timestamps
            cur.execute(f"""
                SELECT * FROM candidates 
                WHERE EXTRACT(YEAR FROM COALESCE(letzter_kontakt, CURRENT_TIMESTAMP)) < 10000
            """)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
        except:
            cur.close()
            conn.close()
            return []

    cur.close()
    conn.close()

    kandidaten_liste = []
    for r in rows:
        k = dict(zip(cols, r))
        # Konvertiere zu Kleinbuchstaben für Vergleiche
        for field in ["position_now", "department", "wohnort", "wunscharbeitsort"]:
            if k.get(field) and isinstance(k.get(field), str):
                k[field] = k[field].lower()

        # Regionale Verfügbarkeit wie in Matching.py interpretieren
        rv_raw = k.get("regionale_verfuegbarkeit")
        rv = str(rv_raw).lower().strip() if rv_raw is not None else ""
        if "deutschland" in rv:
            # deutschlandweit verfügbar -> sehr großer Radius
            k["regionale_verfuegbarkeit"] = 1000
        else:
            nums = re.findall(r"\d+", rv)
            k["regionale_verfuegbarkeit"] = int(nums[0]) if nums else 50

        kandidaten_liste.append(k)
    
    print(f"✓ {len(kandidaten_liste)} Kandidaten geladen")
    return kandidaten_liste

# --------------------------------------------------
# MATCHING
# --------------------------------------------------
def match_candidates(intent, kandidaten_liste):
    """
    Matched Kandidaten basierend auf Intent.
    Verwendet candidates-Tabellen-Spaltennamen.
    """
    ziel_lat, ziel_lon = None, None

    # Basis-Filter aus Intent
    ziel_position = intent.get("position")
    ziel_fach = intent.get("fachbereich")
    ziel_state = intent.get("state")
    ziel_land = intent.get("land")

    # Wenn eine Stadt im Intent steht, nutze deren Bundesland als Standard-
    # Gebiet ("größtes Gebiet" = Bundesland der Zielstadt).
    if "ort" in intent and intent["ort"]:
        try:
            ziel_lat, ziel_lon, ziel_state_from_ort = get_coords_and_state(intent["ort"])
            if not ziel_state:
                ziel_state = ziel_state_from_ort
        except ValueError:
            print(f"Warnung: Ort '{intent['ort']}' nicht gefunden. Entfernung wird ignoriert.")

    passende = []
    passende_roh = []

    for k in kandidaten_liste:
        # Fachbereich-Check (candidates hat 'department' statt 'fachbereich')
        # Skills / Fachbereich sind NICHT mandatory: Wenn beim Kandidaten
        # kein Fachbereich hinterlegt ist, wird er nicht ausgeschlossen.
        if ziel_fach:
            department = k.get("department")
            if department and department != ziel_fach:
                continue

        # Position-Check (candidates hat 'position_now' statt 'position')
        # Auch die aktuelle Position ist optional: Nur wenn eine
        # Position beim Kandidaten hinterlegt ist, wird der Karrierpfad
        # zur Filterung verwendet.
        if ziel_position:
            aktuelle_position = k.get("position_now") or ""
            if aktuelle_position:
                erlaubte = KARRIERE_PFADE.get(aktuelle_position, set())
                if ziel_position not in erlaubte:
                    continue

        # Wohnort aus CSV (ggf. mit Komma, z.B. "mannheim, baden-württemberg")
        wohnort = k.get("wohnort", "")
        if wohnort:
            # Nur die Stadt vor dem ersten Komma für die Koordinaten verwenden
            wohnort_stadt = wohnort.split(",")[0].strip()
            try:
                wohn_lat, wohn_lon, wohn_state = get_coords_and_state(wohnort_stadt)
            except ValueError:
                wohn_lat = wohn_lon = wohn_state = None
        else:
            wohn_lat = wohn_lon = wohn_state = None

        # Wunscharbeitsort aus CSV (ggf. mit Komma, z.B. "köln, nordrhein-westfalen, ohne")
        wunsch = k.get("wunscharbeitsort", "")
        if wunsch:
            wunsch_stadt = wunsch.split(",")[0].strip()
            try:
                w_lat, w_lon, w_state = get_coords_and_state(wunsch_stadt)
            except ValueError:
                w_lat = w_lon = w_state = None
        else:
            w_lat = w_lon = w_state = None

        # Entfernung zuerst prüfen: alle Kandidaten mit Entfernung <= 50 km
        # (zwischen Such-Ort und Wohn- bzw. Wunscharbeitsort) werden angezeigt.
        min_dist = None
        if ziel_lat is not None and ziel_lon is not None:
            dist_wohn = haversine(ziel_lat, ziel_lon, wohn_lat, wohn_lon) if wohn_lat else float("inf")
            dist_wunsch = haversine(ziel_lat, ziel_lon, w_lat, w_lon) if w_lat else float("inf")

            min_dist = min(dist_wohn, dist_wunsch)
            if min_dist == float("inf"):
                min_dist = None

            if min_dist is not None and min_dist <= 50:
                # passt über Entfernung -> Kandidat bleibt erhalten
                pass
            else:
                # keine oder zu große Entfernung -> Fallback auf Bundesland/Land
                # 1) Wenn Bundesland bekannt: Kandidaten mit Wohn- oder Wunscharbeitsort
                #    im selben Bundesland behalten.
                same_state = False
                if ziel_state:
                    if wohn_state and wohn_state == ziel_state:
                        same_state = True
                    if w_state and w_state == ziel_state:
                        same_state = True

                # 2) Wenn (noch) kein Treffer über Bundesland und ein Land
                #    im Intent existiert, zusätzlich Kandidaten berücksichtigen,
                #    deren Wunscharbeitsort im selben Land liegt (z.B. "de").
                tokens_wunsch = tokenize(wunsch) if wunsch else []

                same_country = False
                if not same_state and ziel_land and tokens_wunsch:
                    for tok in tokens_wunsch:
                        land = LAND_LOOKUP.get(tok)
                        if land == ziel_land:
                            same_country = True
                            break

                # 3) Spezieller Fall: Wunscharbeitsort ist deutschlandweit
                #    (z.B. nur "de" oder "deutschland"). Diese Kandidaten
                #    sollen immer berücksichtigt werden, auch wenn im Intent
                #    kein Land explizit genannt wurde.
                deutschlandweit = False
                if tokens_wunsch:
                    for tok in tokens_wunsch:
                        land = LAND_LOOKUP.get(tok)
                        if land == "deutschland":
                            deutschlandweit = True
                            break

                if not same_state and not same_country and not deutschlandweit:
                    # weder Entfernung <= 50 km, noch gleiches Bundesland,
                    # noch explizit gleiches Land, noch deutschlandweit -> Kandidat überspringen
                    continue

        # Kompakte Ausgabe
        wohn_info = f"{wohnort} / {wohn_state}" if wohn_state else wohnort
        wunsch_info = f"{wunsch} / {w_state}" if w_state else wunsch

        passende_roh.append(k)
        passende.append({
            "kandidat_id": k["id"],
            "name": f"{k.get('first_name', '')} {k.get('last_name', '')}".strip(),
            "position": k.get("position_now", "N/A"),
            "fachbereich": k.get("department", "N/A"),
            "wohnort": wohn_info,
            "wunscharbeitsort": wunsch_info,
            "entfernung_km": round(min_dist, 2) if min_dist is not None else None
        })

    passende.sort(key=lambda x: x["entfernung_km"] if x["entfernung_km"] is not None else float('inf'))
    return passende, passende_roh


def export_to_excel(intent, kandidaten_roh):
    if not kandidaten_roh:
        print("\nKein Excel-Export, da keine passenden Kandidaten gefunden wurden.")
        return

    os.makedirs(RESULTS_DIR, exist_ok=True)

    teile = ["export"]
    for schluessel in ["position", "fachbereich", "ort", "state", "land"]:
        wert = intent.get(schluessel)
        if wert:
            teile.append(slugify(str(wert)))

    datum_str = datetime.now().strftime("%Y%m%d")
    teile.append(datum_str)

    dateiname = "_".join(teile) + ".xlsx"
    pfad = os.path.join(RESULTS_DIR, dateiname)

    try:
        df = pd.DataFrame(kandidaten_roh)
        df.to_excel(pfad, index=False)
        print(f"\nExcel-Export erstellt: {pfad}")
    except Exception as e:
        print(f"Fehler beim Excel-Export: {e}")

# --------------------------------------------------
# MAIN
# --------------------------------------------------
if __name__ == "__main__":
    print("=" * 80)
    print("Intelligente Kandidatensuche")
    print("=" * 80)
    print("\nBeispiel: 'Facharzt für Radiologie in München'")
    print("Beispiel: 'Oberarzt Chirurgie Berlin'\n")
    
    frage = input("Frage eingeben: ")

    intent = extract_intent(frage)
    kandidaten = load_candidates()
    ergebnis, ergebnis_roh = match_candidates(intent, kandidaten)

    print("\n" + "=" * 80)
    print(f"Geeignete Kandidaten ({len(ergebnis)} gefunden, Top 5 angezeigt)")
    print("=" * 80 + "\n")
    
    if not ergebnis:
        print("Keine passenden Kandidaten gefunden.")
    else:
        # Begrenze Ausgabe auf Top 5
        top_kandidaten = ergebnis[:5]
        for idx, k in enumerate(top_kandidaten, 1):
            print(f"{idx}. {k['name']}")
            print(f"   ID: {k['kandidat_id']}")
            print(f"   Position: {k['position']}")
            print(f"   Fachbereich: {k['fachbereich']}")
            print(f"   Wohnort: {k['wohnort']}")
            print(f"   Wunscharbeitsort: {k['wunscharbeitsort']}")
            if k['entfernung_km'] is not None:
                print(f"   Entfernung: {k['entfernung_km']} km")
            print()

    export_to_excel(intent, ergebnis_roh)
