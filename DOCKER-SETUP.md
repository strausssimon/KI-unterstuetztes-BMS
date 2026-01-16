# PostgreSQL mit pgvector und pgAdmin4 - Docker Setup

## Voraussetzungen

- **Docker Desktop** muss installiert und gestartet sein
- [Docker Desktop für Windows herunterladen](https://www.docker.com/products/docker-desktop/)

## Schnellstart

### 1. Container starten

**Option A: Batch-Script (einfachste Methode)**
```cmd
docker-start.bat
```

**Option B: Manuell mit Docker Compose**
```cmd
docker-compose up -d
```

### 2. Container-Status prüfen

```cmd
docker-compose ps
```

Erwartete Ausgabe:
```
NAME                IMAGE                              STATUS
postgres_pgvector   pgvector/pgvector:pg18-bookworm   Up
pgadmin4            dpage/pgadmin4:latest              Up
```

### 3. Logs anzeigen

```cmd
# Alle Logs
docker-compose logs -f

# Nur PostgreSQL
docker-compose logs -f postgres

# Nur pgAdmin
docker-compose logs -f pgadmin
```

## Zugriff

### PostgreSQL-Datenbank

- **Host:** `localhost`
- **Port:** `5432`
- **Datenbank:** `postgres`
- **Benutzer:** `postgres`
- **Passwort:** `bigdataconsulting`

**Verbindungstest mit psql (im Container):**
```cmd
docker exec -it postgres_pgvector psql -U postgres
```

**pgvector-Version prüfen:**
```cmd
docker exec postgres_pgvector psql -U postgres -c "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
```

### pgAdmin4

1. Öffne Browser: **http://localhost:5050**
2. Login:
   - **Email:** `admin@admin.com`
   - **Passwort:** `admin`

#### PostgreSQL-Server in pgAdmin hinzufügen:

1. Klicke auf "Add New Server"
2. **General Tab:**
   - Name: `PostgreSQL Docker`
3. **Connection Tab:**
   - Host: `postgres` (Container-Name!)
   - Port: `5432`
   - Maintenance database: `postgres`
   - Username: `postgres`
   - Password: `bigdataconsulting`
   - Save password: ✓
4. Klicke "Save"

## Python-Scripts verwenden

Die bestehenden Python-Scripts funktionieren ohne Änderungen:

```python
# Connection-Parameter (bereits in new_table.py und test_pgvector.py)
conn_params = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'postgres',
    'user': 'postgres',
    'password': 'bigdataconsulting'
}
```

**Test ausführen:**
```cmd
python "src\db communication\test_pgvector.py"
```

## pgvector Funktionalität testen

**In pgAdmin Query Tool oder psql:**

```sql
-- Extension prüfen
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Test-Tabelle erstellen
CREATE TABLE items (
    id bigserial PRIMARY KEY, 
    name text,
    embedding vector(3)
);

-- Daten einfügen
INSERT INTO items (name, embedding) VALUES 
    ('Item A', '[1,2,3]'),
    ('Item B', '[4,5,6]'),
    ('Item C', '[7,8,9]');

-- Nearest Neighbor Suche (L2-Distanz)
SELECT name, embedding, embedding <-> '[3,1,2]' AS distance
FROM items
ORDER BY embedding <-> '[3,1,2]'
LIMIT 3;

-- Cosine Similarity
SELECT name, embedding, 1 - (embedding <=> '[3,1,2]') AS similarity
FROM items
ORDER BY embedding <=> '[3,1,2]'
LIMIT 3;
```

## Container verwalten

### Container stoppen

```cmd
docker-compose stop
```
oder
```cmd
docker-stop.bat
```

### Container neu starten

```cmd
docker-compose start
```

### Container entfernen (Daten bleiben erhalten)

```cmd
docker-compose down
```

### Container UND Daten entfernen

```cmd
docker-compose down -v
```

**⚠️ WARNUNG:** Dies löscht alle Datenbank-Daten!

### Logs in Echtzeit verfolgen

```cmd
docker-compose logs -f
```

### Container-Shell öffnen

```cmd
# PostgreSQL Container
docker exec -it postgres_pgvector bash

# pgAdmin Container
docker exec -it pgadmin4 sh
```

## Problemlösung

### Docker läuft nicht
```
FEHLER: Docker ist nicht gestartet!
```
→ Starte Docker Desktop

### Port bereits belegt (5432 oder 5050)
```
Error: bind: address already in use
```

**Lösung 1:** Stoppe andere PostgreSQL-Instanz
- Öffne Services (Win+R → `services.msc`)
- Stoppe "PostgreSQL" Service

**Lösung 2:** Ändere Port in `docker-compose.yml`
```yaml
ports:
  - "5433:5432"  # Statt 5432:5432
```

### pgAdmin kann nicht auf Postgres zugreifen
- Verwende `postgres` als Host (nicht `localhost`)
- Stelle sicher beide Container im gleichen Netzwerk sind: `docker-compose ps`

### pgvector Extension fehlt
```sql
-- Manuell aktivieren
CREATE EXTENSION vector;
```

## Daten sichern

### Backup erstellen

```cmd
docker exec postgres_pgvector pg_dump -U postgres postgres > backup.sql
```

### Backup wiederherstellen

```cmd
docker exec -i postgres_pgvector psql -U postgres postgres < backup.sql
```

## Upgrade/Neustart

```cmd
# Container und Images aktualisieren
docker-compose pull
docker-compose up -d
```

## Nützliche Docker-Befehle

```cmd
# Container-Status
docker-compose ps

# Ressourcen-Nutzung
docker stats

# Container neu bauen
docker-compose up -d --build

# Einzelnen Container neu starten
docker-compose restart postgres
docker-compose restart pgadmin

# Container-Logs begrenzen (letzte 100 Zeilen)
docker-compose logs --tail=100

# Netzwerk-Info
docker network inspect ki-unterstuetztes-bms_pgnetwork
```

## Production-Tipps

Für Produktionsumgebungen:

1. **Passwörter ändern** in `docker-compose.yml`
2. **Volume-Backups** einrichten
3. **Ressourcen-Limits** setzen:
   ```yaml
   postgres:
     deploy:
       resources:
         limits:
           cpus: '2'
           memory: 4G
   ```
4. **Health Checks** überwachen
5. **SSL-Verbindungen** aktivieren

## Weitere Ressourcen

- [pgvector Dokumentation](https://github.com/pgvector/pgvector)
- [PostgreSQL Docker Hub](https://hub.docker.com/_/postgres)
- [pgAdmin Docker Hub](https://hub.docker.com/r/dpage/pgadmin4)
- [Docker Compose Dokumentation](https://docs.docker.com/compose/)
