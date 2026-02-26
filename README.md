# KI-unterstütztes Bewerbermanagementsystem (BMS)

## Projektübersicht

Dieses Repository enthält ein modulares System zur intelligenten Verarbeitung, Analyse und Verwaltung von Bewerberdaten mittels künstlicher Intelligenz. Die Lösung kombiniert eine GUI mit lokalen Language Models (Ollama), PostgreSQL und regelbasierter Matching-Logik.
Das Projekt richtet sich an Recruiter und Personalverantwortliche im Gesundheitswesen.


---

## Hauptfunktionen

- **GUI (Hauptanwendung):**
  Zentrale Oberfläche zur Verwaltung von Kandidaten und Stellen, inkl. Matching,
  intelligenter Suche, LM-Datenimport und Mailgenerierung.

- **Job-Kandidaten-Matching:**
  Automatischer Abgleich von Stellen und Bewerbern anhand von Karrierepfad, Fachbereich sowie Scoring (Gehalt, Fahrtweg, Skills).

- **Intelligente Suchabfrage:**
  Natürlichsprachige Suchanfragen werden per Ollama-LLM interpretiert und in strukturierte Datenbankabfragen umgewandelt.

- **Strukturierter Datenimport (LLM):**
  Freitext (z. B. aus Mails oder CRM-Exporten) wird per Ollama zu strukturierten JSON-Objekten verarbeitet, per Pydantic validiert und in die DB importiert.

- **Skill-Extraktion:**
  Automatisches Erkennen von Skills aus Lebensläufen (PDF) und Kurznotizen, Abgleich mit einer hinterlegten Skills-Datenbank (Fuzzy-Matching).

- **Mailgenerierung:**
  Personalisierte Kandidaten-Anschreiben auf Basis von Vorlagen und DB-Daten.

- **Docker-basierte Datenbankinfrastruktur:**
  PostgreSQL mit pgvector-Extension, verwaltet über Docker Compose.

---

## Projektstruktur

```
KI-unterstuetztes-BMS/
├── data/
│   ├── skills.csv                          # Interne Skills-Referenzdatenbank
│   ├── Staedte_Deutschland.csv             # Deutsche Städte für Ortsabgleich
│   └── db/
│       ├── backup_postresql/               # CSV-Backups (Kandidaten & Jobs)
│       ├── CV/                             # Lebenslauf-PDFs
│       ├── leaddelta/                      # LeadDelta-Kontaktexporte
│       ├── mails/                          # Mail-Vorlagen
│       └── miniCRM/                        # CRM-Exportdaten
│
├── init-scripts/
│   ├── 01-init-pgvector.sql               # pgvector Extension Setup
│   └── README-Setup.md
│
├── models/
│   └── extract_skills/
│       ├── read_cv_llm.py                 # LLM-basierte CV-Analyse
│       └── read_cv_skills_cos_indx.py     # Cosinus-Ähnlichkeit für Skills
│
├── results/                               # Analyse-Ergebnisse und Reports
│
├── src/
│   ├── db_config.py                       # Zentrale DB-Verbindungskonfiguration
│   │
│   ├── GUI/                               # Hauptanwendung (Tkinter)
│   │   ├── GUI_5.py                       # Haupteinstieg: Tkinter-GUI
│   │   ├── intelligente_Suchabfrage_7.py  # NLP-Suche via Ollama
│   │   ├── Matching.py                    # Job-Kandidaten-Matching + Excel-Export
│   │   ├── Strukturierter_Datenimport_LLM.py  # Freitext → DB via Ollama & Pydantic
│   │   └── mail_candidate.py              # Mailgenerierung (GUI-Modul)
│   │
│   ├── helpers/
│   │   ├── explorative_analyse_datenquellen.py
│   │   ├── leaddelta_create_dataset.py
│   │   └── ollama_test.py                 # Ollama-Verbindungstest
│   │
│   ├── mailing/
│   │   ├── generate_personalized_mails.py
│   │   └── mail_candidate.py
│   │
│   └── PostreSQL/
│       ├── backup_candidates_to_csv.py    # Kandidaten-Backup nach CSV
│       ├── backup_jobs_to_csv.py          # Jobs-Backup nach CSV
│       │
│       ├── Aufbau/                        # Schema-Setup & Migrations-Skripte
│       │   ├── new_table_candidates.py
│       │   ├── new_table_jobs.py
│       │   ├── add_skills_column.py
│       │   ├── add_cv_pdf_column.py
│       │   ├── add_missing_columns.py
│       │   ├── add_minicrm_id_column.py
│       │   └── check_and_fix_constraints.py
│       │
│       └── import/                        # Datenimport-Skripte
│           ├── miniCRM_import_candidates.py
│           ├── miniCRM_import_jobs.py
│           ├── import_single_cv_pdf.py
│           ├── extract_skills_from_cv_pdf.py
│           ├── extract_skills_from_long_note.py
│           ├── job_skills_extraktion.py
│           ├── job_gehalt_extraktion.py
│           ├── job_ort_extraktion.py
│           ├── fill_salary.py
│           └── wunscharbeitsort.py
│
├── docker-compose.yml
├── DOCKER-SETUP.md
├── docker-start.bat                       # Windows: Container starten
├── docker-stop.bat                        # Windows: Container stoppen
├── install_pgvector.bat
├── pgvector-demo.sql
├── README.md
└── requirements.txt
```

