""" 
====================================================
Programmname : KI-unterstütztes BMS – Mail Candidate Generator
Beschreibung : Generiert personalisierte E-Mails für Kandidaten aus Matching-Ergebnissen
               unter Verwendung von Ollama LLM (llama3.2:3b, mistral:7b oder phi3:3.8b)

====================================================
"""

import sys
import os
# Füge Projekt-Root zum Python-Pfad hinzu
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

import pandas as pd
import requests
import json
from datetime import datetime

# --------------------------------------------------
# KONFIGURATION
# --------------------------------------------------

RESULTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "results"
)

OLLAMA_URL = "http://localhost:11434/api/generate"

# Verfügbare Modelle
MODELS = {
    "llama3.2": "llama3.2:3b",      # Sehr gut für Deutsch
    "mistral": "mistral:latest",    # Exzellent für deutsche Texte
    "phi3": "phi3:3.8b"             # Kompakt, schnell
}

DEFAULT_MODEL = "llama3.2:3b"  # Bestes Modell für deutsche Texte


def create_empty_job_df():
    """Erstellt leeres Job-DataFrame als Fallback"""
    return pd.DataFrame([{
        'id': 'unknown',
        'position': 'N/A',
        'department': 'N/A',
        'ort': 'N/A',
        'klinik': 'N/A',
        'gehalt_von': 'N/A',
        'gehalt_bis': 'N/A',
        'job_description': '',
        'long_note': '',
        'status': 'N/A'
    }])


