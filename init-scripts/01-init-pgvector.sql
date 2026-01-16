-- Initialisierungsskript für pgvector
-- Wird beim ersten Start automatisch ausgeführt

-- pgvector Extension aktivieren
CREATE EXTENSION IF NOT EXISTS vector;

-- Bestätigung
SELECT 'pgvector Extension Version: ' || extversion 
FROM pg_extension 
WHERE extname = 'vector';

-- Beispiel: Bewerber-Tabelle erstellen (falls noch nicht vorhanden)
CREATE TABLE IF NOT EXISTS bewerber (
    id SERIAL PRIMARY KEY,
    nachname VARCHAR(100) NOT NULL,
    vorname VARCHAR(100) NOT NULL,
    beruf VARCHAR(200),
    adresse TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Info ausgeben
\echo 'pgvector erfolgreich initialisiert!'
\echo 'Die Extension ist nun verfügbar.'
