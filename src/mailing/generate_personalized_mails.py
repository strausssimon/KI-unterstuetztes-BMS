""" 
====================================================
Programmname : Mail-Vorlagen-Generator
Beschreibung : Generiert personalisierte E-Mails aus echten Vorlagen mit Hilfe von Ollama
Prozess:
1. Lade echte E-Mails aus data/db/mails
2. Analysiere mit Ollama → Extrahiere Templates mit Platzhaltern
3. Nutze Templates um neue, personalisierte E-Mails zu generieren

====================================================
"""

import sys
import os
# Füge Projekt-Root zum Python-Pfad hinzu
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

import pandas as pd
import requests
import random
from datetime import datetime

# --------------------------------------------------
# KONFIGURATION
# --------------------------------------------------

RESULTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "results"
)

MAIL_TEMPLATES_DIR = os.path.join(
    project_root,
    "data", "db", "mails"
)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral:latest"


def check_ollama():
    """Prüft ob Ollama läuft"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False


def load_email_template(filepath):
    """Lädt eine einzelne E-Mail-Vorlage"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except:
        try:
            with open(filepath, 'r', encoding='latin-1') as f:
                return f.read().strip()
        except Exception as e:
            print(f"⚠ Fehler beim Lesen von {os.path.basename(filepath)}: {e}")
            return None


def load_real_emails():
    """Lädt alle echten E-Mails aus data/db/mails"""
    if not os.path.exists(MAIL_TEMPLATES_DIR):
        return []
    
    emails = []
    for filename in os.listdir(MAIL_TEMPLATES_DIR):
        if filename.endswith('.txt'):
            filepath = os.path.join(MAIL_TEMPLATES_DIR, filename)
            content = load_email_template(filepath)
            if content:
                emails.append({
                    'filename': filename,
                    'content': content
                })
    
    return emails


def create_template_from_emails_with_llm(real_emails):
    """
    Analysiert echte E-Mails und extrahiert ein wiederverwendbares Template
    """
    # Nimm 3 repräsentative Beispiele (weniger = schneller)
    sample_emails = real_emails[:min(3, len(real_emails))]
    
    emails_text = "\n\n--- NÄCHSTE E-MAIL ---\n\n".join([e['content'] for e in sample_emails])
    
    prompt = f"""Du bist ein Experte für Text-Analyse. Analysiere die folgenden ECHTEN E-Mails aus der Praxis und extrahiere daraus ein TEMPLATE/MUSTER.

AUFGABE:
1. Erkenne die gemeinsame STRUKTUR (Anrede, Einleitung, Hauptteil, Abschluss)
2. Erkenne den SCHREIBSTIL (formell/informell, Du/Sie, Tonalität)
3. Identifiziere PLATZHALTER für variable Daten:
   - [ANREDE] für Herr/Frau Dr. [NAME]
   - [POSITION] für Jobtitel
   - [FACHBEREICH] für Abteilung/Spezialisierung
   - [ORT] für Standort
   - [GEHALT_VON] - [GEHALT_BIS] für Gehaltsspanne
   - [UNTERNEHMEN] für Firma/Klinik
   - [DETAILS] für job-spezifische Details

4. Erstelle EIN TEMPLATE, das die Essenz dieser E-Mails erfasst

ECHTE E-MAILS ZUR ANALYSE:
{emails_text}

ERSTELLE NUN EIN TEMPLATE IM FOLGENDEN FORMAT:

TEMPLATE:
---
[Hier das Template mit Platzhaltern]
---

STIL-HINWEISE:
- Tonalität: [beschreibe]
- Anrede-Form: [Du/Sie]
- Besonderheiten: [liste auf]

NUR DAS TEMPLATE AUSGEBEN (keine Erklärungen davor/danach):"""

    try:
        print("\n⏳ Analysiere E-Mails und erstelle Template... (kann 60-120 Sek. dauern)")
        
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "num_predict": 2000
                }
            },
            timeout=300  # 5 Minuten für Template-Erstellung
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get('response', '').strip()
        else:
            return None
            
    except Exception as e:
        print(f"✗ Fehler bei Template-Erstellung: {e}")
        return None