def check_ollama_running():
    """Prüft, ob Ollama läuft"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            models = response.json().get('models', [])
            return True, models
        return False, []
    except:
        return False, []


def list_excel_files():
    """Listet alle Excel-Dateien im results-Verzeichnis"""
    if not os.path.exists(RESULTS_DIR):
        print(f"✗ Verzeichnis {RESULTS_DIR} existiert nicht")
        return []
    
    excel_files = [f for f in os.listdir(RESULTS_DIR) if f.endswith('.xlsx')]
    excel_files.sort(reverse=True)  # Neueste zuerst
    
    return excel_files


def load_matching_results(filepath):
    """Lädt Matching-Ergebnisse aus Excel-Datei"""
    try:
        # Lese alle verfügbaren Sheet-Namen
        excel_file = pd.ExcelFile(filepath)
        available_sheets = excel_file.sheet_names
        
        print(f"\n✓ Verfügbare Sheets: {', '.join(available_sheets)}")
        
        # Versuche verschiedene mögliche Sheet-Namen für Matching-Daten
        matching_sheet = None
        job_sheet = None
        
        # Mögliche Namen für Matching-Sheet
        for sheet in available_sheets:
            if 'matching' in sheet.lower() or 'ergebnis' in sheet.lower():
                matching_sheet = sheet
                break
        
        # Wenn kein spezielles Matching-Sheet gefunden, nutze das erste Sheet
        if matching_sheet is None and len(available_sheets) > 0:
            matching_sheet = available_sheets[0]
            print(f"  → Verwende erstes Sheet für Kandidaten: {matching_sheet}")
        
        # Mögliche Namen für Job-Sheet
        for sheet in available_sheets:
            if 'job' in sheet.lower() or 'detail' in sheet.lower():
                job_sheet = sheet
                break
        
        # Lade Matching-Daten
        df_matching = pd.read_excel(filepath, sheet_name=matching_sheet)
        
        # Versuche Job-Details zu laden
        if job_sheet:
            df_job = pd.read_excel(filepath, sheet_name=job_sheet)
        else:
            # WARNUNG: Datei wurde nicht von Matching.py erstellt!
            print(f"  ⚠ WARNUNG: Kein 'Job_Details' Sheet gefunden!")
            print(f"  ⚠ Die Excel-Datei wurde nicht von Matching.py exportiert.")
            print(f"  ⚠ Bitte führen Sie Matching.py aus und wählen Sie dort den Excel-Export!")
            print(f"\n  → Versuche Job-Daten aus Datenbank zu laden...")
            
            # Versuche Job-ID aus Dateinamen zu extrahieren (z.B. matching_job_1004_...xlsx)
            import re
            import sys
            filename = os.path.basename(filepath)
            job_id_match = re.search(r'job[_\s]*(\d+)', filename, re.IGNORECASE)
            
            if job_id_match:
                job_id = int(job_id_match.group(1))
                print(f"  → Job-ID aus Dateinamen extrahiert: {job_id}")
                
                # Lade Job-Daten direkt aus Datenbank
                sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                from src.db_config import DB_CONFIG
                import psycopg
                
                conn = psycopg.connect(**DB_CONFIG)
                cur = conn.cursor()
                
                cur.execute("""
                    SELECT id, position, department, ort, gehalt_von, gehalt_bis,
                           job_description, long_note, klinik, status
                    FROM jobs
                    WHERE id = %s;
                """, (job_id,))
                
                job_row = cur.fetchone()
                if job_row:
                    cols = [desc[0] for desc in cur.description]
                    df_job = pd.DataFrame([job_row], columns=cols)
                    print(f"  ✓ Job-Daten aus Datenbank geladen")
                else:
                    print(f"  ✗ Job-ID {job_id} nicht in Datenbank gefunden")
                    df_job = create_empty_job_df()
                
                cur.close()
                conn.close()
            else:
                print(f"  ✗ Konnte Job-ID nicht aus Dateinamen extrahieren")
                df_job = create_empty_job_df()
        
        print(f"\n✓ Excel-Datei geladen: {os.path.basename(filepath)}")
        print(f"  Kandidaten: {len(df_matching)}")
        job_id_display = df_job['id'].iloc[0] if 'id' in df_job.columns else 'unknown'
        print(f"  Job-ID: {job_id_display}")
        if 'position' in df_job.columns:
            print(f"  Position: {df_job['position'].iloc[0]}")
        
        return df_matching, df_job
        
    except Exception as e:
        print(f"✗ Fehler beim Laden der Excel-Datei: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def build_email_prompt(candidate, job, tail_instructions: str | None = None) -> str:
    """Baut den Prompt für die LLM-E-Mail-Erzeugung.

    "tail_instructions" kann verwendet werden, um den Standard-
    Anweisungs-/FORMAT-Block zu überschreiben (z.B. aus der GUI).
    """
    first_name = candidate.get('first_name', 'Sehr geehrte/r')
    position = job.get('position', 'Facharzt')
    department = job.get('department', 'Radiologie')
    ort = job.get('ort', 'Deutschland')
    gehalt_von = job.get('gehalt_von', 'N/A')
    gehalt_bis = job.get('gehalt_bis', 'N/A')
    qualification = candidate.get('qualification', 'Facharzt')
    long_note = job.get('long_note') or ''

    # Skill-Informationen für das LLM zusammenstellen
    job_skills = (
        job.get('sonstiges_anforderungen')
        or job.get('skills_job')
        or ''
    )
    matched_skills = (
        candidate.get('skills_gemeinsam')
        or candidate.get('skills_match')
        or ''
    )

    header = f"""Schreibe eine kurze, professionelle Recruiting-E-Mail auf Deutsch mit maximal 5 Sätzen.
WICHTIG: Sprich die Kandidatin / den Kandidaten konsequent mit "Sie" an (formelle Anrede, kein "du").

KANDIDAT: {first_name}, {qualification}
POSITION: {position} {department} in {ort}
GEHALT: {gehalt_von}-{gehalt_bis} EUR

LONG_NOTE (Stellenbeschreibung):
{long_note}

GESUCHTE_SKILLS (aus der Stelle): {job_skills}
ÜBEREINSTIMMENDE_SKILLS (Kandidat): {matched_skills}"""

    if tail_instructions is None:
        tail = f"""

