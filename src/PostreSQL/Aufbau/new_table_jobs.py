"""
Erstellt die Jobs-Tabelle basierend auf data/db/jobs_master.xlsx
Struktur:
- Zeile 1: Spaltennamen
- Zeile 2: Datentypen
- Zeile 3: Beispieleintrag
- Ab Zeile 4: Filterwerte/Vordefinierte Werte
"""

import sys
import os
# Füge Projekt-Root zum Python-Pfad hinzu
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

import psycopg
from psycopg import sql
import pandas as pd
from src.db_config import DB_CONFIG


def read_jobs_schema(excel_path='data/db/jobs_master.xlsx'):
    """
    Liest die Schema-Definition aus der Excel-Datei.
    
    Returns:
        tuple: (column_names, data_types, example_row, filter_values)
    """
    print("=== Lese Schema aus Excel ===\n")
    
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Excel-Datei nicht gefunden: {excel_path}")
    
    # Lese die ersten Zeilen ohne Header
    df = pd.read_excel(excel_path, header=None, nrows=10)
    
    # Zeile 1: Spaltennamen (row 0)
    column_names = df.iloc[0].tolist()
    
    # Zeile 2: Datentypen (row 1)
    data_types = df.iloc[1].tolist()
    
    # Zeile 3: Beispiel (row 2)
    example_row = df.iloc[2].tolist()
    
    # Ab Zeile 4: Filterwerte (rows 3+)
    filter_values = {}
    for idx, col_name in enumerate(column_names):
        if pd.notna(col_name) and col_name not in ['Spaltenname', 'ID']:
            # Sammle alle nicht-leeren Werte ab Zeile 4
            values = []
            for row_idx in range(3, len(df)):
                val = df.iloc[row_idx, idx]
                if pd.notna(val) and str(val).strip() and str(val) != 'NaN':
                    values.append(str(val).strip())
            
            if values:
                filter_values[col_name] = values
    
    print(f"✓ {len(column_names)} Spalten gefunden")
    print(f"✓ {len(filter_values)} Spalten mit Filterwerten")
    
    return column_names, data_types, example_row, filter_values


def get_existing_columns(cur):
    """
    Holt die bestehenden Spalten der jobs-Tabelle.
    
    Returns:
        dict: {column_name: data_type_string}
    """
    cur.execute("""
        SELECT column_name, data_type, character_maximum_length
        FROM information_schema.columns
        WHERE table_name = 'jobs'
        ORDER BY ordinal_position;
    """)
    
    existing = {}
    for col_name, data_type, max_length in cur.fetchall():
        type_str = data_type.upper()
        if max_length and 'CHARACTER' in type_str:
            type_str = f"CHARACTER VARYING({max_length})"
        existing[col_name] = type_str
    
    return existing


def sanitize_column_name(col_name):
    """
    Bereinigt Spaltennamen für PostgreSQL.
    """
    clean_col_name = str(col_name).strip().lower()
    clean_col_name = clean_col_name.replace(' ', '_').replace('/', '_').replace('-', '_')
    clean_col_name = clean_col_name.replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue')
    clean_col_name = clean_col_name.replace('ß', 'ss')
    
    while '__' in clean_col_name:
        clean_col_name = clean_col_name.replace('__', '_')
    
    clean_col_name = clean_col_name.strip('_')
    
    return clean_col_name


def map_excel_type_to_postgres(data_type):
    """
    Mappt Excel-Datentypen auf PostgreSQL-Typen.
    """
    if pd.isna(data_type):
        return 'TEXT'
    
    data_type_str = str(data_type).upper()
    
    if 'CHARACTER VARYING' in data_type_str:
        return data_type_str
    elif data_type_str in ['INT', 'INTEGER']:
        return 'INTEGER'
    elif data_type_str == 'BOOLEAN':
        return 'BOOLEAN'
    elif data_type_str == 'DATE':
        return 'DATE'
    elif data_type_str == 'DATETIME':
        return 'TIMESTAMP'
    else:
        return 'TEXT'


def compare_schemas(existing_columns, desired_columns):
    """
    Vergleicht bestehende und gewünschte Spalten.
    
    Returns:
        tuple: (neue_spalten, wegfallende_spalten, geaenderte_typen)
    """
    existing_names = set(existing_columns.keys())
    desired_names = set(desired_columns.keys())
    
    neue_spalten = {}
    for col in desired_names - existing_names:
        neue_spalten[col] = desired_columns[col]
    
    wegfallende_spalten = list(existing_names - desired_names)
    
    geaenderte_typen = {}
    for col in existing_names & desired_names:
        if existing_columns[col] != desired_columns[col]:
            geaenderte_typen[col] = {
                'alt': existing_columns[col],
                'neu': desired_columns[col]
            }
    
    return neue_spalten, wegfallende_spalten, geaenderte_typen


