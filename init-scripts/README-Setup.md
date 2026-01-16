# Installation:  Docker, PostgreSQL, pgvector & pgAdmin4

Schritt-für-Schritt Anleitung zur Einrichtung der Datenbankinfrastruktur für das KI-unterstützte BMS.

---

## Übersicht

Diese Anleitung beschreibt die Installation von:
- **Docker Desktop** (Container-Plattform)
- **PostgreSQL 18** (Datenbank)
- **pgvector 0.8.1+** (Vektorsuche-Extension)
- **pgAdmin 4** (Datenbank-Verwaltung)

**Geschätzte Zeit:** 15-30 Minuten

---

## Voraussetzungen

- **Windows 10/11 (64-bit)**
- **Virtualisierung aktiviert** (Intel VT-x oder AMD-V)
- **8 GB RAM** (empfohlen:  16 GB)
- **Administrator-Rechte**
- **Internetverbindung**

---

## 1. Docker Desktop installieren

### Schritt 1.1: Docker Desktop herunterladen und installieren

```powershell
# PowerShell als Administrator öffnen

# Docker Desktop installieren
winget install Docker.DockerDesktop
```

**Alternativ:** Manueller Download von https://www.docker.com/products/docker-desktop/

### Schritt 1.2: WSL 2 installieren (Windows-Subsystem für Linux)

```powershell
# WSL mit einem Befehl installieren
wsl --install

# PC neu starten (erforderlich)
Restart-Computer
```

### Schritt 1.3: Nach Neustart - WSL 2 konfigurieren

```powershell
# PowerShell als Administrator öffnen

# WSL 2 als Standard-Version setzen
wsl --set-default-version 2

# Installation prüfen
wsl --status
```

**Erwartete Ausgabe:**
```
Standardversion:  2
```

### Schritt 1.4: Virtualisierung prüfen (falls Probleme)

```powershell
# Virtualisierungs-Status prüfen
systeminfo | findstr /C:"Virtualization"
```

**Sollte zeigen:**
```
Virtualisierung in Firmware aktiviert:  Ja
```

**Falls "Nein":**
1. PC neu starten
2. BIOS/UEFI aufrufen (F2, F10, F12 oder DEL beim Start)
3. **Intel:** `Intel VT-x` oder `Virtualization Technology` aktivieren
4. **AMD:** `AMD-V` oder `SVM Mode` aktivieren
5. Speichern & Neustart

### Schritt 1.5: Docker Desktop starten

1. **Windows-Taste** drücken
2. `Docker Desktop` suchen und öffnen
3. **Warten** bis unten links **"Engine running"** angezeigt wird (ca. 30 Sekunden)
4. Bei erster Nutzung: Tutorial überspringen

### Schritt 1.6: Docker testen

```powershell
# Neue PowerShell öffnen (wichtig für PATH-Aktualisierung)

# Docker-Version prüfen
docker --version

# Test-Container starten
docker run hello-world
```

**Erwartete Ausgabe:**
```
Hello from Docker!
This message shows that your installation appears to be working correctly. 
```

---

## 2. PostgreSQL 18 mit pgvector installieren

### Option A: Docker Container (Empfohlen)

#### Schritt 2.1: Container starten

```powershell
# PostgreSQL 18 mit pgvector als Container starten
docker run -d `
  --name postgres-pgvector `
  --restart unless-stopped `
  -e POSTGRES_PASSWORD=IhrPasswort `
  -e POSTGRES_DB=postgres `
  -e POSTGRES_USER=postgres `
  -p 5432:5432 `
  -v pgvector-data:/var/lib/postgresql/data `
  pgvector/pgvector:pg18
```

**Parameter-Erklärung:**
- `-d`: Im Hintergrund ausführen
- `--name`: Container-Name für einfache Verwaltung
- `--restart unless-stopped`: Automatischer Start nach PC-Neustart
- `-e POSTGRES_PASSWORD`: Datenbank-Passwort setzen
- `-e POSTGRES_DB`: Standard-Datenbank-Name
- `-p 5432:5432`: Port-Mapping (Host:Container)
- `-v pgvector-data`: Persistenter Speicher für Daten
- `pgvector/pgvector:pg18`: Docker-Image mit PostgreSQL 18 + pgvector

