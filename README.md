# KI-unterstütztes Bewerbermanagementsystem (BMS)

## Projektübersicht

Dieses Repository enthält ein modulares System zur intelligenten Verarbeitung, Analyse und Verwaltung von Bewerberdaten mittels künstlicher Intelligenz. Die Lösung kombiniert moderne NLP-Technologien (Natural Language Processing), Vektor-Embeddings und Large Language Models (LLMs) mit einer leistungsfähigen PostgreSQL-Datenbank inkl. pgvector-Erweiterung. Das Projekt richtet sich an Recruiter, Personalverantwortliche und Entwickler aus den Bereichen HR-Tech, maschinelles Lernen und intelligente Datenverarbeitung.

---

## Hauptfunktionen

- **Intelligente Bewerberdatenverarbeitung:**  
  Automatisches Extrahieren von Qualifikationen, Skills und Erfahrungen aus Lebensläufen (PDFs) mittels LLM-gestützter Analyse.

- **Skill-Matching mit ESCO-Datenbank:**  
  Semantischer Abgleich von Bewerber-Skills mit der europäischen ESCO-Klassifikation (European Skills, Competences, Qualifications and Occupations) zur standardisierten Kompetenzerfassung.

- **Vektor-basierte Ähnlichkeitssuche:**  
  Nutzung von Sentence Embeddings und pgvector für semantische Suche nach passenden Kandidaten basierend auf Stellenanforderungen.

- **LLM-Integration:**  
  Anbindung lokaler LLMs (via Ollama) für natürlichsprachliche Datenbankabfragen und intelligente Kandidatenempfehlungen.

- **Docker-basierte Infrastruktur:**  
  Vollständig containerisiertes Setup mit PostgreSQL (pgvector) und pgAdmin4 für einfaches Deployment und Wartung.

---

## Projektstruktur

```plaintext
KI-unterstuetztes-BMS/
├── data/                               # Rohdaten und aufbereitete Datensätze
│   ├── Staedte_Deutschland.csv         # Deutsche Städte für Ortsabgleich
│   ├── db/                             # Datenbank-Exports
│   │   ├── leaddelta/                  # Lead-Daten
│   │   └── miniCRM/                    # CRM-Exporte
│   └── skills_de/                      # ESCO-Datenbank (deutsch)
│       ├── broaderRelationsOccPillar_de.csv
│       ├── broaderRelationsSkillPillar_de.csv
│       ├── digCompSkillsCollection_de.csv
│       ├── digitalSkillsCollection_de.csv
│       ├── greenSkillsCollection_de.csv
│       ├── ISCOGroups_de.csv
│       ├── languageSkillsCollection_de.csv
│       ├── occupations_de.csv
│       ├── occupationSkillRelations_de.csv
│       ├── researchOccupationsCollection_de.csv
│       ├── researchSkillsCollection_de.csv
│       ├── skillGroups_de.csv
│       ├── skills_de.csv
│       ├── skillsHierarchy_de.csv
│       ├── skillSkillRelations_de.csv
│       └── transversalSkillsCollection_de.csv
│
├── init-scripts/                       # PostgreSQL Initialisierungsskripte
│   ├── 01-init-pgvector.sql           # pgvector Extension Setup
│   └── README-Setup.md                 # Setup-Dokumentation
│
├── models/                             # KI-Modelle und Kernlogik
│   ├── Datenbank_LLM_Abfrage.py       # LLM-gestützte Datenbankabfragen
│   ├── load_medical_professions.py     # Laden medizinischer Berufe
│   ├── search_medical_professions.py   # Suche nach medizinischen Fachkräften
│   ├── skill_matching.py              # Skill-Matching mit ESCO
│   ├── skills_de.csv                  # ESCO Skills (kompakt)
│   └── extract_skills/                # CV-Analyse Module
│       ├── read_cv_llm.py             # LLM-basierte CV-Extraktion
│       └── read_cv_skills_cos_indx.py # Cosinus-Ähnlichkeit für Skills
│
├── pgvector/                           # pgvector Demonstrations-Dateien
│
├── results/                            # Evaluierungsergebnisse und Logs
│
├── src/                                # Hauptmodule und Kernlogik
│   ├── gui/                            # Grafische Benutzeroberfläche
│   │
│   ├── helpers/                        # Hilfsfunktionen und Utilities
│   │   ├── create_sample_parquet.py   # Parquet-Testdaten erstellen
│   │   └── ollama_test.py             # Ollama-Verbindungstest
│   │
│   ├── nlp/                            # NLP-Processing Module
│   │
│   ├── PostreSQL/                      # Datenbank-Operationen
│   │   ├── DB_LLM_abfrage.py          # LLM-Datenbankintegration
│   │   ├── intelligente_Suchabfrage.py # Intelligente Kandidatensuche
│   │   │
│   │   ├── Aufbau/                     # Datenbank-Schema-Management
│   │   │   ├── check_and_fix_constraints.py # Constraint-Validierung
│   │   │   ├── new_table_candidates.py      # Kandidaten-Tabelle
│   │   │   ├── new_table_jobs.py            # Jobs-Tabelle
│   │   │   ├── new_table.py                 # Generisches Tabellen-Setup
│   │   │   ├── test_pgvector.py             # pgvector Funktionstests
│   │   │   └── update_short_note_length.py  # Schema-Updates
│   │   │
│   │   └── import/                     # Datenimport-Skripte
│   │       ├── miniCRM_import.py       # CRM-Datenimport
│   │       └── wunscharbeitsort.py     # Wunscharbeitsort-Verarbeitung
│   │
│   └── vector/                         # Vektor-Embeddings
│       └── embedding.py                # Embedding-Generierung
│
├── check_mapping.py                    # Mapping-Validierung
├── docker-compose.yml                  # Docker Service Definition
├── DOCKER-SETUP.md                     # Docker Setup-Anleitung
├── docker-start.bat                    # Windows: Container starten
├── docker-stop.bat                     # Windows: Container stoppen
├── install_pgvector.bat                # pgvector Installation (Windows)
├── pgvector-demo.sql                   # pgvector Beispielabfragen
├── README.md                           # Dieses Dokument
└── requirements.txt                    # Python-Abhängigkeiten
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
ollama pull llama2
ollama pull phi3:mini
```

