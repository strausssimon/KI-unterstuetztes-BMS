""" 
====================================================
Programmname : miniCRM → PostgreSQL Jobs Import
Beschreibung : Importiert Jobs aus miniCRM Excel-Datei in die PostgreSQL jobs-Tabelle.
Das Mapping zwischen miniCRM und PostgreSQL Spalten ist in mapping_minicrm_postresql_jobs.xlsx definiert.

====================================================
"""

import sys
import os
# Füge Projekt-Root zum Python-Pfad hinzu
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

import pandas as pd
import psycopg
from datetime import datetime, timedelta
from src.db_config import DB_CONFIG

# --------------------------------------------------
# KONFIGURATION
# --------------------------------------------------

# Pfade
JOBS_FILE = r"data\db\miniCRM\jobs_examples.xlsx"
SCHEMA_FILE = r"data\db\jobs_master.xlsx"

# --------------------------------------------------
# MAPPING UND SCHEMA
# --------------------------------------------------
def get_direct_mapping():
    """
    Direktes Mapping zwischen miniCRM Excel-Spalten und PostgreSQL-Spalten.
    Basierend auf jobs_master.xlsx Schema.
    
    Returns:
        dict: {db_column: minicrm_column}
    """
    return {
        'position': 'Job: desired position',
        'department': 'Job: Department',
        'sonstiges_anforderungen': None,  # Nicht in miniCRM
        'job_description': 'Job: Job-Description',
        'long_note': 'Job: long note',
        'gehalt_von': None,  # Nicht in miniCRM
        'gehalt_bis': None,  # Nicht in miniCRM
        'status_job': 'Job: Status',
        'klinik': 'Job: Name',
        'ort': None,  # Nicht in miniCRM
        'status_klinik': None,  # Nicht in miniCRM
        'kontaktname': 'Job: Decision maker',
        'email': None,  # Nicht in miniCRM
        'telefon': 'Job: how / where contacted',
        'von': None,  # Nicht in miniCRM
        'bis': None  # Nicht in miniCRM
    }


# --------------------------------------------------
# JOBS LADEN
# --------------------------------------------------
def load_jobs_from_excel():
    """
    Lädt Jobs aus der miniCRM Excel-Datei.
    """
    df = pd.read_excel(JOBS_FILE)
    print(f"✓ {len(df)} Jobs aus Excel geladen")
    return df


# --------------------------------------------------
# DATEN TRANSFORMIEREN
# --------------------------------------------------
def transform_data(minicrm_df, mapping):
    """
    Transformiert miniCRM Daten basierend auf dem direkten Mapping.
    Erstellt ein DataFrame mit PostgreSQL Spaltennamen.
    """
    transformed_data = []
    
    print(f"   Verfügbare Excel-Spalten: {list(minicrm_df.columns)[:5]}...")
    
    for _, row in minicrm_df.iterrows():
        pg_row = {}
        
        for db_col, minicrm_col in mapping.items():
            # Wenn kein Mapping existiert, setze None
            if minicrm_col is None:
                pg_row[db_col] = None
                continue
            
            # Hole Wert aus miniCRM DataFrame
            value = None
            if minicrm_col in row.index:
                value = row[minicrm_col]
            
            # None/NaN beibehalten für leere Felder
            if pd.isna(value):
                pg_row[db_col] = None
            else:
                # Strings trimmen
                if isinstance(value, str):
                    value = value.strip()
                
                # Spezielle Transformationen
                pg_row[db_col] = transform_field(db_col, value)
        
        transformed_data.append(pg_row)
    
    df = pd.DataFrame(transformed_data)
    
    return df


