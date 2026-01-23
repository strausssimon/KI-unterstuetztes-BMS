#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
miniCRM_import.py

Importiert Kandidaten aus miniCRM Excel-Datei in die PostgreSQL candidates-Tabelle.
Das Mapping zwischen miniCRM und PostgreSQL Spalten ist in mapping_minicrm_postresql.xlsx definiert.
"""

import sys
import os
# Füge Projekt-Root zum Python-Pfad hinzu
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

import pandas as pd
import psycopg
from datetime import datetime
from src.db_config import DB_CONFIG

# --------------------------------------------------
# KONFIGURATION
# --------------------------------------------------

# Pfade
MAPPING_FILE = r"src\PostreSQL\import\mapping_minicrm_postresql.xlsx"
CANDIDATES_FILE = r"data\db\miniCRM\candidates_examples.xlsx"

# --------------------------------------------------
# MAPPING LADEN
# --------------------------------------------------
def load_mapping():
    """
    Lädt das Mapping aus der Excel-Datei.
    Gibt ein Dictionary zurück: {postgresql_spalte: minicrm_spalte}
    """
    df = pd.read_excel(MAPPING_FILE)
    
    # Zeile 0: minicrm-candidates-index (Index-Nummern)
    # Zeile 1: minicrm-candidates (tatsächliche Spaltennamen)
    # Spalte 0 enthält die PostgreSQL Spaltennamen
    
    postgresql_cols = df.columns.tolist()
    minicrm_cols = df.iloc[1].tolist()  # Zeile 1 (minicrm-candidates)
    
    mapping = {}
    for i, pg_col in enumerate(postgresql_cols):
        if i == 0:  # Erste Spalte ist "postresql-candidates"
            continue
        
        # ID wird automatisch vergeben, daher überspringen
        if pg_col == 'ID':
            continue
        
        minicrm_col = minicrm_cols[i]
        
        # Nur hinzufügen wenn miniCRM Spaltenname existiert (nicht NaN)
        if pd.notna(minicrm_col):
            mapping[pg_col] = minicrm_col
    
    return mapping


# --------------------------------------------------
# KANDIDATEN LADEN
# --------------------------------------------------
def load_candidates_from_excel():
    """
    Lädt Kandidaten aus der miniCRM Excel-Datei.
    """
    df = pd.read_excel(CANDIDATES_FILE)
    print(f"✓ {len(df)} Kandidaten aus Excel geladen")
    return df


# --------------------------------------------------
# DATEN TRANSFORMIEREN
# --------------------------------------------------
def transform_data(minicrm_df, mapping):
    """
    Transformiert miniCRM Daten basierend auf dem Mapping.
    Erstellt ein DataFrame mit PostgreSQL Spaltennamen (bereits sanitiert).
    """
    transformed_data = []
    
    for _, row in minicrm_df.iterrows():
        pg_row = {}
        
        for pg_col, minicrm_col in mapping.items():
            value = row.get(minicrm_col)
            
            # Spezialbehandlung für Datumsfeld "Anlage wann" / "Letzter Kontakt": Auch bei NaN transform_field aufrufen
            if (
                pg_col.lower() in ['anlage wann', 'letzter kontakt']
                or 'anlage_wann' in pg_col.lower()
                or 'letzter_kontakt' in pg_col.lower()
            ):
                if pd.isna(value) or (isinstance(value, str) and value.strip() == ''):
                    pg_row[pg_col] = datetime.now()
                else:
                    # Strings trimmen
                    if isinstance(value, str):
                        value = value.strip()
                    pg_row[pg_col] = transform_field(pg_col, value)
            else:
                # None/NaN beibehalten für andere Felder
                if pd.isna(value):
                    pg_row[pg_col] = None
                else:
                    # Strings trimmen
                    if isinstance(value, str):
                        value = value.strip()
                    
                    # Spezielle Transformationen
                    pg_row[pg_col] = transform_field(pg_col, value)
        
        # miniCRM-ID immer aus "candidate: Id" übernehmen
        if 'candidate: Id' in row:
            minicrm_id = row['candidate: Id']
            pg_row['miniCRM-ID'] = minicrm_id if pd.notna(minicrm_id) else None
        
        transformed_data.append(pg_row)
    
    df = pd.DataFrame(transformed_data)
    
    # Spaltennamen direkt nach Transformation sanitieren
    df.columns = [sanitize_column_name(col) for col in df.columns]
    
    return df


def transform_field(field_name, value):
    """
    Spezielle Transformationen für bestimmte Felder.
    """
    # Datetime Felder - Spezialbehandlung für anlage_wann / letzter kontakt
    if 'date' in field_name.lower() or field_name.lower() in ['anlage wann', 'letzter kontakt']:
        # Wenn leer, verwende aktuelles Datum für anlage_wann/letzter kontakt
        if (value is None or (isinstance(value, str) and value.strip() == '')) and field_name.lower() in ['anlage wann', 'letzter kontakt']:
            return datetime.now()
        
        # Behandle leere Strings als None für andere Datumsfelder
        if value is None or (isinstance(value, str) and value.strip() == ''):
            return None
        
        if isinstance(value, pd.Timestamp):
            return value
        elif isinstance(value, str):
            try:
                return pd.to_datetime(value)
            except:
                return None
        # Wenn es weder Timestamp noch String ist, aber auch nicht None -> None
        return None
    
    # Behandle leere Strings explizit als None für andere Felder
    if value is None or (isinstance(value, str) and value.strip() == ''):
        return None
    
    # Integer Felder
    if field_name.lower() in ['regionale verfügbarkeit', 'id']:
        try:
            return int(value) if pd.notna(value) else None
        except:
            return None
    
    # Boolean Felder - konvertiere zu echtem Boolean
    if field_name.lower() in ['umzugszwang', 'ready_to_move']:
        if isinstance(value, str):
            value_lower = value.lower().strip()
            if value_lower in ['ja', 'yes', 'true', '1']:
                return True
            elif value_lower in ['nein', 'no', 'false', '0']:
                return False
        elif isinstance(value, bool):
            return value
        return None
    
    return value


# --------------------------------------------------
# SPALTENNAMEN SANITIEREN
# --------------------------------------------------
def sanitize_column_name(col_name):
    """
    Konvertiert Spaltennamen für PostgreSQL:
    - Umlaute ersetzen (ä→ae, ö→oe, ü→ue)
    - Leerzeichen und Bindestriche durch Unterstriche ersetzen
    - Kleinbuchstaben
    - Führende/Trailing Unterstriche entfernen
    - Multiple Unterstriche auf einen reduzieren
    """
    replacements = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue',
        'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
        'ß': 'ss',
        ' ': '_',
        '-': '_',
        '/': '_'
    }
    
    # Erst trimmen
    sanitized = str(col_name).strip()
    
    # Dann Zeichen ersetzen
    for old, new in replacements.items():
        sanitized = sanitized.replace(old, new)
    
    # Kleinbuchstaben
    sanitized = sanitized.lower()
    
    # Multiple Unterstriche auf einen reduzieren
    while '__' in sanitized:
        sanitized = sanitized.replace('__', '_')
    
    # Führende/Trailing Unterstriche entfernen
    sanitized = sanitized.strip('_')
    
    return sanitized


# --------------------------------------------------
# IN DATENBANK EINFÜGEN
# --------------------------------------------------
def insert_into_database(df):
    """
    Fügt transformierte Daten in die candidates-Tabelle ein.
    ID wird automatisch fortlaufend vergeben.
    (Spaltennamen sind bereits sanitiert)
    """
    if df.empty:
        print("⚠ Keine Daten zum Einfügen")
        return 0
    
    conn = psycopg.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Höchste bestehende ID ermitteln (ID kann TEXT oder INTEGER sein)
    try:
        # Versuche als INTEGER
        cur.execute("SELECT COALESCE(MAX(id::INTEGER), 0) FROM candidates;")
        max_id = cur.fetchone()[0]
    except Exception as e:
        # Rollback bei Fehler
        conn.rollback()
        # Falls TEXT-IDs existieren, zähle alle und nimm die höchste numerische
        try:
            cur.execute("""
                SELECT COALESCE(MAX(CAST(id AS INTEGER)), 0) 
                FROM candidates 
                WHERE id ~ '^[0-9]+$';
            """)
            max_id = cur.fetchone()[0]
        except:
            # Wenn auch das fehlschlägt, starte bei 1
            conn.rollback()
            max_id = 0
    
    next_id = max_id + 1
    
    print(f"ℹ Höchste bestehende ID: {max_id}")
    print(f"ℹ Nächste ID beginnt bei: {next_id}\n")
    
    # Spalten ohne ID für INSERT vorbereiten
    columns = [col for col in df.columns.tolist() if col != 'id']
    placeholders = ', '.join(['%s'] * len(columns))
    column_names = ', '.join(columns)
    
    # Prüfe ob minicrm_id existiert für UPSERT
    has_minicrm_id = 'minicrm_id' in columns
    
    if has_minicrm_id:
        # UPSERT auf minicrm_id - ID wird automatisch per Subquery ermittelt
        # Nur numerische IDs für MAX berücksichtigen (~ '^[0-9]+$' prüft auf nur Zahlen)
        insert_sql = f"""
            INSERT INTO candidates (id, {column_names})
            VALUES (
                COALESCE(
                    (SELECT id FROM candidates WHERE minicrm_id = %s),
                    CAST(
                        (SELECT COALESCE(MAX(CAST(id AS INTEGER)), 0) + 1 
                         FROM candidates 
                         WHERE id ~ '^[0-9]+$') 
                    AS TEXT)
                ),
                {placeholders}
            )
            ON CONFLICT (minicrm_id) DO UPDATE SET
                {', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col != 'minicrm_id'])}
            RETURNING id, (xmax = 0) as inserted;
        """
    else:
        # Einfaches INSERT ohne UPSERT - ID wird per Subquery ermittelt
        # Nur numerische IDs für MAX berücksichtigen
        insert_sql = f"""
            INSERT INTO candidates (id, {column_names})
            VALUES (
                CAST(
                    (SELECT COALESCE(MAX(CAST(id AS INTEGER)), 0) + 1 
                     FROM candidates 
                     WHERE id ~ '^[0-9]+$') 
                AS TEXT),
                {placeholders}
            )
            RETURNING id, true as inserted;
        """
    
    inserted = 0
    updated = 0
    errors = 0
    error_details = []
    
    for idx, row in df.iterrows():
        try:
            if has_minicrm_id:
                # minicrm_id muss als erster Parameter für die Subquery übergeben werden
                values = [row['minicrm_id']] + [row[col] for col in columns]
            else:
                values = [row[col] for col in columns]
            
            cur.execute(insert_sql, values)
            result = cur.fetchone()
            returned_id = result[0]
            was_inserted = result[1]
            
            if was_inserted:
                inserted += 1
            else:
                updated += 1
            
        except Exception as e:
            errors += 1
            conn.rollback()  # Rollback nach jedem Fehler
            
            # Detaillierte Fehlerinformationen sammeln
            error_info = {
                'zeile': idx + 1,
                'fehler': str(e),
                'minicrm_id': row.get('minicrm_id', 'N/A'),
                'vorname': row.get('first_name', 'N/A'),
                'nachname': row.get('last_name', 'N/A')
            }
            error_details.append(error_info)
            
            # Zeige nur erste 5 Fehler direkt
            if errors <= 5:
                print(f"\n✗ Fehler bei Zeile {idx + 1}:")
                print(f"   Kandidat: {error_info['vorname']} {error_info['nachname']}")
                print(f"   miniCRM-ID: {error_info['minicrm_id']}")
                print(f"   Fehler: {e}")
            
            continue
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"\n" + "=" * 60)
    print("IMPORT-ZUSAMMENFASSUNG")
    print("=" * 60)
    print(f"✓ {inserted} Kandidaten neu eingefügt")
    if updated > 0:
        print(f"✓ {updated} Kandidaten aktualisiert")
    if errors > 0:
        print(f"✗ {errors} Fehler aufgetreten")
        
        if errors > 5:
            print(f"\nℹ Weitere {errors - 5} Fehler (nicht alle angezeigt)")
            print("Möchten Sie alle Fehler-Details sehen? (j/n):")
            antwort = input().strip().lower()
            if antwort in ['j', 'ja', 'y', 'yes']:
                print("\n" + "=" * 60)
                print("ALLE FEHLER-DETAILS")
                print("=" * 60)
                for err in error_details:
                    print(f"\nZeile {err['zeile']}: {err['vorname']} {err['nachname']}")
                    print(f"  miniCRM-ID: {err['minicrm_id']}")
                    print(f"  Fehler: {err['fehler']}")
    
    return inserted + updated


# --------------------------------------------------
# VALIDIERUNG
# --------------------------------------------------
def validate_data(df):
    """
    Validiert die transformierten Daten vor dem Import.
    (Spaltennamen sind bereits sanitiert)
    """
    print("\n" + "=" * 60)
    print("DATENVALIDIERUNG")
    print("=" * 60)
    
    # Pflichtfelder prüfen (bereits sanitiert)
    required_fields = {
        'last_name': 'Last Name',
        'first_name': 'First Name'
    }
    
    missing_required = []
    
    for sanitized_name, display_name in required_fields.items():
        if sanitized_name not in df.columns:
            missing_required.append(display_name)
        else:
            null_count = df[sanitized_name].isna().sum()
            if null_count > 0:
                print(f"⚠ {display_name}: {null_count} leere Werte")
    
    if missing_required:
        print(f"✗ Fehlende Pflichtfelder: {', '.join(missing_required)}")
        print(f"\nℹ Verfügbare Spalten:")
        for col in sorted(df.columns):
            print(f"  - {col}")
        return False
    
    # Prüfe miniCRM-ID
    if 'minicrm_id' in df.columns:
        null_count = df['minicrm_id'].isna().sum()
        if null_count > 0:
            print(f"⚠ miniCRM-ID: {null_count} leere Werte")
        print(f"✓ miniCRM-ID vorhanden für UPSERT")
    else:
        print(f"ℹ miniCRM-ID nicht vorhanden - nur INSERT")
    
    print(f"✓ Alle Pflichtfelder vorhanden")
    print(f"✓ {len(df)} Datensätze bereit zum Import")
    
    return True


# --------------------------------------------------
# MAIN
# --------------------------------------------------
def main():
    print("=" * 60)
    print("miniCRM → PostgreSQL Import")
    print("=" * 60)
    
    try:
        # 1. Mapping laden
        print("\n1. Lade Mapping...")
        mapping = load_mapping()
        print(f"✓ {len(mapping)} Spalten-Mappings geladen")
        
        # 2. Kandidaten laden
        print("\n2. Lade Kandidaten aus Excel...")
        minicrm_df = load_candidates_from_excel()
        
        # 3. Daten transformieren
        print("\n3. Transformiere Daten...")
        transformed_df = transform_data(minicrm_df, mapping)
        print(f"✓ {len(transformed_df)} Datensätze transformiert")
        
        # 4. Daten validieren
        if not validate_data(transformed_df):
            print("\n✗ Validierung fehlgeschlagen. Import abgebrochen.")
            return 1
        
        # 5. Vorschau anzeigen
        print("\n" + "=" * 60)
        print("VORSCHAU (erste 3 Zeilen)")
        print("=" * 60)
        # Spalten sind bereits sanitiert
        preview_cols = ['minicrm_id', 'first_name', 'last_name', 'position_now', 'department']
        available_cols = [c for c in preview_cols if c in transformed_df.columns]
        print(transformed_df[available_cols].head(3).to_string())
        
        # 6. Bestätigung einholen
        print("\n" + "=" * 60)
        response = input(f"\nMöchten Sie {len(transformed_df)} Kandidaten importieren? (j/n): ")
        
        if response.lower() not in ['j', 'ja', 'y', 'yes']:
            print("\n✗ Import abgebrochen")
            return 0
        
        # 7. In Datenbank einfügen
        print("\n4. Füge Daten in PostgreSQL ein...")
        inserted = insert_into_database(transformed_df)
        
        print("\n" + "=" * 60)
        print("IMPORT ABGESCHLOSSEN")
        print("=" * 60)
        print(f"✓ {inserted} Kandidaten erfolgreich importiert")
        
        return 0
        
    except FileNotFoundError as e:
        print(f"\n✗ Datei nicht gefunden: {e}")
        print("Bitte prüfen Sie die Pfade:")
        print(f"  - Mapping: {MAPPING_FILE}")
        print(f"  - Kandidaten: {CANDIDATES_FILE}")
        return 1
        
    except psycopg.Error as e:
        print(f"\n✗ Datenbankfehler: {e}")
        print("Bitte prüfen Sie:")
        print("  - PostgreSQL läuft")
        print("  - Zugangsdaten korrekt")
        print("  - candidates-Tabelle existiert")
        return 1
        
    except Exception as e:
        print(f"\n✗ Unerwarteter Fehler: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