---

## Zugriff auf die Dienste

### PostgreSQL-Datenbank
- **Host:** localhost
- **Port:** 5432
- **Datenbank:** postgres
- **Benutzer:** postgres
- **Passwort:** bigdataconsulting

### pgAdmin4 (Web-Interface)
- **URL:** http://localhost:5050
- **Email:** admin@admin.com
- **Passwort:** admin

### Ollama (LLM-API)
- **URL:** http://localhost:11434

---

## Nutzung

### Skill-Matching durchführen

Analysiert Bewerber-Skills und gleicht sie mit der ESCO-Datenbank ab:

```bash
python models/skill_matching.py
```

### Lebenslauf mit LLM analysieren

Extrahiert strukturierte Informationen aus PDF-Lebensläufen:

```bash
python models/extract_skills/read_cv_llm.py
```

### Intelligente Kandidatensuche

Führt semantische Suche nach passenden Kandidaten durch:

```bash
python src/PostreSQL/intelligente_Suchabfrage.py
```

### LLM-Datenbankabfrage

Natürlichsprachliche Abfragen auf der Bewerberdatenbank:

```bash
python models/Datenbank_LLM_Abfrage.py
```

### pgvector-Funktionalität testen

```bash
python src/PostreSQL/Aufbau/test_pgvector.py
```

---

## Datenbank-Setup

### Tabellen initialisieren

```bash
# Kandidaten-Tabelle
python src/PostreSQL/Aufbau/new_table_candidates.py

# Jobs-Tabelle
python src/PostreSQL/Aufbau/new_table_jobs.py
```

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

- **Datenbank:** PostgreSQL 18 mit pgvector-Extension
- **Embeddings:** sentence-transformers (all-mpnet-base-v2)
- **LLM:** Ollama (llama2, phi3:mini)
- **NLP:** NLTK, scikit-learn
- **PDF-Processing:** pdfplumber, PyPDF2, pytesseract
- **Container:** Docker, Docker Compose
- **Python:** pandas, numpy, requests

---

## ESCO-Datenbank

Das System nutzt die [ESCO-Klassifikation](https://esco.ec.europa.eu/) (European Skills, Competences, Qualifications and Occupations) für standardisierte Skill-Erfassung. Die deutschen ESCO-Daten befinden sich im Verzeichnis `data/skills_de/`.

### Enthaltene ESCO-Datasets:
- Skills und Skill-Hierarchien
- Berufsgruppen (ISCO)
- Skill-Beruf-Relationen
- Spezialisierte Collections (Digital, Green, Transversal Skills)

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

### pgvector nicht verfügbar
```bash
# Extension manuell aktivieren
docker exec -it postgres_pgvector psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Ollama nicht erreichbar
```bash
# Ollama-Status prüfen
ollama list

# Service neu starten
# Windows: Ollama aus Taskleiste neu starten
```

---

## Lizenz

Dieses Projekt wurde im Rahmen eines Big Data Consulting-Projekts entwickelt.

---

## Kontakt

Bei Fragen oder Anregungen wenden Sie sich bitte an:
- **Repository:** [github.com/strausssimon/KI-unterstuetztes-BMS](https://github.com/strausssimon/KI-unterstuetztes-BMS)