def fill_template_with_data(template, candidate, job):
    """
    Füllt das Template mit echten Kandidaten- und Job-Daten
    """
    first_name = candidate.get('first_name', 'N/A')
    last_name = candidate.get('last_name', 'N/A')
    qualification = candidate.get('qualification', 'Facharzt')
    
    job_position = job.get('position', 'Facharzt')
    job_department = job.get('department', 'Radiologie')
    job_ort = job.get('ort', 'Deutschland')
    job_gehalt_von = job.get('gehalt_von', 'N/A')
    job_gehalt_bis = job.get('gehalt_bis', 'N/A')
    job_klinik = job.get('klinik', 'unserem Kunden')
    job_beschreibung = job.get('job_description', '')
    
    # Sichere Konvertierung von job_beschreibung zu String
    if isinstance(job_beschreibung, float):
        job_beschreibung = ''
    elif job_beschreibung:
        job_beschreibung = str(job_beschreibung)
    
    # Bestimme Anrede
    if qualification and 'dr' in qualification.lower():
        anrede = f"Herr Dr. {last_name}" if candidate.get('geschlecht') != 'weiblich' else f"Frau Dr. {last_name}"
    else:
        anrede = f"Herr {last_name}" if candidate.get('geschlecht') != 'weiblich' else f"Frau {last_name}"
    
    prompt = f"""Du bist ein Recruiter. Fülle das folgende E-MAIL-TEMPLATE mit den echten Daten.

TEMPLATE:
{template}

ERSETZE DIE PLATZHALTER MIT FOLGENDEN DATEN:

KANDIDAT:
- Anrede: {anrede}
- Vorname: {first_name}
- Nachname: {last_name}
- Qualification: {qualification}

JOB:
- Position: {job_position}
- Fachbereich: {job_department}
- Standort: {job_ort}
- Gehalt: {job_gehalt_von} - {job_gehalt_bis} EUR
- Unternehmen: {job_klinik}
- Details: {job_beschreibung[:200] if job_beschreibung else 'moderne Position mit vielfältigen Aufgaben'}

WICHTIG:
1. Behalte den EXAKTEN Schreibstil bei
2. Ersetze NUR die Platzhalter
3. Passe Formulierungen natürlich an (z.B. Artikel, Deklination)
4. Keine zusätzlichen Informationen erfinden
5. Behalte die Struktur EXAKT bei

AUSGABE NUR DIE FERTIGE E-MAIL:"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.5,
                    "top_p": 0.9,
                    "num_predict": 1000
                }
            },
            timeout=90
        )
        
        if response.status_code == 200:
            result = response.json()
            email_text = result.get('response', '').strip()
            email_text = email_text.replace('```', '').strip()
            return email_text
        else:
            return None
            
    except Exception as e:
        print(f"✗ Fehler beim Füllen: {e}")
        return None


def list_excel_files():
    """Listet alle Excel-Dateien im results-Verzeichnis"""
    if not os.path.exists(RESULTS_DIR):
        return []
    
    excel_files = [f for f in os.listdir(RESULTS_DIR) if f.endswith('.xlsx')]
    excel_files.sort(reverse=True)  # Neueste zuerst
    
    return excel_files


def load_matching_data(filepath):
    """Lädt Matching-Daten aus Excel"""
    try:
        excel_file = pd.ExcelFile(filepath)
        
        # Versuche die richtigen Sheets zu finden
        matching_sheet = None
        job_sheet = None
        
        for sheet in excel_file.sheet_names:
            if 'matching' in sheet.lower() or 'ergebnis' in sheet.lower():
                matching_sheet = sheet
            elif 'job' in sheet.lower() or 'detail' in sheet.lower():
                job_sheet = sheet
        
        if not matching_sheet:
            matching_sheet = excel_file.sheet_names[0]
        
        df_matching = pd.read_excel(filepath, sheet_name=matching_sheet)
        
        if job_sheet:
            df_job = pd.read_excel(filepath, sheet_name=job_sheet)
        else:
            # Erstelle leeres Job-DataFrame
            df_job = pd.DataFrame([{
                'id': 'unknown',
                'position': 'N/A',
                'department': 'N/A',
                'ort': 'N/A',
                'gehalt_von': 'N/A',
                'gehalt_bis': 'N/A'
            }])
        
        return df_matching, df_job
        
    except Exception as e:
        print(f"✗ Fehler beim Laden: {e}")
        return None, None


def analyze_and_personalize_with_llm(template, candidate, job):
    """
    VERALTET - wird durch fill_template_with_data ersetzt
    """
    return fill_template_with_data(template, candidate, job)


def extract_subject_from_email(email_text):
    """Extrahiert Betreff aus E-Mail (falls vorhanden)"""
    lines = email_text.split('\n')
    
    for line in lines[:5]:  # Prüfe erste 5 Zeilen
        if line.strip().lower().startswith('betreff:'):
            return line.split(':', 1)[1].strip()
    
    # Fallback: Erstelle einfachen Betreff
    return "Spannende berufliche Möglichkeit"


def save_personalized_emails(emails, job_id, output_dir=RESULTS_DIR):
    """
    Speichert personalisierte E-Mails in separate Dateien
    """
    job_folder = os.path.join(output_dir, f"job_{job_id}")
    os.makedirs(job_folder, exist_ok=True)
    
    saved_files = []
    
    for email in emails:
        clean_name = email['name'].replace(' ', '_').replace('/', '_').replace('\\', '_')
        filename = f"job_{job_id}_candidate_{email['candidate_id']}_{clean_name}.txt"
        filepath = os.path.join(job_folder, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write(f"JOB-ID: {job_id}\n")
            f.write(f"KANDIDAT: {email['name']}\n")
            f.write(f"KANDIDATEN-ID: {email['candidate_id']}\n")
            f.write(f"E-MAIL: {email['email']}\n")
            f.write(f"VORLAGE: {email['template_used']}\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"BETREFF: {email['betreff']}\n\n")
            f.write(f"{email['mail']}\n")
        
        saved_files.append(filepath)
    
    return job_folder, saved_files


def main():
    """Hauptfunktion"""
    print("\n" + "=" * 80)
    print("PERSONALISIERTE E-MAIL-GENERIERUNG AUS ECHTEN E-MAILS")
    print("=" * 80)
    
    # 1. Prüfe Ollama
    print("\n1. Prüfe Ollama-Verfügbarkeit...\n")
    if check_ollama():
        print(f"✓ Ollama läuft (Modell: {MODEL})")
    else:
        print("✗ Ollama läuft nicht!")
        print("  Starten Sie Ollama mit: ollama serve")
        return
    
    # 2. Lade echte E-Mails
    print("\n2. Lade echte E-Mails aus data/db/mails...\n")
    real_emails = load_real_emails()
    
    if not real_emails:
        print("✗ Keine E-Mails gefunden in data/db/mails")
        return
    
    print(f"✓ {len(real_emails)} echte E-Mails geladen")
    
    # 3. Erstelle Template aus echten E-Mails
    print("\n3. Erstelle Template aus echten E-Mails...\n")
    
    template = create_template_from_emails_with_llm(real_emails)
    
    if not template:
        print("✗ Konnte kein Template erstellen")
        return
    
    print("\n" + "=" * 80)
    print("ERSTELLTES TEMPLATE")
    print("=" * 80)
    print(template[:800] + "..." if len(template) > 800 else template)
    print("=" * 80)
    
    # Optional: Template speichern
    save_template = input("\nTemplate speichern? (j/n): ").strip().lower()
    if save_template in ['j', 'ja', 'y', 'yes']:
        template_file = os.path.join(RESULTS_DIR, f"email_template_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(template_file, 'w', encoding='utf-8') as f:
            f.write(template)
        print(f"✓ Template gespeichert: {template_file}")
    
    # 4. Liste Excel-Dateien
    print("\n4. Verfügbare Matching-Ergebnisse:\n")
    excel_files = list_excel_files()
    
    if not excel_files:
        print("✗ Keine Excel-Dateien gefunden")
        return
    
    for i, file in enumerate(excel_files[:10], 1):
        print(f"   {i}. {file}")
    
    try:
        choice = int(input("\nWelche Datei verwenden? (Nummer): "))
        if choice < 1 or choice > len(excel_files):
            print("✗ Ungültige Auswahl")
            return
        selected_file = excel_files[choice - 1]
    except ValueError:
        print("✗ Ungültige Eingabe")
        return
    
    filepath = os.path.join(RESULTS_DIR, selected_file)
    
    # 5. Lade Matching-Daten
    print("\n5. Lade Matching-Daten...\n")
    df_matching, df_job = load_matching_data(filepath)
    
    if df_matching is None or df_job is None:
        return
    
    job_data = df_job.iloc[0].to_dict()
    job_id = job_data.get('id', 'unknown')
    
    print(f"✓ {len(df_matching)} Kandidaten geladen")
    print(f"✓ Job-ID: {job_id}")
    print(f"  Position: {job_data.get('position', 'N/A')} {job_data.get('department', '')}")
    print(f"  Ort: {job_data.get('ort', 'N/A')}")
    
    # 6. Generiere E-Mails mit Template
    print(f"\n6. Generiere personalisierte E-Mails aus Template...\n")
    
    emails = []
    
    for idx, row in df_matching.iterrows():
        candidate_data = row.to_dict()
        
        print(f"   [{idx+1}/{len(df_matching)}] {candidate_data.get('first_name', '')} {candidate_data.get('last_name', '')}...", end='')
        
        # Fülle Template mit Kandidaten-Daten
        personalized_email = fill_template_with_data(
            template, 
            candidate_data, 
            job_data
        )
        
        if personalized_email:
            betreff = extract_subject_from_email(personalized_email)
            
            emails.append({
                'name': f"{candidate_data.get('first_name', '')} {candidate_data.get('last_name', '')}",
                'candidate_id': candidate_data.get('id', 'N/A'),
                'email': candidate_data.get('e_mail', 'N/A'),
                'betreff': betreff,
                'mail': personalized_email,
                'template_used': 'Generated from real emails'
            })
            
            print(" ✓")
        else:
            print(" ✗")
    
    if not emails:
        print("\n✗ Keine E-Mails generiert")
        return
    
    # 7. Speichere E-Mails
    print(f"\n7. Speichere {len(emails)} E-Mails...\n")
    
    output_folder, saved_files = save_personalized_emails(emails, job_id)
    
    print(f"✓ E-Mails gespeichert in: {output_folder}")
    
    # 7. Zeige Beispiel
    if emails:
        print("\n" + "=" * 80)
        print("BEISPIEL E-MAIL (1. Kandidat)")
        print("=" * 80)
        print(f"\nKandidat: {emails[0]['name']}")
        print(f"Vorlage: {emails[0]['template_used']}")
        print(f"Betreff: {emails[0]['betreff']}\n")
        print(emails[0]['mail'][:500] + "..." if len(emails[0]['mail']) > 500 else emails[0]['mail'])
        print("\n" + "=" * 80)
    
    print(f"\n✓ Fertig! {len(emails)} personalisierte E-Mails erstellt")


if __name__ == "__main__":
    main()
