#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wunscharbeitsort.py

Leitet den Wunscharbeitsort aus der available-Spalte ab:
- "Deutschland" → "DE"
- Städtenamen aus CSV → Stadt1, Stadt2, ...
"""

import pandas as pd
import psycopg
import re

# Konfiguration
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "postgres",
    "user": "postgres",
    "password": "bigdataconsulting"
}

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


def load_staedte():
    """
    Lädt Städte und Bundesländer aus der CSV.
    Orientiert sich an intelligente_Suchabfrage.py
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


def extract_wunscharbeitsort(available_text, orte, debug=False):
    """
    Extrahiert Wunscharbeitsort aus available-Text.
    
    Args:
        available_text: Text aus der available-Spalte
        orte: Set mit deutschen Städten und Bundesländern
        debug: Wenn True, gibt Debug-Informationen aus
    
    Returns:
        String mit extrahierten Orten (kommasepariert)
    """
    if not available_text or pd.isna(available_text):
        return None
    
    available_text = str(available_text).strip()
    
    if debug:
        print(f"\n   Debug: available_text = '{available_text}'")
    
    # Normalisiere Text für Suche
    text_lower = available_text.lower()
    
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
        print(f"   Suche in: '{text_ersetzt}'")
        print(f"   Anzahl Orte zu prüfen: {len(orte)}")
    
    for ort in orte_sortiert:
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
        return ", ".join(unique_orte)
    
    return None