Anweisungen für den Inhalt:
- Formuliere höchstens ZWEI sehr kurze Sätze, die die Stelle anhand der LONG_NOTE grob und attraktiv beschreiben.
- Baue ein bis zwei Sätze ein, die die gesuchten Skills und die übereinstimmenden Skills positiv hervorheben (ohne Aufzählungslisten, sondern fließender Text).
- Erwähne Position, Ort und Gehalt in natürlicher Form.
- Schließe mit einer freundlichen Frage nach Gesprächs- oder Informationsinteresse.

FORMAT:
BETREFF: [Kurzer Betreff]

MAIL:
Guten Tag {first_name},

[Text nach obigen Anweisungen, maximal 5 Sätze.]

Mit freundlichen Grüßen"""
    else:
        # Benutzerdefinierter Block wird unverändert angehängt
        tail = "\n" + tail_instructions.strip()

    return header + tail


def generate_email_with_ollama_custom_prompt(prompt: str, job, model=DEFAULT_MODEL):
    """Sendet einen gegebenen Prompt an Ollama und parst Betreff/Text."""
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "num_predict": 200
                }
            },
            timeout=180
        )

        if response.status_code == 200:
            result = response.json()
            email_text = result.get('response', '').strip()

            if "BETREFF:" in email_text and "MAIL:" in email_text:
                parts = email_text.split("MAIL:")
                betreff = parts[0].replace("BETREFF:", "").strip()
                mail = parts[1].strip()
                return betreff, mail
            else:
                betreff = f"Interessante Stelle als {job.get('position', 'Facharzt')} in {job.get('ort', 'Deutschland')}"
                return betreff, email_text
        else:
            print(f"✗ Ollama API Fehler: {response.status_code}")
            if response.status_code == 404:
                print(f"  → Modell '{model}' nicht gefunden!")
                print(f"  → Installieren Sie es mit: ollama pull {model.split(':')[0]}")
            return None, None

    except requests.exceptions.RequestException as e:
        print(f"✗ Verbindungsfehler zu Ollama: {e}")
        print("  Tipp: Stellen Sie sicher, dass Ollama läuft (ollama serve)")
        return None, None
    except Exception as e:
        print(f"✗ Fehler bei E-Mail-Generierung: {e}")
        return None, None


def generate_email_with_ollama(candidate, job, model=DEFAULT_MODEL):
    """Rückwärtskompatible Hilfsfunktion: baut Standard-Prompt und ruft Ollama."""
    prompt = build_email_prompt(candidate, job)
    return generate_email_with_ollama_custom_prompt(prompt, job, model=model)


def generate_fallback_email(candidate, job):
    """Fallback: Einfache Template-basierte E-Mail"""
    first_name = candidate.get('first_name', 'Sehr geehrte/r')
    position = job.get('position', 'Facharzt')
    department = job.get('department', 'Radiologie')
    ort = job.get('ort', 'Deutschland')
    klinik = job.get('klinik', 'unserem Kunden')
    gehalt_von = job.get('gehalt_von', 'N/A')
    gehalt_bis = job.get('gehalt_bis', 'N/A')
    long_note = job.get('long_note') or ''

    # Kurze, max. zwei Sätze aus long_note extrahieren
    def _short_long_note(text: str, max_sentences: int = 2) -> str:
        if not text:
            return ""
        # Sehr einfache Satzaufteilung an Punkt/Fragezeichen/Ausrufezeichen
        import re as _re
        parts = _re.split(r"(?<=[.!?])\s+", text.strip())
        parts = [p.strip() for p in parts if p.strip()]
        return " " .join(parts[:max_sentences])

    long_note_short = _short_long_note(long_note)

    # Skills: gesuchte und übereinstimmende Skills kurz beschreiben
    job_skills = (
        job.get('sonstiges_anforderungen')
        or job.get('skills_job')
        or ''
    )
    matched_skills = (
        candidate.get('skills_gemeinsam')
        or candidate.get('skills_match')
        or ''
    )

    skill_sentence = ""
    if job_skills and matched_skills:
        skill_sentence = (
            f"Besonders interessant ist, dass die gesuchten Schwerpunkte ({job_skills}) "
            f"sehr gut zu Ihren vorhandenen Erfahrungen ({matched_skills}) passen."
        )
    elif job_skills:
        skill_sentence = (
            f"Für die Position werden insbesondere folgende Schwerpunkte gesucht: {job_skills}."
        )
    
    betreff = f"Interessante Stelle als {position} {department} in {ort}"

    beschreibung = ""
    if long_note_short:
        beschreibung = f" {long_note_short}"

    skills_text = f"\n\n{skill_sentence}" if skill_sentence else ""

    mail = f"""Guten Tag {first_name},

