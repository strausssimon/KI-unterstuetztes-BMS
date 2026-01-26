"""
Skript zum Füllen der Gehaltswunsch-Spalte in der candidates-Tabelle
Berücksichtigt Position, Fachauswahl und Land als Einflussfaktoren
"""

import sys
import os
# Füge Projekt-Root zum Python-Pfad hinzu
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

import psycopg
import random
from src.db_config import DB_CONFIG

# --------------------------------------------------
# KONFIGURATION
# --------------------------------------------------

# Positionen hierarchisch geordnet (niedrigste zu höchster)
POSITIONEN_HIERARCHIE = {
    "assistenzarzt": 1,
    "facharzt": 2,
    "oberarzt": 3,
    "leitender oberarzt": 4,
    "chefarzt": 5,
    "standortleiter": 6,
    "gesellschafter": 7
}

# Fachbereiche mit Gehaltsfaktoren (relativ)
# Höhere Faktoren = höhere Gehälter
FACHBEREICH_FAKTOREN = {
    "radiologie": 1.70,        # Erhöht: Radiologie zahlt deutlich mehr
    "nuklearmedizin": 1.65,    # Erhöht
    "neuroradiologie": 1.68,   # Erhöht
    "strahlentherapie": 1.60,  # Erhöht
    "kinderradiologie": 1.55,  # Erhöht
    "mammographie": 1.50,      # Erhöht
    "anästhesie": 1.30,        # Leicht erhöht
    "chirurgie": 1.25,         # Leicht erhöht
    "orthopädie & uch": 1.25,  # Leicht erhöht
    "innere medizin": 1.15,    # Leicht erhöht
    "gynäkologie": 1.15,       # Leicht erhöht
    "pädiatrie/kindermedizin": 1.10,
    "psychiatrie": 1.00
}

# Länder mit Gehaltsfaktoren (relativ zu Deutschland = 1.0)
LAND_FAKTOREN = {
    "schweiz": 1.50,          # Schweiz zahlt ca. 50% mehr
    "luxemburg": 1.35,        # Luxemburg zahlt ca. 35% mehr
    "deutschland": 1.00,      # Basis
    "österreich": 0.95,       # Österreich zahlt etwas weniger
    "niederlande": 1.05,      # Niederlande zahlt etwas mehr
    "belgien": 1.03,          # Belgien zahlt etwas mehr
    "frankreich": 0.98,       # Frankreich zahlt ähnlich
    "dänemark": 1.20,         # Dänemark zahlt deutlich mehr
    "polen": 0.40,            # Polen zahlt deutlich weniger
    "tschechien": 0.45        # Tschechien zahlt deutlich weniger
}

