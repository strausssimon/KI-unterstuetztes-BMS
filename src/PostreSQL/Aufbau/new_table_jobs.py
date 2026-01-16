"""
Erstellt die Jobs-Tabelle basierend auf data/db/jobs_master.xlsx
Struktur:
- Zeile 1: Spaltennamen
- Zeile 2: Datentypen
- Zeile 3: Beispieleintrag
- Ab Zeile 4: Filterwerte/Vordefinierte Werte
"""

import psycopg
from psycopg import sql
import pandas as pd
import os

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


def create_jobs_table(conn):
    """
    Erstellt die Jobs-Tabelle in PostgreSQL.
    """
    print("\n=== Erstelle Jobs-Tabelle ===\n")
    
    # Lese Schema
    column_names, data_types, example_row, filter_values = read_jobs_schema()
    
    with conn.cursor() as cur:
        # Prüfe ob Tabelle bereits existiert
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'jobs'
            );
        """)
        
        table_exists = cur.fetchone()[0]
        
        if table_exists:
            print("⚠ Tabelle 'jobs' existiert bereits!")
            antwort = input("Möchten Sie die Tabelle löschen und neu erstellen? (j/n): ").strip().lower()
            if antwort in ['j', 'ja', 'y', 'yes']:
                print("   Lösche alte Tabelle...")
                cur.execute("DROP TABLE jobs CASCADE;")
                conn.commit()
                print("✓ Tabelle gelöscht")
            else:
                print("✓ Abgebrochen. Tabelle bleibt erhalten.")
                return
        
        # Baue CREATE TABLE Statement
        print("   Erstelle CREATE TABLE Statement...")
        
        create_columns = []
        for i, (col_name, data_type) in enumerate(zip(column_names, data_types)):
            if pd.notna(col_name) and col_name != 'Spaltenname':
                # Bereinige Spaltennamen (entferne Leerzeichen, Sonderzeichen)
                clean_col_name = str(col_name).strip().lower()
                clean_col_name = clean_col_name.replace(' ', '_').replace('/', '_').replace('-', '_')
                clean_col_name = clean_col_name.replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue')
                clean_col_name = clean_col_name.replace('ß', 'ss')
                
                # Mappe Excel-Datentypen auf PostgreSQL
                if pd.isna(data_type):
                    pg_type = 'TEXT'
                elif 'character varying' in str(data_type):
                    pg_type = str(data_type)
                elif data_type == 'int':
                    pg_type = 'INTEGER'
                elif data_type == 'boolean':
                    pg_type = 'BOOLEAN'
                elif data_type == 'date':
                    pg_type = 'DATE'
                elif data_type == 'datetime':
                    pg_type = 'TIMESTAMP'
                else:
                    pg_type = 'TEXT'
                
                # ID als Primary Key
                if col_name == 'ID':
                    create_columns.append(f'    {clean_col_name} {pg_type} PRIMARY KEY')
                else:
                    create_columns.append(f'    {clean_col_name} {pg_type}')
        
        create_statement = f"""