über unser Netzwerk sind wir auf Ihr Profil aufmerksam geworden.

Aktuell betreuen wir eine spannende Position als {position} im Bereich {department} bei {klinik} in {ort}.{beschreibung}

Die Position bietet unter anderem eine attraktive Vergütung von {gehalt_von} bis {gehalt_bis} EUR sowie gute Entwicklungsmöglichkeiten im Fachbereich {department}.{skills_text}

Hätten Sie Interesse an näheren Informationen zu dieser Position?

Ich freue mich auf Ihre Rückmeldung!

Mit freundlichen Grüßen
Ihr Recruiting-Team"""

    return betreff, mail


def save_emails_to_file(emails, job_id, output_dir=RESULTS_DIR):
    """
    Speichert generierte E-Mails in separate Textdateien
    Pro Kandidat eine Datei im Ordner results/job_{job_id}/
    """
    # Erstelle Unterordner mit Job-ID
    job_folder = os.path.join(output_dir, f"job_{job_id}")
    os.makedirs(job_folder, exist_ok=True)
    
    saved_files = []
    
    for email in emails:
        # Bereinige Namen für Dateinamen (entferne Sonderzeichen)
        clean_name = email['name'].replace(' ', '_').replace('/', '_').replace('\\', '_')
        
        # Dateiname: job_{job_id}_candidate_{candidate_id}_{name}.txt
        filename = f"job_{job_id}_candidate_{email['candidate_id']}_{clean_name}.txt"
        filepath = os.path.join(job_folder, filename)
        
        # Schreibe E-Mail in separate Datei
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write(f"JOB-ID: {job_id}\n")
            f.write(f"KANDIDAT: {email['name']}\n")
            f.write(f"KANDIDATEN-ID: {email['candidate_id']}\n")
            f.write(f"E-MAIL: {email['email']}\n")
            f.write(f"SCORE: {email['score']}\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"BETREFF: {email['betreff']}\n\n")
            f.write(f"MAIL:\n{email['mail']}\n")
        
        saved_files.append(filepath)
    
    print(f"\n✓ {len(saved_files)} E-Mails gespeichert in: {job_folder}")
    return job_folder, saved_files


def main():
    """Hauptfunktion"""
    print("\n" + "=" * 80)
    print("E-MAIL-GENERIERUNG FÜR KANDIDATEN")
    print("=" * 80)
    
    # 1. Liste Excel-Dateien auf
    print("\n1. Verfügbare Matching-Ergebnisse:\n")
    excel_files = list_excel_files()
    
    if not excel_files:
        print("✗ Keine Excel-Dateien im results-Verzeichnis gefunden")
        return
    
    for i, file in enumerate(excel_files[:10], 1):
        print(f"   {i}. {file}")
    
    # 2. Wähle Datei
    try:
        choice = int(input("\nWelche Datei möchten Sie verwenden? (Nummer): "))
        if choice < 1 or choice > len(excel_files):
            print("✗ Ungültige Auswahl")
            return
        selected_file = excel_files[choice - 1]
    except ValueError:
        print("✗ Ungültige Eingabe")
        return
    
    filepath = os.path.join(RESULTS_DIR, selected_file)
    
    # 3. Lade Daten
    df_matching, df_job = load_matching_results(filepath)
    
    if df_matching is None or df_job is None:
        return
    
    # 4. Prüfe Ollama und wähle Modell
    print("\n2. Prüfe Ollama-Verfügbarkeit...\n")
    
    ollama_running, available_models = check_ollama_running()
    
    if ollama_running:
        print("✓ Ollama läuft")
        if available_models:
            print(f"  Installierte Modelle: {', '.join([m.get('name', 'unknown') for m in available_models])}")
    else:
        print("✗ Ollama läuft nicht")
        print("\n  So starten Sie Ollama:")
        print("  1. Öffnen Sie ein neues PowerShell-Fenster")
        print("  2. Führen Sie aus: ollama serve")
        print("  3. Installieren Sie ein Modell: ollama pull mistral")
        print("\n  Alternativ: Verwenden Sie Option 4 (Template-Modus)\n")
    
    print("\n3. Verfügbare LLM-Modelle:\n")
    print("   1. mistral:latest (empfohlen für Deutsch)")
    print("   2. llama3.2:3b")
    print("   3. phi3:3.8b (schnell)")
    print("   4. Template (kein LLM, einfaches Template)")
    
    model_choice = input("\nWelches Modell verwenden? (1-4, Enter=1): ").strip() or "1"
    
    if model_choice == "1":
        model = MODELS["mistral"]
        use_llm = True
    elif model_choice == "2":
        model = MODELS["llama3.2"]
        use_llm = True
    elif model_choice == "3":
        model = MODELS["phi3"]
        use_llm = True
    elif model_choice == "4":
        use_llm = False
        model = None
    else:
        print("✗ Ungültige Auswahl, verwende mistral:latest")
        model = MODELS["mistral"]
        use_llm = True
    
    # 5. Generiere E-Mails
    print(f"\n4. Generiere E-Mails für {len(df_matching)} Kandidaten...\n")
    
    job_data = df_job.iloc[0].to_dict()
    job_id = job_data.get('id', 'unknown')
    emails = []
    
    for idx, row in df_matching.iterrows():
        candidate_data = row.to_dict()
        
        print(f"   [{idx+1}/{len(df_matching)}] {candidate_data.get('first_name', '')} {candidate_data.get('last_name', '')}...", end='')
        
        if use_llm:
            betreff, mail = generate_email_with_ollama(candidate_data, job_data, model)
            if betreff is None:
                # Fallback auf Template
                betreff, mail = generate_fallback_email(candidate_data, job_data)
                print(" Template ✓")
            else:
                print(" LLM ✓")
        else:
            betreff, mail = generate_fallback_email(candidate_data, job_data)
            print(" Template ✓")
        
        emails.append({
            'name': f"{candidate_data.get('first_name', '')} {candidate_data.get('last_name', '')}",
            'candidate_id': candidate_data.get('id', 'N/A'),
            'email': candidate_data.get('e_mail', 'N/A'),
            'score': candidate_data.get('gesamt_score', 'N/A'),
            'betreff': betreff,
            'mail': mail
        })
    
    # 6. Speichere E-Mails
    output_folder, saved_files = save_emails_to_file(emails, job_id)
    
    # 7. Zeige Beispiel
    print("\n" + "=" * 80)
    # 7. Zeige Beispiel
    print("\n" + "=" * 80)
    print("BEISPIEL E-MAIL (1. Kandidat)")
    print("=" * 80)
    print(f"\nJob-ID: {job_id}")
    print(f"Kandidat: {emails[0]['name']} (ID: {emails[0]['candidate_id']})")
    print(f"An: {emails[0]['email']}")
    print(f"Betreff: {emails[0]['betreff']}\n")
    print(emails[0]['mail'])
    print("\n" + "=" * 80)
    
    print(f"\n✓ Alle E-Mails wurden generiert und gespeichert")
    print(f"  Ordner: {output_folder}")
    print(f"  Anzahl Dateien: {len(saved_files)}")
    print(f"\nBeispiel-Datei: {os.path.basename(saved_files[0])}")
    print(f"\nSie können diese E-Mails nun überprüfen und versenden.")


if __name__ == "__main__":
    main()
