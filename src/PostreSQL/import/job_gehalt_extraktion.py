""" 
====================================================
Programmname : Gehaltsextraktion für Jobs
Beschreibung : Extrahiert Gehaltsinformationen aus job_description und long_note
und schreibt sie in gehalt_von und gehalt_bis.

====================================================
"""


import sys
import os
# Füge Projekt-Root zum Python-Pfad hinzu
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

import psycopg
import re
import random
from src.db_config import DB_CONFIG

# --------------------------------------------------
# KONFIGURATION aus fill_salary.py
# --------------------------------------------------

POSITIONEN_HIERARCHIE = {
    "assistenzarzt": 1,
    "facharzt": 2,
    "oberarzt": 3,
    "leitender oberarzt": 4,
    "chefarzt": 5,
    "standortleiter": 6,
    "gesellschafter": 7
}

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

BASISGEHAELTER = {
    "assistenzarzt": 60000,
    "facharzt": 100000,         # Erhöht von 85.000 auf 100.000
    "oberarzt": 140000,         # Erhöht von 120.000
    "leitender oberarzt": 170000,  # Erhöht von 150.000
    "chefarzt": 230000,         # Erhöht von 200.000
    "standortleiter": 200000,   # Erhöht von 180.000
    "gesellschafter": 280000    # Erhöht von 250.000
}

VARIANZ_PROZENT = 0.05  # ±5% wenn einzelner Wert gefunden


def normalize_text(text):
    """Normalisiert Text für Vergleiche"""
    if not text:
        return ""
    return text.lower().strip()