#### Schritt 2.2: Container-Status prüfen

```powershell
# Laufende Container anzeigen
docker ps

# Logs ansehen
docker logs postgres-pgvector

# In Container einloggen (optional)
docker exec -it postgres-pgvector psql -U postgres
```

**Erwartete Ausgabe von `docker ps`:**
```
CONTAINER ID   IMAGE                    STATUS         PORTS
               pgvector/pgvector:pg18   Up 20 seconds  0.0.0.0:5432->5432/tcp
```

#### Schritt 2.3: pgvector Extension aktivieren

```powershell
# Extension in Datenbank erstellen
docker exec postgres-pgvector psql -U postgres -d postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Prüfen ob Extension installiert ist
docker exec postgres-pgvector psql -U postgres -d postgres -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
```

**Erwartete Ausgabe:**
```
 extname | extversion 
---------+------------
 vector  | 0.8.1
(1 row)
```

#### Schritt 2.4: Vektorsuche testen

```powershell
# Test-Vektor erstellen
docker exec postgres-pgvector psql -U postgres -d postgres -c "SELECT '[1,2,3]'::vector;"

# Test-Tabelle mit Vektoren erstellen
docker exec postgres-pgvector psql -U postgres -d postgres -c "
CREATE TABLE test_vectors (
    id SERIAL PRIMARY KEY,
    embedding vector(3)
);

INSERT INTO test_vectors (embedding) VALUES 
('[1,2,3]'),
('[4,5,6]'),
('[7,8,9]');

SELECT * FROM test_vectors;
"
```

---

### Option B: Lokale Installation (ohne Docker)

#### Schritt 2.1: PostgreSQL 18 installieren

```powershell
# PostgreSQL 18 installieren
winget install PostgreSQL.PostgreSQL. 18
```

**Während der Installation:**
- **Passwort:** Sicheres Passwort festlegen und merken
- **Port:** `5432` (Standard)
- **Locale:** `German, Germany` oder `Default locale`

#### Schritt 2.2: pgvector Binary herunterladen

1.  Gehe zu:  https://github.com/pgvector/pgvector/releases/latest
2. Download:  `pgvector-X.X.X-windows-x64-pg18.zip`
3. Entpacken nach:  `C:\Downloads\pgvector\`

#### Schritt 2.3: pgvector installieren

```powershell
# PowerShell als Administrator öffnen

# Pfade definieren (anpassen falls nötig)
$pgvectorPath = "C:\Downloads\pgvector"
$pgPath = "C:\Program Files\PostgreSQL\18"

# Prüfen ob Pfade existieren
Test-Path $pgvectorPath
Test-Path $pgPath

# DLL-Datei kopieren
Copy-Item "$pgvectorPath\vector.dll" "$pgPath\lib\" -Force

# Extension-Dateien kopieren
Copy-Item "$pgvectorPath\vector.control" "$pgPath\share\extension\" -Force
Copy-Item "$pgvectorPath\vector--*.sql" "$pgPath\share\extension\" -Force

# Installation prüfen
Test-Path "$pgPath\lib\vector.dll"
Test-Path "$pgPath\share\extension\vector.control"
```

**Erwartete Ausgabe:**
```
True
True
```

```powershell
# PostgreSQL Service neu starten
Restart-Service postgresql-x64-18

# Service-Status prüfen
Get-Service postgresql-x64-18
```

#### Schritt 2.4: Extension aktivieren

```powershell
# PostgreSQL-Shell öffnen
psql -U postgres

# In psql: 
CREATE EXTENSION IF NOT EXISTS vector;

-- Prüfen
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';

-- Beenden
\q
```

---

## 3. pgAdmin 4 installieren

### Option A: Docker Container

```powershell
# pgAdmin 4 als Container starten
docker run -d `
  --name pgadmin `
  --restart unless-stopped `
  -e PGADMIN_DEFAULT_EMAIL=admin@example.com `
  -e PGADMIN_DEFAULT_PASSWORD=IhrPasswort `
  -p 8080:80 `
  -v pgadmin-data:/var/lib/pgadmin `
  dpage/pgadmin4:latest

# Status prüfen
docker ps | findstr pgadmin
```