def update_wunscharbeitsort():
    """
    Aktualisiert die wunscharbeitsort-Spalte basierend auf available.
    """
    print("=" * 80)
    print("Wunscharbeitsort aus available ableiten")
    print("=" * 80)
    
    # 1. Städte und Bundesländer laden
    print("\n1. Lade Städte und Bundesländer...")
    orte = load_staedte()
    
    if not orte:
        print("✗ Keine Orte geladen - Abbruch")
        return
    
    # 2. Kandidaten laden
    print("\n2. Lade Kandidaten aus Datenbank...")
    
    try:
        conn = psycopg.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Hole alle Kandidaten mit available- oder short_note-Werten OHNE bestehenden wunscharbeitsort
        cur.execute("""
            SELECT id, available, short_note, wunscharbeitsort 
            FROM candidates
            WHERE (available IS NOT NULL AND available != '' 
                   OR short_note IS NOT NULL AND short_note != '')
            AND (wunscharbeitsort IS NULL OR wunscharbeitsort = '')
            ORDER BY id;
        """)
        
        kandidaten = cur.fetchall()
        print(f"✓ {len(kandidaten)} Kandidaten mit available-Werten gefunden")
        
        if not kandidaten:
            print("ℹ Keine Kandidaten zum Aktualisieren")
            cur.close()
            conn.close()
            return
        
        # 3. Analyse und Vorschau
        print("\n3. Analysiere available-Werte...")
        print("\n" + "=" * 80)
        print("VORSCHAU (erste 10 Einträge)")
        print("=" * 80 + "\n")
        
        updates = []
        
        for idx, (kandidat_id, available, short_note, aktueller_wunsch) in enumerate(kandidaten):
            # Suche in beiden Spalten
            orte_aus_available = extract_wunscharbeitsort(available, orte) if available else None
            orte_aus_note = extract_wunscharbeitsort(short_note, orte) if short_note else None
            
            # Kombiniere Ergebnisse
            gefundene_orte = []
            if orte_aus_available:
                gefundene_orte.extend(orte_aus_available.split(", "))
            if orte_aus_note:
                gefundene_orte.extend(orte_aus_note.split(", "))
            
            # Entferne Duplikate und sortiere
            if gefundene_orte:
                unique_orte = sorted(set(gefundene_orte))
                neuer_wunsch = ", ".join(unique_orte)
            else:
                neuer_wunsch = None
            
            # Nur aktualisieren wenn neuer Wert gefunden wurde
            if neuer_wunsch:
                updates.append({
                    'id': kandidat_id,
                    'available': available,
                    'short_note': short_note,
                    'alt': aktueller_wunsch,
                    'neu': neuer_wunsch
                })
                
                # Zeige erste 10
                if len(updates) <= 10:
                    print(f"ID {kandidat_id}:")
                    if available:
                        print(f"  available: {available[:80]}{'...' if len(available) > 80 else ''}")
                    if short_note:
                        print(f"  short_note: {short_note[:80]}{'...' if len(short_note) > 80 else ''}")
                    print(f"  alt: {aktueller_wunsch or '(leer)'}")
                    print(f"  neu: {neuer_wunsch}")
                    print()
        
        if len(updates) > 10:
            print(f"... und {len(updates) - 10} weitere")
        
        print("\n" + "=" * 80)
        print(f"ZUSAMMENFASSUNG: {len(updates)} Kandidaten würden aktualisiert")
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
                    UPDATE candidates 
                    SET wunscharbeitsort = %s 
                    WHERE id = %s;
                """, (update['neu'], update['id']))
                erfolg += 1
            except Exception as e:
                fehler += 1
                print(f"✗ Fehler bei ID {update['id']}: {e}")
        
        conn.commit()
        cur.close()
        conn.close()
        
        print("\n" + "=" * 80)
        print("ERGEBNIS")
        print("=" * 80)
        print(f"✓ {erfolg} Kandidaten erfolgreich aktualisiert")
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
    
    # Test-Modus für einzelne ID
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        if len(sys.argv) < 3:
            print("Usage: python wunscharbeitsort.py --test <ID>")
            sys.exit(1)
        
        test_id = sys.argv[2]
        
        print("=" * 80)
        print(f"TEST-MODUS für ID {test_id}")
        print("=" * 80)
        
        # Städte und Bundesländer laden
        print("\nLade Städte und Bundesländer...")
        orte = load_staedte()
        
        # Kandidat laden
        print(f"\nLade Kandidat ID {test_id}...")
        try:
            conn = psycopg.connect(**DB_CONFIG)
            cur = conn.cursor()
            
            cur.execute("""
                SELECT id, available, short_note, wunscharbeitsort 
                FROM candidates
                WHERE id = %s;
            """, (test_id,))
            
            result = cur.fetchone()
            
            if not result:
                print(f"✗ Kandidat ID {test_id} nicht gefunden")
                cur.close()
                conn.close()
                sys.exit(1)
            
            kandidat_id, available, short_note, wunscharbeitsort = result
            
            print(f"\nKandidat ID: {kandidat_id}")
            print(f"available: '{available}'")
            print(f"short_note: '{short_note}'")
            print(f"wunscharbeitsort (aktuell): '{wunscharbeitsort}'")
            
            print("\n" + "-" * 80)
            print("ANALYSE available:")
            orte_aus_available = extract_wunscharbeitsort(available, orte, debug=True) if available else None
            print("-" * 80)
            
            print("\n" + "-" * 80)
            print("ANALYSE short_note:")
            orte_aus_note = extract_wunscharbeitsort(short_note, orte, debug=True) if short_note else None
            print("-" * 80)
            
            # Kombiniere Ergebnisse
            gefundene_orte = []
            if orte_aus_available:
                gefundene_orte.extend(orte_aus_available.split(", "))
            if orte_aus_note:
                gefundene_orte.extend(orte_aus_note.split(", "))
            
            if gefundene_orte:
                unique_orte = sorted(set(gefundene_orte))
                neuer_wunsch = ", ".join(unique_orte)
            else:
                neuer_wunsch = None
            
            print(f"\nERGEBNIS kombiniert: {neuer_wunsch or '(nichts gefunden)'}")
            
            cur.close()
            conn.close()
            
        except Exception as e:
            print(f"✗ Fehler: {e}")
            raise
    else:
        update_wunscharbeitsort()
