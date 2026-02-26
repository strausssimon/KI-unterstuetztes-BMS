""" 
====================================================
Programmname : Constraints prüfen und korrigieren
Beschreibung : Prüft und korrigiert Constraints für die candidates-Tabelle
- ID muss PRIMARY KEY sein
- miniCRM-ID muss UNIQUE sein

====================================================
"""


import psycopg
from psycopg import sql

def check_and_fix_constraints():
    """
    Prüft und korrigiert die Constraints der candidates-Tabelle.
    """
    print("=" * 80)
    print("Candidates-Tabelle: Constraint-Prüfung und -Korrektur")
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
        with psycopg.connect(**conn_params, connect_timeout=10) as conn:
            print("\n✓ Verbindung zu PostgreSQL hergestellt\n")
            
            with conn.cursor() as cur:
                # Prüfe ob Tabelle existiert
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'candidates'
                    );
                """)
                
                if not cur.fetchone()[0]:
                    print("✗ Tabelle 'candidates' existiert nicht!")
                    print("Bitte führen Sie zuerst 'new_table_candidates.py' aus.")
                    return
                
                print("=== Prüfe bestehende Constraints ===\n")
                
                # Hole alle Constraints
                cur.execute("""
                    SELECT 
                        tc.constraint_name,
                        tc.constraint_type,
                        kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu 
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                    WHERE tc.table_name = 'candidates'
                    ORDER BY tc.constraint_type, kcu.column_name;
                """)
                
                existing_constraints = {}
                for constraint_name, constraint_type, column_name in cur.fetchall():
                    if column_name not in existing_constraints:
                        existing_constraints[column_name] = []
                    existing_constraints[column_name].append({
                        'name': constraint_name,
                        'type': constraint_type
                    })
                
                # Zeige bestehende Constraints
                if existing_constraints:
                    print("Bestehende Constraints:")
                    for col, constraints in existing_constraints.items():
                        for c in constraints:
                            print(f"  - {col:20s} {c['type']:15s} ({c['name']})")
                else:
                    print("⚠ Keine Constraints gefunden")
                
                print("\n" + "=" * 80)
                print("Prüfe erforderliche Constraints")
                print("=" * 80 + "\n")
                
                changes_made = False
                
                # 1. Prüfe ID (PRIMARY KEY)
                id_has_pk = any(
                    c['type'] == 'PRIMARY KEY' 
                    for c in existing_constraints.get('id', [])
                )
                
                if id_has_pk:
                    print("✓ ID hat PRIMARY KEY Constraint")
                else:
                    print("⚠ ID hat KEINEN PRIMARY KEY Constraint")
                    
                    # Prüfe ob ID Spalte existiert
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'candidates' 
                            AND column_name = 'id'
                        );
                    """)
                    
                    if cur.fetchone()[0]:
                        antwort = input("\nMöchten Sie ID als PRIMARY KEY setzen? (j/n): ").strip().lower()
                        if antwort in ['j', 'ja', 'y', 'yes']:
                            try:
                                print("  → Setze PRIMARY KEY auf ID...")
                                cur.execute("ALTER TABLE candidates ADD PRIMARY KEY (id);")
                                conn.commit()
                                print("  ✓ PRIMARY KEY für ID gesetzt")
                                changes_made = True
                            except Exception as e:
                                print(f"  ✗ Fehler: {e}")
                                print("  ℹ Möglicherweise existieren Duplikate in der ID-Spalte")
                    else:
                        print("  ✗ ID-Spalte existiert nicht!")
                
                # 2. Prüfe minicrm_id (UNIQUE)
                print()
                minicrm_has_unique = any(
                    c['type'] in ['UNIQUE', 'PRIMARY KEY'] 
                    for c in existing_constraints.get('minicrm_id', [])
                )
                
                if minicrm_has_unique:
                    print("✓ minicrm_id hat UNIQUE Constraint")
                else:
                    print("⚠ minicrm_id hat KEINEN UNIQUE Constraint")
                    
                    # Prüfe ob minicrm_id Spalte existiert
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'candidates' 
                            AND column_name = 'minicrm_id'
                        );
                    """)
                    
                    if cur.fetchone()[0]:
                        # Prüfe auf Duplikate
                        cur.execute("""
                            SELECT minicrm_id, COUNT(*) 
                            FROM candidates 
                            WHERE minicrm_id IS NOT NULL
                            GROUP BY minicrm_id 
                            HAVING COUNT(*) > 1;
                        """)
                        
                        duplicates = cur.fetchall()
                        
                        if duplicates:
                            print(f"\n  ⚠ WARNUNG: {len(duplicates)} Duplikate in minicrm_id gefunden!")
                            print("  Duplikate müssen vor dem Setzen des UNIQUE Constraints bereinigt werden:")
                            for minicrm_id, count in duplicates[:5]:
                                print(f"    - {minicrm_id}: {count}x vorhanden")
                            if len(duplicates) > 5:
                                print(f"    ... und {len(duplicates) - 5} weitere")
                            print("\n  Sie müssen die Duplikate manuell bereinigen.")
                        else:
                            antwort = input("\nMöchten Sie UNIQUE Constraint für minicrm_id setzen? (j/n): ").strip().lower()
                            if antwort in ['j', 'ja', 'y', 'yes']:
                                try:
                                    print("  → Erstelle UNIQUE Constraint für minicrm_id...")
                                    cur.execute("""
                                        ALTER TABLE candidates 
                                        ADD CONSTRAINT unique_minicrm_id UNIQUE (minicrm_id);
                                    """)
                                    conn.commit()
                                    print("  ✓ UNIQUE Constraint für minicrm_id gesetzt")
                                    changes_made = True
                                except Exception as e:
                                    print(f"  ✗ Fehler: {e}")
                    else:
                        print("  ℹ minicrm_id-Spalte existiert nicht")
                        print("  Führen Sie 'new_table_candidates.py' aus um die Spalte hinzuzufügen")
                
                print("\n" + "=" * 80)
                if changes_made:
                    print("✓ Änderungen erfolgreich durchgeführt!")
                else:
                    print("ℹ Keine Änderungen erforderlich oder durchgeführt")
                print("=" * 80)
                
                # Zeige finale Constraint-Übersicht
                print("\n=== Finale Constraint-Übersicht ===\n")
                cur.execute("""
                    SELECT 
                        tc.constraint_name,
                        tc.constraint_type,
                        kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu 
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                    WHERE tc.table_name = 'candidates'
                    ORDER BY tc.constraint_type, kcu.column_name;
                """)
                
                constraints = cur.fetchall()
                if constraints:
                    for constraint_name, constraint_type, column_name in constraints:
                        print(f"  {column_name:20s} {constraint_type:15s} ({constraint_name})")
                else:
                    print("  Keine Constraints gefunden")
                
    except psycopg.Error as e:
        print(f"\n✗ Datenbankfehler: {e}")
        print("\nStellen Sie sicher, dass:")
        print("  1. Docker läuft (docker-start.bat)")
        print("  2. PostgreSQL Container aktiv ist")
    except Exception as e:
        print(f"\n✗ Fehler: {e}")
        raise


if __name__ == "__main__":
    check_and_fix_constraints()
