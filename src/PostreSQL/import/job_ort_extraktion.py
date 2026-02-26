""" 
====================================================
Programmname : Ortsextraktion für Jobs
Beschreibung : Extrahiert Ortsinformationen aus job_description und long_note
und schreibt sie in stadt1, stadt2, ... und bundesland.

====================================================
"""

import sys
import os
# Füge Projekt-Root zum Python-Pfad hinzu
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

import pandas as pd
import psycopg
import re
from src.db_config import DB_CONFIG

# Stopwords aus nltk laden
try:
    from nltk.corpus import stopwords
    import nltk
    # Versuche deutsche Stopwords zu laden
    try:
        STOPWORDS = set(stopwords.words('german'))
    except LookupError:
        # Falls nicht vorhanden, lade sie herunter
        print("Lade deutsche Stopwords...")
        nltk.download('stopwords', quiet=True)
        STOPWORDS = set(stopwords.words('german'))
    
    # Erweitere um domänenspezifische Wörter
    DOMAIN_STOPWORDS = {
        "arbeit", "stelle", "position", "job", "team", "aufgabe", "projekt",
        "bereich", "abteilung", "unternehmen", "firma", "praxis", "klinik",
        "krankenhaus", "station", "zentrum", "institut", "organisation",
        "person", "mitarbeiter", "patient", "kunde", "kollege", "leiter",
        "chef", "arzt", "facharzt", "oberarzt", "chefarzt", "assistenzarzt",
        "zeit", "jahr", "monat", "woche", "tag", "stunde", "termin",
        "gehalt", "lohn", "euro", "vergütung", "bezahlung",
        "erfahrung", "qualifikation", "ausbildung", "studium", "abschluss",
        "betreuung", "versorgung", "behandlung", "diagnostik", "therapie",
        "fach", "fachbereich", "fachgebiet", "gebiet",
        "interesse", "freude", "spaß", "motivation", "engagement",
        "wunsch", "ziel", "chance", "möglichkeit", "option", "angebot",
        # Manuell hinzugefügte Stopwörter
        "betten", "klinken", "weil", "sinn", "müssen", "sollten", "können"
    
    }
    STOPWORDS.update(DOMAIN_STOPWORDS)
    
except ImportError:
    print("⚠ nltk nicht installiert - verwende minimale Stopword-Liste")
    # Minimale Fallback-Liste
    STOPWORDS = {
        "kommen", "ohne", "mit", "bei", "nach", "vor", "zu", "von", "aus",
        "der", "die", "das", "den", "dem", "des", "ein", "eine", "und", "oder",
        "arbeit", "stelle", "position", "job", "team", "arzt", "klinik",
        "betten", "klinken", "weil", "sinn", "müssen"
    }

# Konfiguration

STAEDTE_CSV = r"data\Staedte_Deutschland.csv"

# Länder-Mappings (DACH)
LAENDER_MAPPING = {
    "deutschland": "DE",
    "de": "DE",
    "germany": "DE",
    "schweiz": "CH",
    "ch": "CH",
    "switzerland": "CH",
    "österreich": "AT",
    "oesterreich": "AT",
    "at": "AT",
    "austria": "AT"
}

# Bundesländer-Abkürzungen
BUNDESLAENDER_MAPPING = {
    "bw": "baden-württemberg",
    "baden-wuerttemberg": "baden-württemberg",
    "by": "bayern",
    "bayern": "bayern",
    "be": "berlin",
    "bb": "brandenburg",
    "hb": "bremen",
    "hh": "hamburg",
    "he": "hessen",
    "mv": "mecklenburg-vorpommern",
    "mecklenburg-vorpomm": "mecklenburg-vorpommern",
    "ni": "niedersachsen",
    "nrw": "nordrhein-westfalen",
    "nordrhein-westf": "nordrhein-westfalen",
    "rp": "rheinland-pfalz",
    "sl": "saarland",
    "sn": "sachsen",
    "st": "sachsen-anhalt",
    "sh": "schleswig-holstein",
    "th": "thüringen",
    "thueringen": "thüringen"
}

# STOPWORDS werden oben beim Import geladen (nltk oder Fallback)


def load_staedte():
    """
    Lädt Städte und Bundesländer aus der CSV.
    """
    try:
        # CSV verwendet Komma-Separator und hat "place" und "state" Spalten
        df = pd.read_csv(STAEDTE_CSV)
        
        # Normalisiere Städtenamen (lowercase + strip)
        df["place"] = df["place"].str.lower().str.strip()
        df["state"] = df["state"].fillna("").str.lower().str.strip()
        
        # Erstelle Sets mit eindeutigen Namen
        staedte = set(df["place"].dropna())
        bundeslaender = set(filter(None, df["state"]))
        
        # Kombiniere beide
        alle_orte = staedte | bundeslaender
        
        print(f"✓ {len(staedte)} Städte und {len(bundeslaender)} Bundesländer aus CSV geladen")
        
        # Debug: Zeige Beispiele
        beispiel_staedte = sorted(list(staedte))[:3]
        beispiel_laender = sorted(list(bundeslaender))[:3]
        print(f"   Beispiel Städte: {beispiel_staedte}")
        print(f"   Beispiel Bundesländer: {beispiel_laender}")
        
        return alle_orte
        
    except Exception as e:
        print(f"✗ Fehler beim Laden der Städte-CSV: {e}")
        return set()


