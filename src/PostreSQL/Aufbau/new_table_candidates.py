"""
Erstellt die Candidates-Tabelle basierend auf data/db/candidates_master.xlsx
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

def read_candidates_schema(excel_path='data/db/candidates_master.xlsx'):
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
    Holt die bestehenden Spalten der candidates-Tabelle.
    
    Returns:
        dict: {column_name: (data_type, character_maximum_length)}
    """
    cur.execute("""
        SELECT column_name, data_type, character_maximum_length
        FROM information_schema.columns
        WHERE table_name = 'candidates'
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
    - Umlaute ersetzen (ä→ae, ö→oe, ü→ue)
    - Leerzeichen und Bindestriche durch Unterstriche ersetzen
    - Kleinbuchstaben
    - Führende/Trailing Unterstriche entfernen
    - Multiple Unterstriche auf einen reduzieren
    """
    clean_col_name = str(col_name).strip().lower()
    clean_col_name = clean_col_name.replace(' ', '_').replace('/', '_').replace('-', '_')
    clean_col_name = clean_col_name.replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue')
    clean_col_name = clean_col_name.replace('ß', 'ss')
    
    # Multiple Unterstriche auf einen reduzieren
    while '__' in clean_col_name:
        clean_col_name = clean_col_name.replace('__', '_')
    
    # Führende/Trailing Unterstriche entfernen
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
    elif data_type_str == 'INT':
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
        # Neue Spalten hinzufügen
        if neue_spalten:
            print("\n=== Füge neue Spalten hinzu ===\n")
            for col_name, col_type in neue_spalten.items():
                print(f"   + {col_name} ({col_type})")
                cur.execute(f"ALTER TABLE candidates ADD COLUMN {col_name} {col_type};")
                
                # minicrm_id benötigt UNIQUE Constraint
                if col_name == 'minicrm_id':
                    print(f"   + Erstelle UNIQUE Constraint für {col_name}")
                    cur.execute(f"ALTER TABLE candidates ADD CONSTRAINT unique_minicrm_id UNIQUE ({col_name});")
            
            conn.commit()
            print(f"\n✓ {len(neue_spalten)} Spalte(n) hinzugefügt")
        
        # Wegfallende Spalten löschen
        if wegfallende_spalten:
            print("\n=== Lösche wegfallende Spalten ===\n")
            for col_name in wegfallende_spalten:
                print(f"   - {col_name}")
                cur.execute(f"ALTER TABLE candidates DROP COLUMN {col_name};")
            conn.commit()
            print(f"\n✓ {len(wegfallende_spalten)} Spalte(n) gelöscht")
        
        # Geänderte Typen
        if geaenderte_typen:
            print("\n=== Ändere Spaltentypen ===\n")
            for col_name, types in geaenderte_typen.items():
                print(f"   ≠ {col_name}: {types['alt']} → {types['neu']}")
                try:
                    cur.execute(f"ALTER TABLE candidates ALTER COLUMN {col_name} TYPE {types['neu']} USING {col_name}::{types['neu']};")
                except Exception as e:
                    print(f"      ⚠ Warnung: Typ konnte nicht geändert werden: {e}")
            conn.commit()
            print(f"\n✓ Typen angepasst")


def create_candidates_table(conn):
    """
    Erstellt die Candidates-Tabelle in PostgreSQL oder passt sie an.
    """
    print("\n=== Erstelle/Prüfe Candidates-Tabelle ===\n")
    
    # Lese Schema
    column_names, data_types, example_row, filter_values = read_candidates_schema()
    
    with conn.cursor() as cur:
        # Prüfe ob Tabelle bereits existiert
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'candidates'
            );
        """)
        
        table_exists = cur.fetchone()[0]
        
        if table_exists:
            print("ℹ Tabelle 'candidates' existiert bereits\n")
            print("=== Prüfe Tabellenstruktur ===\n")
            
            # Bestehende Spalten holen
            existing_columns = get_existing_columns(cur)

            # Gewünschte Spalten aufbauen (mit Spezialbehandlung für angelegt/anlage_wann → letzter_kontakt)
            # Spalten zu ignorieren/filtern
            columns_to_remove = {'adresse', 'strasse', 'hausnummer', 'plz'}
            
            desired_columns = {}
            for col_name, data_type in zip(column_names, data_types):
                if pd.notna(col_name) and col_name != 'Spaltenname':
                    raw_clean_name = sanitize_column_name(col_name)
                    
                    # Überspringe zu entfernende Spalten
                    if raw_clean_name in columns_to_remove:
                        continue

                    # Spezieller Mapping-Fall: alte Spalte "angelegt_wann"/"anlage_wann" wird zukünftig
                    # als "letzter_kontakt" geführt.
                    if raw_clean_name in ["angelegt_wann", "anlage_wann"]:
                        clean_name = "letzter_kontakt"
                    else:
                        clean_name = raw_clean_name

                    pg_type = map_excel_type_to_postgres(data_type)
                    desired_columns[clean_name] = pg_type
            
            # Stelle sicher, dass "gehaltswunsch" immer als INTEGER definiert ist
            desired_columns["gehaltswunsch"] = "INTEGER"

            # Falls die alte Spalte noch existiert, in der DB umbenennen, damit Daten erhalten bleiben
            renamed = False
            if "angelegt_wann" in existing_columns and "letzter_kontakt" in desired_columns:
                print("   Benenne Spalte 'angelegt_wann' in 'letzter_kontakt' um...")
                cur.execute("ALTER TABLE candidates RENAME COLUMN angelegt_wann TO letzter_kontakt;")
                conn.commit()
                renamed = True
            elif "anlage_wann" in existing_columns and "letzter_kontakt" in desired_columns:
                print("   Benenne Spalte 'anlage_wann' in 'letzter_kontakt' um...")
                cur.execute("ALTER TABLE candidates RENAME COLUMN anlage_wann TO letzter_kontakt;")
                conn.commit()
                renamed = True

            if renamed:
                # Nach dem Umbenennen Spalteninformationen neu laden
                existing_columns = get_existing_columns(cur)
            
            # Schemas vergleichen
            neue_spalten, wegfallende_spalten, geaenderte_typen = compare_schemas(
                existing_columns, desired_columns
            )
            
            # Ausgabe der Unterschiede
            has_changes = neue_spalten or wegfallende_spalten or geaenderte_typen
            
            if not has_changes:
                print("✓ Tabellenstruktur ist aktuell - keine Änderungen erforderlich")
                return
            
            print("⚠ Folgende Abweichungen wurden gefunden:\n")
            
            if neue_spalten:
                print(f"  NEUE SPALTEN ({len(neue_spalten)}):")
                for col_name, col_type in neue_spalten.items():
                    print(f"    + {col_name:30s} {col_type}")
                print()
            
            if wegfallende_spalten:
                print(f"  WEGFALLENDE SPALTEN ({len(wegfallende_spalten)}):")
                for col_name in wegfallende_spalten:
                    print(f"    - {col_name}")
                print()
            
            if geaenderte_typen:
                print(f"  GEÄNDERTE TYPEN ({len(geaenderte_typen)}):")
                for col_name, types in geaenderte_typen.items():
                    print(f"    ≠ {col_name:30s} {types['alt']} → {types['neu']}")
                print()
            
            # Warnung bei wegfallenden Spalten
            if wegfallende_spalten:
                print("⚠ WARNUNG: Die Inhalte in den wegfallenden Spalten werden gelöscht!")
                print()
            
            # Bestätigung einholen
            antwort = input("Möchten Sie den Aufbau der Tabelle ändern? (j/n): ").strip().lower()
            if antwort not in ['j', 'ja', 'y', 'yes']:
                print("✓ Abgebrochen. Tabelle bleibt unverändert.")
                return
            
            # Tabelle anpassen
            alter_table_structure(conn, neue_spalten, wegfallende_spalten, geaenderte_typen)
            print("\n✓ Tabellenstruktur erfolgreich angepasst")
            return
        
        # Neue Tabelle erstellen
        print("   Erstelle CREATE TABLE Statement...")
        
        # Spalten zu ignorieren/filtern
        columns_to_remove = {'adresse', 'strasse', 'hausnummer', 'plz'}
        
        create_columns = []
        for i, (col_name, data_type) in enumerate(zip(column_names, data_types)):
            if pd.notna(col_name) and col_name != 'Spaltenname':
                raw_clean_col_name = sanitize_column_name(col_name)
                
                # Überspringe zu entfernende Spalten
                if raw_clean_col_name in columns_to_remove:
                    print(f"   ⊘ Ignoriere Spalte: {col_name} (wird entfernt)")
                    continue

                # Mapping: angelegt/anlage_wann → letzter_kontakt
                if raw_clean_col_name in ["angelegt_wann", "anlage_wann"]:
                    clean_col_name = "letzter_kontakt"
                else:
                    clean_col_name = raw_clean_col_name
                pg_type = map_excel_type_to_postgres(data_type)
                
                # ID als Primary Key
                if col_name == 'ID':
                    create_columns.append(f'    {clean_col_name} {pg_type} PRIMARY KEY')
                # miniCRM-ID als UNIQUE
                elif col_name == 'miniCRM-ID':
                    create_columns.append(f'    {clean_col_name} {pg_type} UNIQUE')
                else:
                    create_columns.append(f'    {clean_col_name} {pg_type}')

        # Helper-Funktion zum Extrahieren des Spaltennamens
        def _extract_col_name(col_def: str) -> str:
            return col_def.strip().split()[0] if col_def.strip() else ""

        # Spaltenreordering und Einfügen neuer Spalten
        names = [_extract_col_name(c) for c in create_columns]
        
        # 1. "letzter_kontakt" zwischen "status_expired_set" und "current_status_interview" einsortieren
        if "letzter_kontakt" in names and "status_expired_set" in names and "current_status_interview" in names:
            lk_idx = names.index("letzter_kontakt")
            se_idx = names.index("status_expired_set")
            csi_idx = names.index("current_status_interview")
            
            # Wenn nicht schon zwischen den beiden, verschieben
            if lk_idx != se_idx + 1 or csi_idx != se_idx + 2:
                lk_def = create_columns.pop(lk_idx)
                names = [_extract_col_name(c) for c in create_columns]
                se_idx = names.index("status_expired_set")
                create_columns.insert(se_idx + 1, lk_def)
        
        # 2. "gehaltswunsch" zwischen "department" und "short_note" einfügen (falls noch nicht vorhanden)
        names = [_extract_col_name(c) for c in create_columns]
        if "gehaltswunsch" not in names and "department" in names and "short_note" in names:
            dept_idx = names.index("department")
            create_columns.insert(dept_idx + 1, "    gehaltswunsch INTEGER")
            print("   + Füge neue Spalte hinzu: gehaltswunsch (INTEGER)")
        elif "gehaltswunsch" in names and "department" in names and "short_note" in names:
            # Falls "gehaltswunsch" existiert, richtig positionieren
            gw_idx = names.index("gehaltswunsch")
            dept_idx = names.index("department")
            if gw_idx != dept_idx + 1:
                gw_def = create_columns.pop(gw_idx)
                names = [_extract_col_name(c) for c in create_columns]
                dept_idx = names.index("department")
                create_columns.insert(dept_idx + 1, gw_def)
        
        create_statement = f"""