CREATE TABLE jobs (
{',\n'.join(create_columns)}
);
        """
        
        print("\n--- CREATE TABLE Statement ---")
        print(create_statement)
        print("--- Ende Statement ---\n")
        
        # Führe CREATE TABLE aus
        cur.execute(create_statement)
        conn.commit()
        
        print("✓ Tabelle 'jobs' erstellt")
        
        # Zeige Filterwerte an
        if filter_values:
            print("\n=== Vordefinierte Filterwerte ===\n")
            for col_name, values in filter_values.items():
                print(f"{col_name}:")
                for val in values[:5]:  # Zeige max 5 Werte
                    print(f"  - {val}")
                if len(values) > 5:
                    print(f"  ... und {len(values) - 5} weitere")
                print()


def insert_example_job(conn):
    """
    Fügt den Beispiel-Job aus der Excel-Datei ein.
    """
    print("\n=== Füge Beispiel-Job ein ===\n")
    
    # Lese Schema
    column_names, data_types, example_row, _ = read_jobs_schema()
    
    with conn.cursor() as cur:
        # Prüfe ob bereits Jobs vorhanden sind
        cur.execute("SELECT COUNT(*) FROM jobs;")
        existing_count = cur.fetchone()[0]
        
        if existing_count > 0:
            print(f"⚠ Es sind bereits {existing_count} Jobs in der Datenbank")
            antwort = input("Möchten Sie trotzdem den Beispiel-Job hinzufügen? (j/n): ").strip().lower()
            if antwort not in ['j', 'ja', 'y', 'yes']:
                print("✓ Abgebrochen.")
                return
        
        # Bereite INSERT vor
        clean_columns = []
        values = []
        
        for col_name, value, data_type in zip(column_names, example_row, data_types):
            if pd.notna(col_name) and col_name != 'Spaltenname':
                clean_col_name = str(col_name).strip().lower()
                clean_col_name = clean_col_name.replace(' ', '_').replace('/', '_').replace('-', '_')
                clean_col_name = clean_col_name.replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue')
                clean_col_name = clean_col_name.replace('ß', 'ss')
                clean_columns.append(clean_col_name)
                
                # Konvertiere Werte
                if pd.isna(value) or str(value) == 'NaN':
                    values.append(None)
                elif data_type == 'int':
                    try:
                        values.append(int(value))
                    except:
                        values.append(None)
                elif data_type == 'boolean':
                    values.append(str(value).lower() in ['true', 'ja', 'yes', '1'])
                else:
                    values.append(str(value))
        
        # Baue INSERT Statement
        placeholders = ', '.join(['%s'] * len(values))
        columns_str = ', '.join(clean_columns)
        
        insert_sql = f"""
            INSERT INTO jobs ({columns_str})
            VALUES ({placeholders})
            RETURNING id;
        """
        
        try:
            cur.execute(insert_sql, values)
            job_id = cur.fetchone()[0]
            conn.commit()
            
            print(f"✓ Beispiel-Job eingefügt: ID = {job_id}")
            
            # Zeige eingefügte Daten
            print("\n=== Eingefügter Job ===\n")
            cur.execute("SELECT * FROM jobs WHERE id = %s;", (job_id,))
            row = cur.fetchone()
            col_names = [desc[0] for desc in cur.description]
            
            for col, val in zip(col_names, row):
                if val is not None:
                    print(f"{col:25s}: {val}")
            
        except Exception as e:
            conn.rollback()
            print(f"✗ Fehler beim Einfügen: {e}")
            raise


def show_table_info(conn):
    """
    Zeigt Informationen über die Jobs-Tabelle.
    """
    print("\n=== Tabellen-Information ===\n")
    
    with conn.cursor() as cur:
        # Spalten-Info
        cur.execute("""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'jobs'
            ORDER BY ordinal_position;
        """)
        
        print("Spalten:")
        for col_name, data_type, max_length in cur.fetchall():
            type_str = f"{data_type}"
            if max_length:
                type_str += f"({max_length})"
            print(f"  - {col_name:30s} {type_str}")
        
        # Anzahl Einträge
        cur.execute("SELECT COUNT(*) FROM jobs;")
        count = cur.fetchone()[0]
        print(f"\n✓ Anzahl Jobs: {count}")


def main():
    """Hauptfunktion"""
    print("=" * 80)
    print("Jobs-Tabelle erstellen")
    print("=" * 80)
    
    # Verbindungsparameter
    conn_params = {
        'host': 'localhost',
        'port': 5432,
        'dbname': 'postgres',
        'user': 'postgres',
        'password': 'bigdataconsulting'
    }
    
    try:
        # Verbindung herstellen
        print("\n=== Datenbankverbindung ===\n")
        with psycopg.connect(**conn_params, connect_timeout=10) as conn:
            print("✓ Verbindung zu PostgreSQL hergestellt")
            
            # Tabelle erstellen
            create_jobs_table(conn)
            
            # Beispiel-Job einfügen
            antwort = input("\nMöchten Sie den Beispiel-Job einfügen? (j/n): ").strip().lower()
            if antwort in ['j', 'ja', 'y', 'yes']:
                insert_example_job(conn)
            
            # Tabellen-Info anzeigen
            show_table_info(conn)
            
            print("\n" + "=" * 80)
            print("✓ Erfolgreich abgeschlossen!")
            print("=" * 80)
            
    except psycopg.Error as e:
        print(f"\n✗ Datenbankfehler: {e}")
        print("\nStellen Sie sicher, dass:")
        print("  1. Docker läuft (docker-start.bat)")
        print("  2. PostgreSQL Container aktiv ist")
    except Exception as e:
        print(f"\n✗ Fehler: {e}")
        raise


if __name__ == "__main__":
    main()