def transform_field(field_name, value):
    """
    Spezielle Transformationen für bestimmte Felder.
    """
    # Behandle leere Strings explizit als None
    if value is None or (isinstance(value, str) and value.strip() == ''):
        return None
    
    # Datetime Felder
    if 'date' in field_name.lower() or field_name.lower() in ['von', 'bis']:
        if isinstance(value, pd.Timestamp):
            return value
        elif isinstance(value, datetime):
            return value
        elif isinstance(value, str):
            try:
                return pd.to_datetime(value)
            except:
                return None
        return None
    
    # Integer Felder (Gehalt)
    if field_name.lower() in ['gehalt von', 'gehalt bis']:
        try:
            return int(value) if pd.notna(value) else None
        except:
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
        '/': '_',
        '.': '_'
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
    Fügt transformierte Daten in die jobs-Tabelle ein.
    ID wird automatisch per Identity vergeben (Start bei 1000).
    (Spaltennamen sind bereits sanitiert)
    """
    if df.empty:
        print("⚠ Keine Daten zum Einfügen")
        return 0
    
    conn = psycopg.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Spalten ohne ID für INSERT vorbereiten
    columns = [col for col in df.columns.tolist() if col != 'id']
    placeholders = ', '.join(['%s'] * len(columns))
    column_names = ', '.join(columns)
    
    # Prüfe ob minicrm_id existiert für UPSERT
    has_minicrm_id = 'minicrm_id' in columns
    
    if has_minicrm_id:
        # UPSERT auf minicrm_id
        insert_sql = f"""
            INSERT INTO jobs ({column_names})
            VALUES ({placeholders})
            ON CONFLICT (minicrm_id) 
            DO UPDATE SET
                {', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col != 'minicrm_id'])}
            RETURNING id, (xmax = 0) as inserted;
        """
    else:
        # Einfaches INSERT ohne UPSERT
        insert_sql = f"""
            INSERT INTO jobs ({column_names})
            VALUES ({placeholders})
            RETURNING id, true as inserted;
        """
    
    inserted = 0
    updated = 0
    errors = 0
    error_details = []
    
    for idx, row in df.iterrows():
        try:
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
                'position': row.get('position', 'N/A'),
                'klinik': row.get('klinik', 'N/A')
            }
            error_details.append(error_info)
            
            # Zeige nur erste 5 Fehler direkt
            if errors <= 5:
                print(f"\n✗ Fehler bei Zeile {idx + 1}:")
                print(f"   Job: {error_info['position']} bei {error_info['klinik']}")
                print(f"   miniCRM-ID: {error_info['minicrm_id']}")
                print(f"   Fehler: {e}")
            
            continue
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"\n" + "=" * 60)
    print("IMPORT-ZUSAMMENFASSUNG")
    print("=" * 60)
    print(f"✓ {inserted} Jobs neu eingefügt")
    if updated > 0:
        print(f"✓ {updated} Jobs aktualisiert")
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
                    print(f"\nZeile {err['zeile']}: {err['position']} bei {err['klinik']}")
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
    
    # Prüfe miniCRM-ID
    if 'minicrm_id' in df.columns:
        null_count = df['minicrm_id'].isna().sum()
        if null_count > 0:
            print(f"⚠ miniCRM-ID: {null_count} leere Werte")
        print(f"✓ miniCRM-ID vorhanden für UPSERT")
    else:
        print(f"ℹ miniCRM-ID nicht vorhanden - nur INSERT")
    
    print(f"✓ {len(df)} Datensätze bereit zum Import")
    
    return True


# --------------------------------------------------
# MAIN
# --------------------------------------------------
def main():
    print("=" * 60)
    print("miniCRM → PostgreSQL Jobs Import")
    print("=" * 60)
    
    try:
        # 1. Mapping laden
        print("\n1. Lade Mapping...")
        mapping = get_direct_mapping()
        print(f"✓ {len(mapping)} Spalten-Mappings definiert")
        
        # 2. Jobs laden
        print("\n2. Lade Jobs aus Excel...")
        minicrm_df = load_jobs_from_excel()
        
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
        preview_cols = ['minicrm_id', 'position', 'department', 'klinik', 'ort']
        available_cols = [c for c in preview_cols if c in transformed_df.columns]
        if available_cols:
            print(transformed_df[available_cols].head(3).to_string())
        else:
            print("Verfügbare Spalten:", transformed_df.columns.tolist())
            print(transformed_df.head(3).to_string())
        
        # 6. Bestätigung einholen
        print("\n" + "=" * 60)
        response = input(f"\nMöchten Sie {len(transformed_df)} Jobs importieren? (j/n): ")
        
        if response.lower() not in ['j', 'ja', 'y', 'yes']:
            print("\n✗ Import abgebrochen")
            return 0
        
        # 7. In Datenbank einfügen
        print("\n4. Füge Daten in PostgreSQL ein...")
        inserted = insert_into_database(transformed_df)
        
        print("\n" + "=" * 60)
        print("IMPORT ABGESCHLOSSEN")
        print("=" * 60)
        print(f"✓ {inserted} Jobs erfolgreich importiert")
        
        return 0
        
    except FileNotFoundError as e:
        print(f"\n✗ Datei nicht gefunden: {e}")
        print("Bitte prüfen Sie die Pfade:")
        print(f"  - Jobs: {JOBS_FILE}")
        print(f"  - Schema: {SCHEMA_FILE}")
        return 1
        
    except psycopg.Error as e:
        print(f"\n✗ Datenbankfehler: {e}")
        print("Bitte prüfen Sie:")
        print("  - PostgreSQL läuft")
        print("  - Zugangsdaten korrekt")
        print("  - jobs-Tabelle existiert")
        return 1
        
    except Exception as e:
        print(f"\n✗ Unerwarteter Fehler: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())