def extract_salary_from_text(text):
    """
    Extrahiert Gehaltsinformationen aus Text.
    
    Returns:
        tuple: (gehalt_von, gehalt_bis) oder (None, None)
    """
    if not text:
        return None, None
    
    text = str(text)
    
    # Pattern für verschiedene Gehaltsangaben
    patterns = [
        # Mit "k" Notation: "120k", "80k-100k", "80k bis 100k"
        r'(\d{1,3})\s*k\s*(?:-|bis)\s*(\d{1,3})\s*k',
        # Einzelwert mit k: "90k", "120k EUR"
        r'(\d{1,3})\s*k\s*(?:€|EUR|Euro)?',
        # Spanne: "80.000 - 100.000", "80000-100000", "80.000 bis 100.000"
        r'(\d{1,3}(?:[.,]\d{3})*)\s*(?:-|bis)\s*(\d{1,3}(?:[.,]\d{3})*)\s*(?:€|EUR|Euro)?',
        # Einzelwert: "90.000 EUR", "90000€", "90.000 Euro"
        r'(\d{1,3}(?:[.,]\d{3})*)\s*(?:€|EUR|Euro)',
        # Mit "p.a." oder "pro Jahr": "90.000 EUR p.a."
        r'(\d{1,3}(?:[.,]\d{3})*)\s*(?:€|EUR|Euro)?\s*(?:p\.a\.|pro Jahr|jährlich|per annum)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # Nimm das erste Match
            match = matches[0]
            
            if isinstance(match, tuple) and len(match) == 2:
                # Spanne gefunden
                von_str, bis_str = match
                von = parse_salary_number(von_str)
                bis = parse_salary_number(bis_str)
                if von and bis and von < bis:
                    return von, bis
            elif isinstance(match, str):
                # Einzelwert gefunden
                wert = parse_salary_number(match)
                if wert:
                    # ±5% Varianz
                    varianz = int(wert * VARIANZ_PROZENT)
                    return wert - varianz, wert + varianz
    
    return None, None


def parse_salary_number(salary_str):
    """
    Konvertiert Gehaltsstring zu Integer.
    Beispiele: "90.000" -> 90000, "90000" -> 90000, "120k" -> 120000
    """
    if not salary_str:
        return None
    
    salary_str = str(salary_str).strip()
    
    # Prüfe auf "k" Notation (z.B. "120k" = 120.000)
    if 'k' in salary_str.lower():
        # Extrahiere die Zahl vor dem k
        match = re.match(r'(\d+)', salary_str)
        if match:
            try:
                value = int(match.group(1)) * 1000
                # Plausibilitätsprüfung: Gehalt zwischen 20.000 und 500.000
                if 20000 <= value <= 500000:
                    return value
            except ValueError:
                pass
        return None
    
    # Standard-Verarbeitung: Entferne Punkte und Kommas
    cleaned = salary_str.replace(".", "").replace(",", "")
    
    try:
        value = int(cleaned)
        # Plausibilitätsprüfung: Gehalt zwischen 20.000 und 500.000
        if 20000 <= value <= 500000:
            return value
    except ValueError:
        pass
    
    return None


def get_position_level(position_text):
    """Ermittelt die Hierarchiestufe einer Position"""
    if not position_text:
        return None
    
    position_lower = normalize_text(position_text)
    
    for position, level in POSITIONEN_HIERARCHIE.items():
        if position in position_lower:
            return position
    
    return None


def get_fachbereich_from_text(text):
    """Extrahiert den Fachbereich aus einem Text"""
    if not text:
        return None
    
    text_lower = normalize_text(text)
    
    for fach in FACHBEREICH_FAKTOREN.keys():
        if fach in text_lower:
            return fach
    
    return None


def calculate_salary_estimate(position, department):
    """
    Berechnet eine Gehaltsschätzung basierend auf Position und Fachbereich.
    Analog zu fill_salary.py
    """
    # Basis-Gehalt ermitteln
    if position not in BASISGEHAELTER:
        basis_gehalt = BASISGEHAELTER["facharzt"]
    else:
        basis_gehalt = BASISGEHAELTER[position]
    
    # Fachbereich-Faktor anwenden
    fach_faktor = FACHBEREICH_FAKTOREN.get(department, 1.05)
    
    # Berechne Gehalt
    gehalt_mitte = basis_gehalt * fach_faktor
    
    # Erstelle Spanne (±15%)
    varianz = gehalt_mitte * 0.15
    gehalt_von = int((gehalt_mitte - varianz) / 1000) * 1000
    gehalt_bis = int((gehalt_mitte + varianz) / 1000) * 1000
    
    return gehalt_von, gehalt_bis


def extract_and_update_salaries():
    """
    Hauptfunktion: Extrahiert Gehälter aus job_description und long_note
    """
    print("\n" + "=" * 80)
    print("Gehaltsextraktion für Jobs-Tabelle")
    print("=" * 80)
    
    try:
        conn = psycopg.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Lade Jobs ohne Gehaltsangaben ODER mit job_description/long_note
        print("\n1. Lade Jobs aus Datenbank...")
        cur.execute("""
            SELECT id, position, department, job_description, long_note, 
                   gehalt_von, gehalt_bis
            FROM jobs
            WHERE (gehalt_von IS NULL OR gehalt_bis IS NULL)
               OR (job_description IS NOT NULL OR long_note IS NOT NULL)
            ORDER BY id;
        """)
        
        jobs = cur.fetchall()
        print(f"✓ {len(jobs)} Jobs geladen\n")
        
        if not jobs:
            print("ℹ Keine Jobs zum Aktualisieren")
            cur.close()
            conn.close()
            return
        
        # 2. Analyse und Vorschau
        print("2. Analysiere Gehaltsinformationen...")
        print("\n" + "=" * 80)
        print("ALLE EINTRÄGE")
        print("=" * 80 + "\n")
        
        updates = []
        stats = {
            "aus_text_extrahiert": 0,
            "aus_position_berechnet": 0,
            "keine_info": 0
        }
        
        for job_id, position, department, job_desc, long_note, current_von, current_bis in jobs:
            # Versuche Gehalt aus Texten zu extrahieren
            von_desc, bis_desc = extract_salary_from_text(job_desc)
            von_note, bis_note = extract_salary_from_text(long_note)
            
            # Bevorzuge job_description, dann long_note
            if von_desc and bis_desc:
                gehalt_von, gehalt_bis = von_desc, bis_desc
                quelle = "job_description (extrahiert)"
                stats["aus_text_extrahiert"] += 1
            elif von_note and bis_note:
                gehalt_von, gehalt_bis = von_note, bis_note
                quelle = "long_note (extrahiert)"
                stats["aus_text_extrahiert"] += 1
            else:
                # Keine Gehaltsangabe gefunden -> Berechne aus Position und Department
                pos = get_position_level(position)
                fach = get_fachbereich_from_text(department)
                
                if pos or fach:
                    gehalt_von, gehalt_bis = calculate_salary_estimate(
                        pos or "facharzt",
                        fach or "innere medizin"
                    )
                    quelle = f"berechnet (Position: {pos or 'facharzt'}, Fach: {fach or 'innere medizin'})"
                    stats["aus_position_berechnet"] += 1
                else:
                    # Keine Info verfügbar
                    gehalt_von, gehalt_bis = None, None
                    quelle = "keine Information"
                    stats["keine_info"] += 1
            
            # Nur aktualisieren wenn neue Werte vorhanden
            if gehalt_von and gehalt_bis:
                updates.append({
                    'id': job_id,
                    'position': position,
                    'department': department,
                    'von_alt': current_von,
                    'bis_alt': current_bis,
                    'von_neu': gehalt_von,
                    'bis_neu': gehalt_bis,
                    'quelle': quelle
                })
                
                # Zeige ALLE Einträge
                print(f"Job ID {job_id}:")
                print(f"  Position: {position or '(leer)'}")
                print(f"  Department: {department or '(leer)'}")
                print(f"  Gehalt (alt): {current_von} - {current_bis}")
                print(f"  Gehalt (neu): {gehalt_von:,} - {gehalt_bis:,} EUR")
                print(f"  Quelle: {quelle}")
                print()
        
        print("\n" + "=" * 80)
        print("STATISTIKEN")
        print("=" * 80)
        print(f"Aus Text extrahiert: {stats['aus_text_extrahiert']}")
        print(f"Aus Position/Fach berechnet: {stats['aus_position_berechnet']}")
        print(f"Keine Information: {stats['keine_info']}")
        print(f"\nGesamt zu aktualisieren: {len(updates)}")
        print("=" * 80)
        
        if not updates:
            print("\nℹ Keine Änderungen erforderlich")
            cur.close()
            conn.close()
            return
        
        # 3. Bestätigung
        antwort = input("\nMöchten Sie die Änderungen durchführen? (j/n): ").strip().lower()
        
        if antwort not in ['j', 'ja', 'y', 'yes']:
            print("✗ Abgebrochen")
            cur.close()
            conn.close()
            return
        
        # 4. Updates durchführen
        print("\n3. Führe Updates durch...")
        
        erfolg = 0
        fehler = 0
        
        for update in updates:
            try:
                cur.execute("""
                    UPDATE jobs 
                    SET gehalt_von = %s, gehalt_bis = %s
                    WHERE id = %s;
                """, (update['von_neu'], update['bis_neu'], update['id']))
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


if __name__ == "__main__":
    extract_and_update_salaries()
