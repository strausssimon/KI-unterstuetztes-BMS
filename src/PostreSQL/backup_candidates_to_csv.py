""" 
====================================================
Programmname : Backup Kandidaten-Tabelle als CSV
Beschreibung : Backup-Skript für die candidates-Tabelle
Exportiert die Tabelle als CSV mit Zeitstempel im Dateinamen

====================================================
"""

import sys
import os
# Füge Projekt-Root zum Python-Pfad hinzu
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

import psycopg
import pandas as pd
from datetime import datetime
from src.db_config import DB_CONFIG

# --------------------------------------------------
# KONFIGURATION
# --------------------------------------------------

BACKUP_DIR = r"data\db\backup_postresql"


def ensure_backup_directory():
    """
    Stellt sicher, dass das Backup-Verzeichnis existiert.
    """
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        print(f"✓ Backup-Verzeichnis erstellt: {BACKUP_DIR}")
    else:
        print(f"✓ Backup-Verzeichnis existiert: {BACKUP_DIR}")


def backup_candidates_table():
    """
    Erstellt ein CSV-Backup der candidates-Tabelle mit Zeitstempel.
    """
    print("\n=== PostgreSQL Candidates Backup ===\n")
    
    # Verbindung zur Datenbank
    print("Verbinde mit PostgreSQL...")
    try:
        conn = psycopg.connect(**DB_CONFIG)
        print("✓ Verbindung erfolgreich\n")
    except Exception as e:
        print(f"✗ Fehler bei der Verbindung: {e}")
        return
    
    try:
        # Tabelle auslesen
        print("Lese candidates-Tabelle aus...")
        
        # Verwende cursor mit Text-Casting für Datums-/Zeitfelder
        with conn.cursor() as cur:
            # Hole erst die Spaltennamen und Typen
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'candidates' 
                ORDER BY ordinal_position;
            """)
            
            columns_info = cur.fetchall()
            column_names = [col[0] for col in columns_info]
            
            # Baue SELECT-Statement mit CAST für problematische Typen
            select_parts = []
            for col_name, data_type in columns_info:
                # Timestamp und Date Spalten als TEXT casten, um Fehler zu vermeiden
                if data_type in ['timestamp without time zone', 'timestamp with time zone', 'date', 'time']:
                    select_parts.append(f"{col_name}::TEXT as {col_name}")
                else:
                    select_parts.append(col_name)
            
            select_statement = "SELECT " + ", ".join(select_parts) + " FROM candidates;"
            
            # Führe Query aus
            cur.execute(select_statement)
            rows = cur.fetchall()
            
            # DataFrame erstellen
            df = pd.DataFrame(rows, columns=column_names)

            # Dynamische Export-Zeitstempel-Spalten ergänzen
            now = datetime.now()
            df["export_timestamp"] = now.strftime("%Y-%m-%d %H:%M:%S")
            df["export_date"] = now.strftime("%Y-%m-%d")
        
        row_count = len(df)
        col_count = len(df.columns)
        print(f"✓ {row_count} Zeilen und {col_count} Spalten gelesen\n")
        
        # Zeitstempel für Dateinamen erstellen (dynamisch)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Dateiname mit Zeitstempel
        filename = f"candidates_backup_{timestamp}.csv"
        filepath = os.path.join(BACKUP_DIR, filename)
        
        # Verzeichnis sicherstellen
        ensure_backup_directory()
        
        # CSV speichern mit Fehlerbehandlung für problematische Zeichen
        print(f"Speichere Backup als CSV...")
        df.to_csv(filepath, index=False, encoding='utf-8', errors='replace')
        
        file_size = os.path.getsize(filepath) / 1024  # in KB
        
        print(f"✓ Backup erfolgreich erstellt!\n")
        print(f"Datei: {filepath}")
        print(f"Größe: {file_size:.2f} KB")
        print(f"Zeilen: {row_count}")
        print(f"Spalten: {col_count}")
        print(f"Zeitstempel: {timestamp}")
        
    except Exception as e:
        print(f"✗ Fehler beim Backup: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        conn.close()
        print("\n✓ Datenbankverbindung geschlossen")


def list_recent_backups(limit=5):
    """
    Listet die letzten Backups auf.
    """
    print(f"\n=== Letzte {limit} Backups ===\n")
    
    if not os.path.exists(BACKUP_DIR):
        print("Keine Backups vorhanden.")
        return
    
    # Alle CSV-Dateien mit candidates_backup im Namen
    backup_files = [
        f for f in os.listdir(BACKUP_DIR) 
        if f.startswith("candidates_backup_") and f.endswith(".csv")
    ]
    
    if not backup_files:
        print("Keine Backups vorhanden.")
        return
    
    # Nach Datum sortieren (neueste zuerst)
    backup_files.sort(reverse=True)
    
    for i, filename in enumerate(backup_files[:limit], 1):
        filepath = os.path.join(BACKUP_DIR, filename)
        file_size = os.path.getsize(filepath) / 1024  # in KB
        mod_time = datetime.fromtimestamp(os.path.getmtime(filepath))
        
        print(f"{i}. {filename}")
        print(f"   Größe: {file_size:.2f} KB")
        print(f"   Erstellt: {mod_time.strftime('%d.%m.%Y %H:%M:%S')}")
        print()


if __name__ == "__main__":
    # Backup erstellen
    backup_candidates_table()
    
    # Letzte Backups anzeigen
    list_recent_backups()
