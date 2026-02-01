"""
Zentrale Datenbankverbindungskonfiguration für alle Python-Skripte.

Diese Datei enthält die DB_CONFIG für alle Verbindungen zur PostgreSQL-Datenbank.
Änderungen hier wirken sich auf alle Skripte aus, die diese Datei importieren.

Verwendung:
    from src.db_config import DB_CONFIG
    import psycopg
    
    with psycopg.connect(**DB_CONFIG) as conn:
        ...
"""

# Zentrale PostgreSQL-Verbindungskonfiguration
# Docker PostgreSQL Container läuft auf Host-Port 5433
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "postgres",
    "user": "postgres",
    "password": "Start123",
}

__all__ = ["DB_CONFIG"]
