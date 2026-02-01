#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
slm_to_sql.py

Interaktive Kandidaten-Aktualisierung mit Ollama (mistral:latest)
- Skills hinzufügen/aktualisieren
- Telefonnummer aktualisieren
- E-Mail-Adresse aktualisieren
"""

import sys
import os
# Füge Projekt-Root zum Python-Pfad hinzu
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

import psycopg
import requests
import json
from src.db_config import DB_CONFIG

# --------------------------------------------------
# KONFIGURATION
# --------------------------------------------------

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral:latest"


def check_ollama():
    """Prüft ob Ollama läuft"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False


def search_candidates(conn, search_term):
    """
    Sucht Kandidaten nach Name, E-Mail oder ID
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, first_name, last_name, e_mail, tel, position_now, 
                   department, skills
            FROM candidates
            WHERE 
                LOWER(first_name) LIKE LOWER(%s) OR
                LOWER(last_name) LIKE LOWER(%s) OR
                LOWER(e_mail) LIKE LOWER(%s) OR
                id::TEXT = %s
            LIMIT 20;
        """, (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', search_term))
        
        results = cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        
        return [dict(zip(cols, row)) for row in results]


def display_candidate(candidate):
    """Zeigt Kandidaten-Details an"""
    print("\n" + "=" * 80)
    print(f"KANDIDAT ID: {candidate['id']}")
    print("=" * 80)
    print(f"Name:        {candidate['first_name']} {candidate['last_name']}")
    print(f"E-Mail:      {candidate['e_mail'] or 'N/A'}")
    print(f"Telefon:     {candidate['tel'] or 'N/A'}")
    print(f"Position:    {candidate['position_now'] or 'N/A'}")
    print(f"Fachbereich: {candidate['department'] or 'N/A'}")
    print(f"\nSkills:      {candidate['skills'] or '(leer)'}")
    print("=" * 80)


def ask_ollama(prompt, context=""):
    """
    Sendet Anfrage an Ollama und gibt Antwort zurück
    """
    full_prompt = f"{context}\n\n{prompt}" if context else prompt
    
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,  # Niedrig für präzise Antworten
                    "top_p": 0.9
                }
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get('response', '').strip()
        else:
            return None
            
    except Exception as e:
        print(f"✗ Fehler bei Ollama-Anfrage: {e}")
        return None


def extract_skills_with_llm(candidate):
    """
    Nutzt Ollama um Skills aus den Kandidaten-Daten zu extrahieren/vorschlagen
    """
    prompt = f"""Analysiere folgende Kandidaten-Information und extrahiere oder schlage relevante Skills vor.

KANDIDAT:
- Position: {candidate['position_now']}
- Fachbereich: {candidate['department']}
- Aktuelle Skills: {candidate['skills'] or 'keine angegeben'}

AUFGABE:
Liste nur die wichtigsten Skills als kommaseparierte Liste auf (max. 10 Skills).
Fokus auf medizinische/berufliche Fähigkeiten.

FORMAT: Skill1, Skill2, Skill3

ANTWORT:"""

    return ask_ollama(prompt)


def update_candidate_field(conn, candidate_id, field_name, new_value):
    """
    Aktualisiert ein Feld eines Kandidaten
    """
    with conn.cursor() as cur:
        cur.execute(f"""
            UPDATE candidates
            SET {field_name} = %s
            WHERE id = %s;
        """, (new_value, candidate_id))
        conn.commit()