def extract_ort(text, orte, debug=False):
    """
    Extrahiert Orte aus Text (job_description oder long_note).
    
    Args:
        text: Text aus der job_description oder long_note Spalte
        orte: Set mit deutschen Städten und Bundesländern
        debug: Wenn True, gibt Debug-Informationen aus
    
    Returns:
        String mit extrahierten Orten (kommasepariert)
    """
    if not text or pd.isna(text):
        return None
    
    text = str(text).strip()
    
    if debug:
        print(f"\n   Debug: text = '{text[:100]}...'")
    
    # Normalisiere Text für Suche
    text_lower = text.lower()
    
    gefundene_orte = []
    
    # Schritt 1: Länder-Kürzel (DACH) finden und sammeln
    for suchwort, kuerzel in LAENDER_MAPPING.items():
        pattern = r'\b' + re.escape(suchwort) + r'\b'
        if re.search(pattern, text_lower):
            gefundene_orte.append(kuerzel)
            if debug:
                print(f"   → Gefunden: {suchwort} → {kuerzel}")
            # Entferne das gefundene Land aus dem Text, damit es nicht doppelt gefunden wird
            text_lower = re.sub(pattern, '', text_lower)
    
    # Schritt 2: Bundesländer-Abkürzungen ersetzen
    text_ersetzt = text_lower
    for abk, vollname in BUNDESLAENDER_MAPPING.items():
        pattern = r'\b' + re.escape(abk) + r'\b'
        if re.search(pattern, text_ersetzt):
            text_ersetzt = re.sub(pattern, vollname, text_ersetzt)
            if debug:
                print(f"   → Ersetze: {abk} → {vollname}")
    
    # Schritt 3: Städte und Bundesländer finden
    # WICHTIG: Sortiere nach Länge (längste zuerst), damit "schleswig-holstein" vor "schleswig" gefunden wird
    orte_sortiert = sorted(orte, key=len, reverse=True)
    
    if debug:
        print(f"   Suche in: '{text_ersetzt[:100]}...'")
        print(f"   Anzahl Orte zu prüfen: {len(orte)}")
    
    for ort in orte_sortiert:
        # Überspringe Stopwords
        if ort.lower() in STOPWORDS:
            continue
            
        # Suche nach ganzen Wörtern (Word Boundaries)
        # Erlaube auch Bindestrich innerhalb des Wortes (z.B. schleswig-holstein)
        pattern = r'\b' + re.escape(ort.lower()) + r'\b'
        if re.search(pattern, text_ersetzt):
            gefundene_orte.append(ort)
            if debug:
                print(f"   ✓ Match: '{ort}'")
    
    if debug and not gefundene_orte:
        print(f"   ✗ Keine Orte gefunden")
    
    if gefundene_orte:
        # Sortiere alphabetisch und entferne Duplikate
        unique_orte = sorted(set(gefundene_orte))
        # Nehme nur die ersten 3 Orte, um Überfrachtung zu vermeiden
        return ", ".join(unique_orte[:3])
    
    return None