# Länder-Mapping (Varianten -> Hauptname)
LAENDER_MAPPING = {
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

# Basisgehälter pro Position in Deutschland (in EUR/Jahr)
BASISGEHAELTER = {
    "assistenzarzt": 60000,
    "facharzt": 100000,         # Erhöht von 85.000 auf 100.000
    "oberarzt": 140000,         # Erhöht von 120.000
    "leitender oberarzt": 170000,  # Erhöht von 150.000
    "chefarzt": 230000,         # Erhöht von 200.000
    "standortleiter": 200000,   # Erhöht von 180.000
    "gesellschafter": 280000    # Erhöht von 250.000
}

# Varianz für realistische Streuung (±15%)
VARIANZ_PROZENT = 0.15


def normalize_text(text):
    """Normalisiert Text für Vergleiche"""
    if not text:
        return ""
    return text.lower().strip()


def extract_land_from_text(text):
    """
    Extrahiert das Land aus einem Text (z.B. aus wohnort oder wunscharbeitsort)
    """
    if not text:
        return None
    
    text_lower = normalize_text(text)
    
    # Durchsuche alle Ländervarianten
    for land, varianten in LAENDER_MAPPING.items():
        for variante in varianten:
            if variante in text_lower:
                return land
    
    return None


def get_land_from_candidate(candidate_data):
    """
    Ermittelt das Land eines Kandidaten basierend auf Wunscharbeitsort
    Die Land-Information steht primär im Feld "wunscharbeitsort"
    """
    # Primär: wunscharbeitsort (hier steht die Land-Info)
    if candidate_data.get('wunscharbeitsort'):
        land = extract_land_from_text(candidate_data['wunscharbeitsort'])
        if land:
            return land
    
    # Fallback: wohnort und arbeitsort
    for field in ['wohnort', 'arbeitsort']:
        if candidate_data.get(field):
            land = extract_land_from_text(candidate_data[field])
            if land:
                return land
    
    # Default: Deutschland
    return "deutschland"


def get_position_level(position_text):
    """
    Ermittelt die Hierarchiestufe einer Position
    """
    if not position_text:
        return None
    
    position_lower = normalize_text(position_text)
    
    # Direkte Übereinstimmung
    for position, level in POSITIONEN_HIERARCHIE.items():
        if position in position_lower:
            return (position, level)
    
    return None


def get_fachbereich_from_text(text):
    """
    Extrahiert den Fachbereich aus einem Text
    """
    if not text:
        return None
    
    text_lower = normalize_text(text)
    
    # Suche nach exakten Übereinstimmungen
    for fach in FACHBEREICH_FAKTOREN.keys():
        if fach in text_lower:
            return fach
    
    return None


def calculate_salary(position, fachbereich, land):
    """
    Berechnet das Gehalt basierend auf Position, Fachbereich und Land
    """
    # Basis-Gehalt ermitteln
    if position not in BASISGEHAELTER:
        # Wenn Position unbekannt, verwende Facharzt als Default
        basis_gehalt = BASISGEHAELTER["facharzt"]
    else:
        basis_gehalt = BASISGEHAELTER[position]
    
    # Fachbereich-Faktor anwenden
    fach_faktor = FACHBEREICH_FAKTOREN.get(fachbereich, 1.05)  # Default 1.05
    
    # Land-Faktor anwenden
    land_faktor = LAND_FAKTOREN.get(land, 1.00)  # Default Deutschland
    
    # Berechne Gehalt
    gehalt = basis_gehalt * fach_faktor * land_faktor
    
    # Füge Varianz hinzu für realistische Streuung
    varianz = gehalt * VARIANZ_PROZENT
    gehalt_mit_varianz = gehalt + random.uniform(-varianz, varianz)
    
    # Füge zusätzliche kleine Zufallskomponente hinzu (±2000 EUR)
    zusatz_streuung = random.randint(-2000, 2000)
    gehalt_mit_varianz += zusatz_streuung
    
    # Runde auf 500 EUR für feinere Abstufung
    gehalt_gerundet = round(gehalt_mit_varianz / 500) * 500
    
    return int(gehalt_gerundet)


def fill_salary_for_candidates():
    """
    Hauptfunktion: Füllt die gehaltswunsch-Spalte für alle Kandidaten
    Überschreibt auch bestehende Werte, um falsch berechnete Gehälter zu korrigieren
    """
    print("\n=== Gehaltswunsch-Füllung für Candidates ===\n")
    
    # Verbindung zur Datenbank
    print("Verbinde mit PostgreSQL...")
    try:
        conn = psycopg.connect(**DB_CONFIG)
        print("✓ Verbindung erfolgreich\n")
    except Exception as e:
        print(f"✗ Fehler bei der Verbindung: {e}")
        return
    
    try:
        with conn.cursor() as cur:
            # Prüfe ob gehaltswunsch-Spalte existiert
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'candidates' AND column_name = 'gehaltswunsch';
            """)
            
            if not cur.fetchone():
                print("Erstelle gehaltswunsch-Spalte...")
                cur.execute("""
                    ALTER TABLE candidates 
                    ADD COLUMN gehaltswunsch INTEGER;
                """)
                conn.commit()
                print("✓ Spalte 'gehaltswunsch' erstellt\n")
            
            # Lade ALLE Kandidaten (auch mit vorhandenen Gehaltswerten)
            print("Lade Kandidaten aus der Datenbank...")
            cur.execute("""
                SELECT id, position_now, qualification, department, wunscharbeitsort, 
                       wohnort, arbeitsort, gehaltswunsch
                FROM candidates;
            """)
            
            candidates = cur.fetchall()
            total_candidates = len(candidates)
            print(f"✓ {total_candidates} Kandidaten geladen\n")
            print("⚠ ACHTUNG: Bestehende Gehaltswerte werden überschrieben!\n")
            
            # Statistiken
            updated_count = 0
            skipped_count = 0
            overwritten_count = 0  # Neue Statistik für überschriebene Werte
            stats = {
                "mit_position": 0,
                "ohne_position": 0,
                "mit_fachbereich": 0,
                "ohne_fachbereich": 0,
                "land_distribution": {}
            }
            
            print("Berechne und aktualisiere Gehaltswünsche...\n")
            
            for idx, candidate in enumerate(candidates, 1):
                candidate_id, position_now, qualification, department, wunsch_ort, wohn_ort, arbeit_ort, current_salary = candidate
                
                # Erstelle Kandidaten-Dict für Land-Extraktion
                candidate_data = {
                    'wunscharbeitsort': wunsch_ort,
                    'wohnort': wohn_ort,
                    'arbeitsort': arbeit_ort
                }
                
                # Extrahiere Position (erst position_now, dann qualification)
                position_info = get_position_level(position_now)
                if position_info:
                    position, level = position_info
                    stats["mit_position"] += 1
                else:
                    # Fallback: Prüfe qualification
                    position_info = get_position_level(qualification)
                    if position_info:
                        position, level = position_info
                        stats["mit_position"] += 1
                    else:
                        # Letzter Fallback auf Facharzt
                        position = "facharzt"
                        stats["ohne_position"] += 1
                
                # Extrahiere Fachbereich
                fachbereich = get_fachbereich_from_text(department)
                if fachbereich:
                    stats["mit_fachbereich"] += 1
                else:
                    # Fallback auf innere Medizin (mittlerer Bereich)
                    fachbereich = "innere medizin"
                    stats["ohne_fachbereich"] += 1
                
                # Extrahiere Land
                land = get_land_from_candidate(candidate_data)
                stats["land_distribution"][land] = stats["land_distribution"].get(land, 0) + 1
                
                # Berechne Gehalt (immer neu berechnen mit aktualisierten Faktoren)
                gehalt = calculate_salary(position, fachbereich, land)
                
                # Aktualisiere Datenbank
                cur.execute("""
                    UPDATE candidates 
                    SET gehaltswunsch = %s 
                    WHERE id = %s;
                """, (gehalt, candidate_id))
                
                # Zähle überschriebene vs. neue Werte
                if current_salary is not None:
                    overwritten_count += 1
                
                updated_count += 1
                
                # Fortschrittsanzeige alle 50 Kandidaten
                if idx % 50 == 0 or idx == total_candidates:
                    print(f"   Fortschritt: {idx}/{total_candidates} ({(idx/total_candidates)*100:.1f}%)")
            
            # Commit aller Änderungen
            conn.commit()
            
            print(f"\n✓ {updated_count} Kandidaten aktualisiert")
            print(f"✓ {overwritten_count} bestehende Werte überschrieben (neu berechnet)")
            print(f"✓ {updated_count - overwritten_count} neue Werte hinzugefügt")
            
            # Statistiken ausgeben
            print("\n=== Statistiken ===")
            print(f"Kandidaten mit erkannter Position: {stats['mit_position']}")
            print(f"Kandidaten ohne erkannte Position (Fallback: Facharzt): {stats['ohne_position']}")
            print(f"Kandidaten mit erkanntem Fachbereich: {stats['mit_fachbereich']}")
            print(f"Kandidaten ohne erkannten Fachbereich (Fallback: Innere Medizin): {stats['ohne_fachbereich']}")
            
            print("\nLänder-Verteilung:")
            for land, count in sorted(stats["land_distribution"].items(), key=lambda x: x[1], reverse=True):
                print(f"  {land.capitalize()}: {count}")
            
            # Beispiel-Abfrage: Zeige Gehaltsverteilung nach Position
            print("\n=== Gehaltsverteilung nach Position ===")
            cur.execute("""
                SELECT position_now, 
                       COUNT(*) as anzahl,
                       MIN(gehaltswunsch) as min_gehalt,
                       AVG(gehaltswunsch)::INTEGER as avg_gehalt,
                       MAX(gehaltswunsch) as max_gehalt
                FROM candidates
                WHERE gehaltswunsch IS NOT NULL 
                  AND position_now IS NOT NULL
                GROUP BY position_now
                ORDER BY avg_gehalt DESC;
            """)
            
            positions_stats = cur.fetchall()
            for pos_stat in positions_stats[:10]:  # Zeige Top 10
                pos, anzahl, min_g, avg_g, max_g = pos_stat
                print(f"{pos}: {anzahl} Kandidaten | Min: {min_g:,}€ | Ø: {avg_g:,}€ | Max: {max_g:,}€")
            
    except Exception as e:
        print(f"\n✗ Fehler beim Update: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    
    finally:
        conn.close()
        print("\n✓ Datenbankverbindung geschlossen")


def show_salary_examples():
    """
    Zeigt Beispiele für Gehaltsberechnungen
    """
    print("\n=== Beispiel-Gehaltsberechnungen ===\n")
    
    beispiele = [
        ("oberarzt", "radiologie", "deutschland"),
        ("facharzt", "radiologie", "deutschland"),
        ("oberarzt", "innere medizin", "deutschland"),
        ("facharzt", "innere medizin", "deutschland"),
        ("oberarzt", "radiologie", "schweiz"),
        ("chefarzt", "radiologie", "deutschland"),
        ("assistenzarzt", "psychiatrie", "deutschland"),
    ]
    
    for position, fach, land in beispiele:
        gehalt = calculate_salary(position, fach, land)
        print(f"{position.capitalize()} in {fach.capitalize()} ({land.capitalize()}): {gehalt:,}€")


if __name__ == "__main__":
    # Zeige erst Beispiele
    show_salary_examples()
    
    # Frage Benutzer
    print("\n" + "="*60)
    antwort = input("\nMöchten Sie die Gehälter für alle Kandidaten aktualisieren? (j/n): ")
    
    if antwort.lower() in ['j', 'ja', 'y', 'yes']:
        fill_salary_for_candidates()
    else:
        print("\nAbgebrochen.")
