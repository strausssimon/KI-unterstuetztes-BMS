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
from difflib import SequenceMatcher
from src.db_config import DB_CONFIG

# --------------------------------------------------
# KONFIGURATION
# --------------------------------------------------

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

    # Sortiere nach Länge (längste zuerst), damit "hamburg" vor "burg" gefunden wird
    staedte_sortiert = sorted(STADTEN, key=len, reverse=True)
    states_sortiert = sorted(STATES, key=len, reverse=True)

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
        for field in ["position_now", "department", "wohnort", "wunscharbeitsort", "status"]:
            if k.get(field) and isinstance(k.get(field), str):
                k[field] = k[field].lower()
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
    if "ort" in intent and intent["ort"]:
        try:
            ziel_lat, ziel_lon, _ = get_coords_and_state(intent["ort"])
        except ValueError:
            print(f"Warnung: Ort '{intent['ort']}' nicht gefunden. Entfernung wird ignoriert.")

    ziel_position = intent.get("position")
    ziel_fach = intent.get("fachbereich")
    ziel_state = intent.get("state")

    passende = []

    for k in kandidaten_liste:
        # Status-Check (candidates hat 'status' Spalte)
        if k.get("status") and k["status"].lower() == "nicht auf der suche":
            continue
        
        # Fachbereich-Check (candidates hat 'department' statt 'fachbereich')
        if ziel_fach and k.get("department") != ziel_fach:
            continue
        
        # Position-Check (candidates hat 'position_now' statt 'position')
        if ziel_position:
            aktuelle_position = k.get("position_now", "")
            erlaubte = KARRIERE_PFADE.get(aktuelle_position, set())
            if ziel_position not in erlaubte:
                continue

        # Wohnort aus CSV
        wohnort = k.get("wohnort", "")
        if wohnort:
            try:
                wohn_lat, wohn_lon, wohn_state = get_coords_and_state(wohnort)
            except ValueError:
                wohn_lat = wohn_lon = wohn_state = None
        else:
            wohn_lat = wohn_lon = wohn_state = None

        # Wunscharbeitsort aus CSV
        wunsch = k.get("wunscharbeitsort", "")
        if wunsch:
            try:
                w_lat, w_lon, w_state = get_coords_and_state(wunsch)
            except ValueError:
                w_lat = w_lon = w_state = None
        else:
            w_lat = w_lon = w_state = None

        # Bundesland filtern
        if ziel_state:
            if wohn_state != ziel_state and w_state != ziel_state:
                continue

        # Entfernung prüfen (nutze 'regionale_verfuegbarkeit' statt 'fahrbereitschaft')
        if ziel_lat is not None and ziel_lon is not None:
            max_km = k.get("regionale_verfuegbarkeit") or 50
            dist_wohn = haversine(ziel_lat, ziel_lon, wohn_lat, wohn_lon) if wohn_lat else float("inf")
            dist_wunsch = haversine(ziel_lat, ziel_lon, w_lat, w_lon) if w_lat else float("inf")
            min_dist = min(dist_wohn, dist_wunsch)
            if min_dist > max_km:
                continue
        else:
            min_dist = None

        # Kompakte Ausgabe
        wohn_info = f"{wohnort} / {wohn_state}" if wohn_state else wohnort
        wunsch_info = f"{wunsch} / {w_state}" if w_state else wunsch

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
    return passende

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
    ergebnis = match_candidates(intent, kandidaten)

    print("\n" + "=" * 80)
    print(f"Geeignete Kandidaten ({len(ergebnis)} gefunden)")
    print("=" * 80 + "\n")
    
    if not ergebnis:
        print("Keine passenden Kandidaten gefunden.")
    else:
        for idx, k in enumerate(ergebnis, 1):
            print(f"{idx}. {k['name']}")
            print(f"   ID: {k['kandidat_id']}")
            print(f"   Position: {k['position']}")
            print(f"   Fachbereich: {k['fachbereich']}")
            print(f"   Wohnort: {k['wohnort']}")
            print(f"   Wunscharbeitsort: {k['wunscharbeitsort']}")
            if k['entfernung_km'] is not None:
                print(f"   Entfernung: {k['entfernung_km']} km")
            print()