CREATE TABLE candidates (
{',\n'.join(create_columns)}
);
        """
        
        print("\n--- CREATE TABLE Statement ---")
        print(create_statement)
        print("--- Ende Statement ---\n")
        
        # Führe CREATE TABLE aus
        cur.execute(create_statement)
        conn.commit()
        
        print("✓ Tabelle 'candidates' erstellt")
        print("✓ minicrm_id als UNIQUE definiert")
        
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


def insert_example_candidate(conn):
    """
    Fügt den Beispiel-Kandidaten aus der Excel-Datei ein.
    """
    print("\n=== Füge Beispiel-Kandidaten ein ===\n")
    
    # Lese Schema
    column_names, data_types, example_row, _ = read_candidates_schema()
    
    with conn.cursor() as cur:
        # Prüfe ob bereits Kandidaten vorhanden sind
        cur.execute("SELECT COUNT(*) FROM candidates;")
        existing_count = cur.fetchone()[0]
        
        if existing_count > 0:
            print(f"⚠ Es sind bereits {existing_count} Kandidaten in der Datenbank")
            antwort = input("Möchten Sie trotzdem den Beispiel-Kandidaten hinzufügen? (j/n): ").strip().lower()
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
            INSERT INTO candidates ({columns_str})
            VALUES ({placeholders})
            RETURNING id;
        """
        
        try:
            cur.execute(insert_sql, values)
            candidate_id = cur.fetchone()[0]
            conn.commit()
            
            print(f"✓ Beispiel-Kandidat eingefügt: ID = {candidate_id}")
            
            # Zeige eingefügte Daten
            print("\n=== Eingefügter Kandidat ===\n")
            cur.execute("SELECT * FROM candidates WHERE id = %s;", (candidate_id,))
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
    Zeigt Informationen über die Candidates-Tabelle.
    """
    print("\n=== Tabellen-Information ===\n")
    
    with conn.cursor() as cur:
        # Spalten-Info
        cur.execute("""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'candidates'
            ORDER BY ordinal_position;
        """)
        
        print("Spalten:")
        for col_name, data_type, max_length in cur.fetchall():
            type_str = f"{data_type}"
            if max_length:
                type_str += f"({max_length})"
            print(f"  - {col_name:30s} {type_str}")
        
        # Anzahl Einträge
        cur.execute("SELECT COUNT(*) FROM candidates;")
        count = cur.fetchone()[0]
        print(f"\n✓ Anzahl Kandidaten: {count}")


def main():
    """Hauptfunktion"""
    print("=" * 80)
    print("Candidates-Tabelle erstellen")
    print("=" * 80)
    
    try:
        # Verbindung herstellen
        print("\n=== Datenbankverbindung ===\n")
        with psycopg.connect(**DB_CONFIG, connect_timeout=10) as conn:
            print("✓ Verbindung zu PostgreSQL hergestellt")
            
            # Tabelle erstellen
            create_candidates_table(conn)
            
            # Beispiel-Kandidaten einfügen
            antwort = input("\nMöchten Sie den Beispiel-Kandidaten einfügen? (j/n): ").strip().lower()
            if antwort in ['j', 'ja', 'y', 'yes']:
                insert_example_candidate(conn)
            
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