---

## Installation

### 1. Repository klonen

```bash
git clone https://github.com/strausssimon/KI-unterstuetztes-BMS.git
cd KI-unterstuetztes-BMS
```

### 2. Docker Desktop installieren

- **Windows:** [Docker Desktop herunterladen](https://www.docker.com/products/docker-desktop/)
- Nach Installation Docker Desktop starten

### 3. Datenbank-Container starten

**Option A: Batch-Script (Windows)**
```cmd
docker-start.bat
```

**Option B: Docker Compose**
```bash
docker-compose up -d
```

**Status prüfen:**
```bash
docker-compose ps
```

### 4. Python-Umgebung einrichten

```bash
# Virtuelle Umgebung erstellen
python -m venv venv

# Aktivieren
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Abhängigkeiten installieren
pip install -r requirements.txt
```

### 5. Ollama installieren (für LLM-Funktionen)

- **Download:** [Ollama herunterladen](https://ollama.ai/)
- Modell laden:
```bash
ollama pull phi3:mini
ollama pull llama3.2:3b
ollama pull mistral:7b
```

### 6. Datenbank-Schema initialisieren

```bash
python src/PostreSQL/Aufbau/new_table_candidates.py
python src/PostreSQL/Aufbau/new_table_jobs.py
```

---

## Nutzung

### Matching (`src/GUI/Matching.py`)
Vergleicht Kandidaten mit einer Stelle anhand von:
- Karrierepfad und Fachbereich
- Gehaltswunsch vs. angebotenem Gehalt (Score)
- Fahrtweg (Wunscharbeitsort)
- Skills (Fuzzy-Matching)


### Intelligente Suchabfrage (`src/GUI/intelligente_Suchabfrage_7.py`)
Parst eine natürlichsprachige Eingabe per Ollama-LLM, extrahiert Suchintentionen
(Beruf, Ort, Verfügbarkeit etc.) und sucht passende Kandidaten in der Datenbank.

### Strukturierter Datenimport LLM (`src/GUI/Strukturierter_Datenimport_LLM.py`)
Extrahiert aus Freitext (Mail, Notiz) ein strukturiertes Kandidaten-JSON per Ollama,
validiert es mit Pydantic-Modellen und bereitet es für den DB-Import vor.

### Gehaltsdaten
- `job_gehalt_extraktion.py`: Regex-Extraktion aus Jobtexten → `gehalt_von`/`gehalt_bis` in `jobs`
- `fill_salary.py`: Schätzung aus Position/Fachbereich/Land → `gehaltswunsch` in `candidates`

---

## Daten-Backups

```bash
python src/PostreSQL/backup_candidates_to_csv.py
python src/PostreSQL/backup_jobs_to_csv.py
```

Backups werden in `data/db/backup_postresql/` gespeichert.

---

### Daten importieren

```bash
# CRM-Daten importieren
python src/PostreSQL/import/miniCRM_import.py
```

### pgvector Extension aktivieren

```bash
# Automatisch via Docker init-scripts
# Oder manuell:
psql -U postgres -d postgres -f init-scripts/01-init-pgvector.sql
```

---

## Technologie-Stack

- **GUI:** TKinter
- **Datenbank:** PostgreSQL 18 mit pgvector-Extension
- **Embeddings:** sentence-transformers (all-mpnet-base-v2)
- **LM:** Ollama (phi3:mini, llama3.2:3b, mistral:7b)
- **Datenvalidierung** Pydantic v2 
- **NLP/ Matching:** fuzzywuzzy, python-Levenshtein
- **PDF-Processing:** pdfplumber, pdf2image, PyPDF2, pytesseract
- **Container:** Docker, Docker Compose
- **Datenanalyse** pandas, numpy, scikit-learn, pyarrow

---

## Docker-Verwaltung

### Container starten
```bash
docker-compose up -d
```

### Container stoppen
```bash
docker-compose down
```

### Logs anzeigen
```bash
# Alle Dienste
docker-compose logs -f

# Nur PostgreSQL
docker-compose logs -f postgres
```

### Container neu bauen
```bash
docker-compose up -d --build
```

---

## Troubleshooting

### Port bereits belegt (5432 oder 5050)
```bash
# Prozess auf Port finden (Windows)
netstat -ano | findstr :5432
# Prozess beenden
taskkill /PID <PID> /F
```

### Ollama nicht erreichbar
```bash
# Ollama-Status prüfen
ollama list

# Service neu starten
# Windows: Ollama aus Taskleiste neu starten
```

**psycopg3 Installation schlägt fehl:**
```bash
pip install "psycopg[binary]>=3.1.0"
```

---

## Lizenz

Dieses Projekt wurde im Rahmen eines Big Data Consulting-Projekts entwickelt.

---

## Kontakt

Bei Fragen oder Anregungen wenden Sie sich bitte an:
- **Repository:** [github.com/strausssimon/KI-unterstuetztes-BMS](https://github.com/strausssimon/KI-unterstuetztes-BMS)