def update_job_ort():
    """
    Aktualisiert die ort-Spalte in der jobs-Tabelle basierend auf job_description und long_note.
    """
    print("=" * 80)
    print("Ort aus job_description und long_note extrahieren (jobs-Tabelle)")
    print("=" * 80)
    
    # 1. Städte und Bundesländer laden
    print("\n1. Lade Städte und Bundesländer...")
    orte = load_staedte()
    
    if not orte:
        print("✗ Keine Orte geladen - Abbruch")
        return
    
    # 2. Jobs laden
    print("\n2. Lade Jobs aus Datenbank...")
    
    try:
        conn = psycopg.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Hole alle Jobs mit job_description oder long_note OHNE bestehenden ort
        cur.execute("""
            SELECT id, job_description, long_note, ort 
            FROM jobs
            WHERE (job_description IS NOT NULL AND job_description != '' 
                   OR long_note IS NOT NULL AND long_note != '')
            AND (ort IS NULL OR ort = '')
            ORDER BY id;
        """)
        
        jobs = cur.fetchall()
        print(f"✓ {len(jobs)} Jobs mit job_description/long_note gefunden")
        
        if not jobs:
            print("ℹ Keine Jobs zum Aktualisieren")
            cur.close()
            conn.close()
            return
        
        # 3. Analyse und Vorschau
        print("\n3. Analysiere job_description und long_note...")
        print("\n" + "=" * 80)
        print("VORSCHAU (erste 10 Einträge)")
        print("=" * 80 + "\n")
        
        updates = []
        
        for idx, (job_id, job_description, long_note, aktueller_ort) in enumerate(jobs):
            # Suche in beiden Spalten
            orte_aus_description = extract_ort(job_description, orte) if job_description else None
            orte_aus_note = extract_ort(long_note, orte) if long_note else None
            
            # Kombiniere Ergebnisse (Priorität: job_description > long_note)
            gefundene_orte = []
            if orte_aus_description:
                gefundene_orte.extend(orte_aus_description.split(", "))
            if orte_aus_note:
                gefundene_orte.extend(orte_aus_note.split(", "))
            
            # Entferne Duplikate und sortiere, maximal 3 Orte
            if gefundene_orte:
                unique_orte = sorted(set(gefundene_orte))[:3]
                neuer_ort = ", ".join(unique_orte)
            else:
                neuer_ort = None
            
            # Nur aktualisieren wenn neuer Wert gefunden wurde
            if neuer_ort:
                updates.append({
                    'id': job_id,
                    'job_description': job_description,
                    'long_note': long_note,
                    'alt': aktueller_ort,
                    'neu': neuer_ort
                })
                
                # Zeige erste 10
                if len(updates) <= 10:
                    print(f"Job ID {job_id}:")
                    if job_description:
                        print(f"  job_description: {job_description[:80]}{'...' if len(job_description) > 80 else ''}")
                    if long_note:
                        print(f"  long_note: {long_note[:80]}{'...' if len(long_note) > 80 else ''}")
                    print(f"  ort (alt): {aktueller_ort or '(leer)'}")
                    print(f"  ort (neu): {neuer_ort}")
                    print()
        
        if len(updates) > 10:
            print(f"... und {len(updates) - 10} weitere")
        
        print("\n" + "=" * 80)
        print(f"ZUSAMMENFASSUNG: {len(updates)} Jobs würden aktualisiert")
        print("=" * 80)
        
        if not updates:
            print("\nℹ Keine Änderungen erforderlich")
            cur.close()
            conn.close()
            return
        
        # 4. Bestätigung
        antwort = input("\nMöchten Sie die Änderungen durchführen? (j/n): ").strip().lower()
        
        if antwort not in ['j', 'ja', 'y', 'yes']:
            print("✗ Abgebrochen")
            cur.close()
            conn.close()
            return
        
        # 5. Updates durchführen
        print("\n4. Führe Updates durch...")
        
        erfolg = 0
        fehler = 0
        
        for update in updates:
            try:
                cur.execute("""
                    UPDATE jobs 
                    SET ort = %s 
                    WHERE id = %s;
                """, (update['neu'], update['id']))
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
        
    except psycopg.Error as e:
        print(f"\n✗ Datenbankfehler: {e}")
    except Exception as e:
        print(f"\n✗ Fehler: {e}")
        raise


if __name__ == "__main__":
    import sys
    
    # Test-Modus für einzelne Job-ID
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        if len(sys.argv) < 3:
            print("Usage: python job_ort_extraktion.py --test <JOB_ID>")
            sys.exit(1)
        
        test_id = sys.argv[2]
        
        print("=" * 80)
        print(f"TEST-MODUS für Job ID {test_id}")
        print("=" * 80)
        
        # Städte und Bundesländer laden
        print("\nLade Städte und Bundesländer...")
        orte = load_staedte()
        
        # Job laden
        print(f"\nLade Job ID {test_id}...")
        try:
            conn = psycopg.connect(**DB_CONFIG)
            cur = conn.cursor()
            
            cur.execute("""
                SELECT id, job_description, long_note, ort 
                FROM jobs
                WHERE id = %s;
            """, (test_id,))
            
            result = cur.fetchone()
            
            if not result:
                print(f"✗ Job ID {test_id} nicht gefunden")
                cur.close()
                conn.close()
                sys.exit(1)
            
            job_id, job_description, long_note, ort = result
            
            print(f"\nJob ID: {job_id}")
            print(f"job_description: '{job_description[:200] if job_description else '(leer)'}'...")
            print(f"long_note: '{long_note[:200] if long_note else '(leer)'}'...")
            print(f"ort (aktuell): '{ort}'")
            
            print("\n" + "-" * 80)
            print("ANALYSE job_description:")
            orte_aus_description = extract_ort(job_description, orte, debug=True) if job_description else None
            print("-" * 80)
            
            print("\n" + "-" * 80)
            print("ANALYSE long_note:")
            orte_aus_note = extract_ort(long_note, orte, debug=True) if long_note else None
            print("-" * 80)
            
            # Kombiniere Ergebnisse
            gefundene_orte = []
            if orte_aus_description:
                gefundene_orte.extend(orte_aus_description.split(", "))
            if orte_aus_note:
                gefundene_orte.extend(orte_aus_note.split(", "))
            
            if gefundene_orte:
                unique_orte = sorted(set(gefundene_orte))[:3]
                neuer_ort = ", ".join(unique_orte)
            else:
                neuer_ort = None
            
            print(f"\nERGEBNIS kombiniert: {neuer_ort or '(nichts gefunden)'}")
            
            cur.close()
            conn.close()
            
        except Exception as e:
            print(f"✗ Fehler: {e}")
            raise
    else:
        update_job_ort()