def interactive_update(conn, candidate):
    """
    Interaktiver Update-Prozess für einen Kandidaten
    """
    while True:
        display_candidate(candidate)
        
        print("\nWas möchten Sie aktualisieren?")
        print("  1. Skills hinzufügen/bearbeiten")
        print("  2. Skills mit LLM generieren lassen")
        print("  3. E-Mail-Adresse ändern")
        print("  4. Telefonnummer ändern")
        print("  5. Kandidaten neu laden")
        print("  0. Zurück zur Suche")
        
        choice = input("\nAuswahl (0-5): ").strip()
        
        if choice == "1":
            # Manuelle Skills-Eingabe
            print(f"\nAktuelle Skills: {candidate['skills'] or '(leer)'}")
            new_skills = input("Neue Skills (kommasepariert, Enter = keine Änderung): ").strip()
            
            if new_skills:
                update_candidate_field(conn, candidate['id'], 'skills', new_skills)
                print("✓ Skills aktualisiert")
                candidate['skills'] = new_skills
            
        elif choice == "2":
            # LLM-generierte Skills
            print("\n⏳ Generiere Skills mit Ollama...")
            suggested_skills = extract_skills_with_llm(candidate)
            
            if suggested_skills:
                print(f"\n💡 Vorschlag von Ollama:")
                print(f"   {suggested_skills}")
                
                accept = input("\nÜbernehmen? (j/n/bearbeiten): ").strip().lower()
                
                if accept in ['j', 'ja', 'y', 'yes']:
                    update_candidate_field(conn, candidate['id'], 'skills', suggested_skills)
                    print("✓ Skills übernommen")
                    candidate['skills'] = suggested_skills
                elif accept == 'bearbeiten':
                    edited = input(f"Bearbeiten Sie die Skills:\n> ").strip()
                    if edited:
                        update_candidate_field(conn, candidate['id'], 'skills', edited)
                        print("✓ Skills gespeichert")
                        candidate['skills'] = edited
            else:
                print("✗ Konnte keine Skills generieren")
        
        elif choice == "3":
            # E-Mail ändern
            print(f"\nAktuelle E-Mail: {candidate['e_mail'] or '(leer)'}")
            new_email = input("Neue E-Mail (Enter = keine Änderung): ").strip()
            
            if new_email:
                update_candidate_field(conn, candidate['id'], 'e_mail', new_email)
                print("✓ E-Mail aktualisiert")
                candidate['e_mail'] = new_email
        
        elif choice == "4":
            # Telefon ändern
            print(f"\nAktuelle Telefonnummer: {candidate['tel'] or '(leer)'}")
            new_tel = input("Neue Telefonnummer (Enter = keine Änderung): ").strip()
            
            if new_tel:
                update_candidate_field(conn, candidate['id'], 'tel', new_tel)
                print("✓ Telefonnummer aktualisiert")
                candidate['tel'] = new_tel
        
        elif choice == "5":
            # Neu laden
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, first_name, last_name, e_mail, tel, position_now, 
                           department, skills
                    FROM candidates
                    WHERE id = %s;
                """, (candidate['id'],))
                
                row = cur.fetchone()
                cols = [desc[0] for desc in cur.description]
                candidate = dict(zip(cols, row))
                print("✓ Daten neu geladen")
        
        elif choice == "0":
            break
        else:
            print("⚠ Ungültige Auswahl")


def main():
    """Hauptfunktion"""
    print("\n" + "=" * 80)
    print("KANDIDATEN-AKTUALISIERUNG MIT OLLAMA")
    print("=" * 80)
    
    # Prüfe Ollama
    print("\n1. Prüfe Ollama-Verfügbarkeit...\n")
    if check_ollama():
        print(f"✓ Ollama läuft (Modell: {MODEL})")
    else:
        print("⚠ Ollama läuft nicht - LLM-Funktionen nicht verfügbar")
        print("  Starten Sie Ollama mit: ollama serve")
        print("  Sie können weiterhin manuelle Updates vornehmen\n")
    
    # Verbinde mit DB
    print("\n2. Verbinde mit Datenbank...\n")
    try:
        conn = psycopg.connect(**DB_CONFIG)
        print("✓ Datenbankverbindung hergestellt")
    except Exception as e:
        print(f"✗ Fehler bei Datenbankverbindung: {e}")
        return
    
    # Hauptschleife
    try:
        while True:
            print("\n" + "=" * 80)
            print("KANDIDATEN-SUCHE")
            print("=" * 80)
            
            search = input("\nSuche nach Name, E-Mail oder ID (Enter = Beenden): ").strip()
            
            if not search:
                print("\n✓ Beendet")
                break
            
            # Suche Kandidaten
            results = search_candidates(conn, search)
            
            if not results:
                print(f"\n⚠ Keine Kandidaten gefunden für: {search}")
                continue
            
            # Zeige Ergebnisse
            print(f"\n✓ {len(results)} Kandidat(en) gefunden:\n")
            for i, candidate in enumerate(results, 1):
                print(f"{i}. {candidate['first_name']} {candidate['last_name']} "
                      f"(ID {candidate['id']}) - {candidate['e_mail'] or 'keine E-Mail'}")
            
            # Wähle Kandidaten
            try:
                choice = int(input(f"\nWelchen Kandidaten bearbeiten? (1-{len(results)}, 0=zurück): "))
                
                if choice == 0:
                    continue
                elif 1 <= choice <= len(results):
                    selected = results[choice - 1]
                    interactive_update(conn, selected)
                else:
                    print("⚠ Ungültige Auswahl")
            except ValueError:
                print("⚠ Bitte Zahl eingeben")
    
    finally:
        conn.close()
        print("\n✓ Datenbankverbindung geschlossen")


if __name__ == "__main__":
    main()