def alter_table_structure(conn, neue_spalten, wegfallende_spalten, geaenderte_typen):
    """
    Ändert die Tabellenstruktur basierend auf den Unterschieden.
    """
    with conn.cursor() as cur:
        if neue_spalten:
            print("\n=== Füge neue Spalten hinzu ===\n")
            for col_name, col_type in neue_spalten.items():
                print(f"   + {col_name} ({col_type})")
                cur.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_type};")
            conn.commit()
            print(f"\n✓ {len(neue_spalten)} Spalte(n) hinzugefügt")
        
        if wegfallende_spalten:
            print("\n=== Lösche wegfallende Spalten ===\n")
            for col_name in wegfallende_spalten:
                print(f"   - {col_name}")
                cur.execute(f"ALTER TABLE jobs DROP COLUMN {col_name};")
            conn.commit()
            print(f"\n✓ {len(wegfallende_spalten)} Spalte(n) gelöscht")
        
        if geaenderte_typen:
            print("\n=== Ändere Spaltentypen ===\n")
            for col_name, types in geaenderte_typen.items():
                print(f"   ≠ {col_name}: {types['alt']} → {types['neu']}")
                try:
                    cur.execute(f"ALTER TABLE jobs ALTER COLUMN {col_name} TYPE {types['neu']} USING {col_name}::{types['neu']};")
                except Exception as e:
                    print(f"      ⚠ Warnung: Typ konnte nicht geändert werden: {e}")
            conn.commit()
            print(f"\n✓ Typen angepasst")


def create_jobs_table(conn, column_names, data_types):
    """
    Erstellt die Jobs-Tabelle mit allen Spalten aus dem Excel-Schema.
    """
    print("\n=== Erstelle Jobs-Tabelle ===\n")
    
    # Erstelle Dictionary mit bereinigten Spaltennamen und Typen
    desired_columns = {}
    
    for col_name, col_type in zip(column_names, data_types):
        if pd.notna(col_name) and col_name != 'Spaltenname':
            clean_col = sanitize_column_name(col_name)
            pg_type = map_excel_type_to_postgres(col_type)
            
            # ID-Spalte bekommt Identity
            if clean_col == 'id':
                desired_columns[clean_col] = 'INTEGER GENERATED BY DEFAULT AS IDENTITY (START WITH 1000) PRIMARY KEY'
            else:
                desired_columns[clean_col] = pg_type
            
            print(f"   {clean_col}: {desired_columns[clean_col]}")
    
    with conn.cursor() as cur:
        # Prüfe ob Tabelle existiert
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'jobs'
            );
        """)
        table_exists = cur.fetchone()[0]
        
        if table_exists:
            print("\n⚠ Tabelle 'jobs' existiert bereits!")
            response = input("Möchten Sie die Tabelle [d]ropen und neu erstellen oder [a]npassen? (d/a): ").lower()
            
            if response == 'd':
                print("\n=== Lösche bestehende Tabelle ===")
                cur.execute("DROP TABLE IF EXISTS jobs CASCADE;")
                conn.commit()
                table_exists = False
            elif response == 'a':
                # Anpassungsmodus
                existing_columns = get_existing_columns(cur)
                neue_spalten, wegfallende_spalten, geaenderte_typen = compare_schemas(existing_columns, desired_columns)
                
                if neue_spalten or wegfallende_spalten or geaenderte_typen:
                    alter_table_structure(conn, neue_spalten, wegfallende_spalten, geaenderte_typen)
                else:
                    print("\n✓ Tabellenstruktur ist bereits aktuell")
                
                return  # Fertig mit Anpassung
            else:
                print("Abbruch.")
                return
        
        if not table_exists:
            # Erstelle neue Tabelle
            columns_sql = []
            for col_name, col_type in desired_columns.items():
                columns_sql.append(f"{col_name} {col_type}")
            
            create_sql = f"CREATE TABLE jobs ({', '.join(columns_sql)});"
            
            print("\n=== SQL für neue Tabelle ===")
            print(create_sql)
            print()
            
            cur.execute(create_sql)
            conn.commit()
            
            print("✓ Tabelle 'jobs' erfolgreich erstellt!")




def show_table_info(conn):
    """
    Zeigt Informationen über die Jobs-Tabelle.
    """
    with conn.cursor() as cur:
        # Spalteninfo
        cur.execute("""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'jobs'
            ORDER BY ordinal_position;
        """)
        
        print("\n=== Tabellenstruktur 'jobs' ===\n")
        for col_name, data_type, max_length in cur.fetchall():
            type_info = data_type
            if max_length:
                type_info += f"({max_length})"
            print(f"   {col_name}: {type_info}")
        
        # Anzahl Zeilen
        cur.execute("SELECT COUNT(*) FROM jobs;")
        count = cur.fetchone()[0]
        print(f"\n✓ Anzahl Datensätze: {count}")


def main():
    """
    Hauptfunktion zum Erstellen/Anpassen der Jobs-Tabelle.
    """
    print("=" * 60)
    print(" Jobs-Tabelle Setup")
    print("=" * 60)
    
    # Lese Schema aus Excel
    column_names, data_types, example_row, filter_values = read_jobs_schema()
    
    # Verbinde mit Datenbank
    print("\n=== Verbinde mit Datenbank ===\n")
    conn = psycopg.connect(**DB_CONFIG)
    print("✓ Verbunden")
    
    try:
        # Erstelle/Aktualisiere Tabelle
        create_jobs_table(conn, column_names, data_types)
        
        # Zeige Tabelleninfo
        show_table_info(conn)
        
    finally:
        conn.close()
        print("\n✓ Verbindung geschlossen")


if __name__ == "__main__":
    main()