**Zugriff:** http://localhost:8080

**Login-Daten:**
- **Email:** Wie bei `-e PGADMIN_DEFAULT_EMAIL` gesetzt
- **Passwort:** Wie bei `-e PGADMIN_DEFAULT_PASSWORD` gesetzt

---

### Option B: Desktop-Installation

```powershell
# pgAdmin 4 installieren
winget install PostgreSQL.pgAdmin
```

**Alternativ:** Manueller Download von https://www.pgadmin.org/download/

---

## 4. pgAdmin 4 konfigurieren

### Schritt 4.1: pgAdmin öffnen

- **Docker-Version:** Browser öffnen und http://localhost:8080 aufrufen
- **Desktop-Version:** pgAdmin 4 aus Startmenü öffnen

### Schritt 4.2: Master-Passwort setzen (nur Desktop)

Beim ersten Start wird nach einem Master-Passwort gefragt.  Dieses merken. 

### Schritt 4.3: Server-Verbindung erstellen

1. **Rechtsklick auf "Servers"** (linke Sidebar)
2. **"Register" → "Server..."**

**Tab "General":**
- **Name:** `PostgreSQL-Docker` (oder `PostgreSQL-Lokal`)

**Tab "Connection":**

**Für Docker-Installation:**
- **Host:** `host.docker.internal`
- **Port:** `5432`
- **Maintenance database:** `postgres`
- **Username:** `postgres`
- **Password:** Das gesetzte POSTGRES_PASSWORD
- **"Save password"** aktivieren

**Für lokale Installation:**
- **Host:** `localhost`
- **Port:** `5432`
- **Maintenance database:** `postgres`
- **Username:** `postgres`
- **Password:** Das bei Installation gesetzte Passwort
- **"Save password"** aktivieren

3. **"Save"** klicken

### Schritt 4.4: Verbindung testen

1. **Server erweitern** (Klick auf Pfeil)
2. **Databases erweitern**
3. **postgres erweitern**
4. **Extensions** prüfen - sollte `vector` enthalten

### Schritt 4.5: Query Tool nutzen

1. **Rechtsklick auf Datenbank "postgres"**
2. **"Query Tool"** wählen
3. **Test-Query ausführen:**

```sql
-- pgvector testen
SELECT '[1,2,3]':: vector;

-- Vektor-Ähnlichkeit berechnen (Cosine Distance)
SELECT 
    '[1,2,3]':: vector <=> '[4,5,6]'::vector AS cosine_distance,
    '[1,2,3]'::vector <-> '[4,5,6]'::vector AS l2_distance,
    '[1,2,3]'::vector <#> '[4,5,6]'::vector AS inner_product;
```

**Erwartetes Ergebnis:**
```
 cosine_distance | l2_distance | inner_product 
-----------------+-------------+---------------
      0.02536     |    5.196     |        -32.0
```

---

## 5. Container-Verwaltung (Docker)

### Nützliche Befehle

```powershell
# Alle Container anzeigen
docker ps -a

# Container starten
docker start postgres-pgvector
docker start pgadmin

# Container stoppen
docker stop postgres-pgvector
docker stop pgadmin

# Container neu starten
docker restart postgres-pgvector

# Container-Logs ansehen
docker logs postgres-pgvector
docker logs -f postgres-pgvector  # Live-Logs

# In Container einloggen
docker exec -it postgres-pgvector bash

# PostgreSQL-Shell im Container
docker exec -it postgres-pgvector psql -U postgres

# Container löschen (Daten bleiben in Volume)
docker rm postgres-pgvector

# Volume (Daten) löschen (ACHTUNG: Datenverlust)
docker volume rm pgvector-data
docker volume rm pgadmin-data

# Alle Volumes anzeigen
docker volume ls
```

### Backup erstellen

