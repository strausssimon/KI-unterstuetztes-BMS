-- ==================================================
-- pgvector Demo & Test für pgAdmin4
-- ==================================================

-- 1. Prüfe pgvector Extension
SELECT 
    extname AS "Extension Name",
    extversion AS "Version"
FROM pg_extension 
WHERE extname = 'vector';

-- 2. Prüfe vorhandene Tabellen
SELECT 
    schemaname,
    tablename
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;

-- ==================================================
-- Demo: Skills mit Vektoren
-- ==================================================

-- 3. Erstelle eine Tabelle für Skills mit Embeddings
DROP TABLE IF EXISTS skills_embeddings CASCADE;

CREATE TABLE skills_embeddings (
    id SERIAL PRIMARY KEY,
    skill_name VARCHAR(200) NOT NULL,
    description TEXT,
    embedding vector(384),  -- 384 Dimensionen für sentence-transformers
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Füge Beispiel-Skills ein (mit Dummy-Vektoren)
INSERT INTO skills_embeddings (skill_name, description, embedding) VALUES
    ('Python Programming', 'Erfahrung mit Python-Entwicklung', 
     array_fill(random(), ARRAY[384])::vector(384)),
    ('Machine Learning', 'Kenntnisse in ML-Algorithmen', 
     array_fill(random(), ARRAY[384])::vector(384)),
    ('Data Analysis', 'Datenanalyse mit pandas und numpy', 
     array_fill(random(), ARRAY[384])::vector(384)),
    ('SQL Databases', 'PostgreSQL und MySQL Kenntnisse', 
     array_fill(random(), ARRAY[384])::vector(384)),
    ('Web Development', 'HTML, CSS, JavaScript, React', 
     array_fill(random(), ARRAY[384])::vector(384));

-- 5. Zeige die Skills an (ohne Embedding-Daten)
SELECT 
    id,
    skill_name,
    description,
    created_at,
    vector_dims(embedding) as embedding_dimensions
FROM skills_embeddings
ORDER BY id;

-- ==================================================
-- Demo: Bewerber-Tabelle erweitern
-- ==================================================

-- 6. Erweitere bestehende Bewerber-Tabelle mit Skills-Embedding
-- (falls sie noch nicht existiert, wird sie erstellt)
CREATE TABLE IF NOT EXISTS bewerber (
    id SERIAL PRIMARY KEY,
    nachname VARCHAR(100) NOT NULL,
    vorname VARCHAR(100) NOT NULL,
    beruf VARCHAR(200),
    adresse TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Füge Skills-Embedding Spalte hinzu (falls noch nicht vorhanden)
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'bewerber' AND column_name = 'skills_embedding'
    ) THEN
        ALTER TABLE bewerber ADD COLUMN skills_embedding vector(384);
    END IF;
END $$;

-- 7. Zeige Bewerber-Struktur
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'bewerber'
ORDER BY ordinal_position;

-- ==================================================
-- Vector Similarity Search Demo
-- ==================================================

-- 8. Erstelle Test-Tabelle für Vector Search
DROP TABLE IF EXISTS vector_search_demo CASCADE;

CREATE TABLE vector_search_demo (
    id SERIAL PRIMARY KEY,
    item_name VARCHAR(100),
    embedding vector(3)  -- 3D für einfache Demo
);

-- 9. Füge Test-Vektoren ein
INSERT INTO vector_search_demo (item_name, embedding) VALUES
    ('Item A', '[1.0, 2.0, 3.0]'),
    ('Item B', '[4.0, 5.0, 6.0]'),
    ('Item C', '[7.0, 8.0, 9.0]'),
    ('Item D', '[2.0, 3.0, 4.0]'),
    ('Item E', '[0.5, 1.5, 2.5]');

-- 10. Suche ähnlichste Vektoren (L2-Distanz)
-- Query-Vektor: [3, 1, 2]
SELECT 
    item_name,
    embedding,
    embedding <-> '[3,1,2]' AS l2_distance,
    1 - (embedding <=> '[3,1,2]') AS cosine_similarity
FROM vector_search_demo
ORDER BY embedding <-> '[3,1,2]'  -- Sortiere nach L2-Distanz
LIMIT 5;

-- ==================================================
-- Performance: Index erstellen
-- ==================================================

-- 11. Erstelle HNSW Index für schnelle Suche
-- (nur wenn viele Daten vorhanden sind)
CREATE INDEX IF NOT EXISTS skills_embeddings_idx 
ON skills_embeddings 
USING hnsw (embedding vector_cosine_ops);

-- 12. Statistiken anzeigen
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
    pg_size_pretty(pg_indexes_size(schemaname||'.'||tablename)) AS indexes_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- ==================================================
-- Aufräumen (optional)
-- ==================================================

-- Uncomment zum Löschen der Demo-Tabellen:
-- DROP TABLE IF EXISTS vector_search_demo CASCADE;
-- DROP TABLE IF EXISTS skills_embeddings CASCADE;

-- ==================================================
-- Fertig! ✓
-- ==================================================
SELECT '✓ pgvector Demo erfolgreich durchgeführt!' AS status;