```powershell
# Datenbank-Backup
docker exec postgres-pgvector pg_dump -U postgres postgres > backup_$(Get-Date -Format "yyyy-MM-dd").sql

# Backup wiederherstellen
Get-Content backup_2026-01-09.sql | docker exec -i postgres-pgvector psql -U postgres postgres
```

### Container-Logs überwachen

```powershell
# Letzte 100 Zeilen
docker logs --tail 100 postgres-pgvector

# Live-Logs (Ctrl+C zum Beenden)
docker logs -f postgres-pgvector
```

---

## 6. Fehlerbehebung

### Problem:  Docker startet nicht

**Fehler:** `Virtualization support not detected`

**Lösung:**
1. Virtualisierung im BIOS aktivieren (siehe Schritt 1.4)
2. WSL 2 installieren:  `wsl --install`
3. PC neu starten

---

### Problem: Port 5432 bereits belegt

**Fehler:** `Bind for 0.0.0.0:5432 failed: port is already allocated`

**Lösung 1: Anderen Port verwenden**
```powershell
docker run -d --name postgres-pgvector -p 5433:5432 ...  pgvector/pgvector:pg18

# Dann in Anwendungen Port 5433 verwenden
```

**Lösung 2: Lokales PostgreSQL stoppen**
```powershell
Stop-Service postgresql-x64-18
```

---

### Problem: pgvector Extension nicht gefunden

**Fehler:** `extension "vector" is not available`

**Docker:**
```powershell
# Image-Name prüfen (muss pgvector/pgvector sein, nicht postgres)
docker inspect postgres-pgvector | findstr Image

# Container mit korrektem Image neu erstellen
docker rm -f postgres-pgvector
docker run -d --name postgres-pgvector ...  pgvector/pgvector: pg18
```

**Lokal:**
```powershell
# Dateien prüfen
Test-Path "C:\Program Files\PostgreSQL\18\lib\vector.dll"
Test-Path "C:\Program Files\PostgreSQL\18\share\extension\vector.control"

# Service neu starten
Restart-Service postgresql-x64-18
```

---

### Problem: pgAdmin kann nicht auf PostgreSQL zugreifen

**Fehler:** `could not connect to server`

**Docker zu Docker (beide Container):**
```
Host: host.docker.internal
```

**Desktop zu Docker:**
```
Host: localhost
Port: 5432
```

**Desktop zu Lokal:**
```
Host: localhost
Port: 5432
```

---

### Problem: Container startet nach PC-Neustart nicht

**Lösung:**
```powershell
# Auto-Start aktivieren (bei Container-Erstellung)
docker run -d --restart unless-stopped ... 

# Bei bestehendem Container ändern
docker update --restart unless-stopped postgres-pgvector
docker update --restart unless-stopped pgadmin
```

---

## 7. Verbindungsdaten für Anwendungen

### Python (psycopg)

```python
import psycopg
from pgvector.psycopg import register_vector

# Docker-Installation
conn = psycopg.connect(
    host="localhost",
    port=5432,
    dbname="postgres",
    user="postgres",
    password="IhrPasswort"
)

register_vector(conn)
```

### Connection String

```
postgresql://postgres:IhrPasswort@localhost:5432/postgres
```

### pgAdmin 4

```
Host: localhost (Desktop) oder host.docker.internal (Docker)
Port: 5432
Database: postgres
Username: postgres
Password: Das gesetzte Passwort
```

---

## 8. Nächste Schritte

Nach erfolgreicher Installation:

1. Datenbank-Schema erstellen
2. Python-Dependencies installieren
3. Berufssynonyme importieren
4. Erste Suche durchführen

---

## Referenzen

- **Docker Dokumentation:** https://docs.docker.com/
- **PostgreSQL 18 Docs:** https://www.postgresql.org/docs/18/
- **pgvector GitHub:** https://github.com/pgvector/pgvector
- **pgAdmin Dokumentation:** https://www.pgadmin.org/docs/

---

**Bei Problemen:** Siehe Abschnitt Fehlerbehebung oder erstelle ein Issue im Repository. 