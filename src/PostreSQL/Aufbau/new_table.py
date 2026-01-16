import psycopg
from psycopg import sql

def insert_beispiel_bewerber():
    """Fügt Beispieleinträge in die Bewerber-Tabelle ein"""
    
    # Verbindungsparameter
    conn_params = {
        'host': 'localhost',
        'port': 5432,
        'dbname': 'postgres',
        'user': 'postgres',
        'password': 'bigdataconsulting'
    }
    
    # Beispieldaten
    bewerber_daten = [
        ('Müller', 'Anna', 'Software Engineer', 'Hauptstraße 123, 10115 Berlin'),
        ('Schmidt', 'Thomas', 'Data Scientist', 'Musterweg 45, 80331 München'),
        ('Weber', 'Lisa', 'Product Manager', 'Seestraße 78, 22767 Hamburg'),
        ('Meyer', 'Jonas', 'Frontend Developer', 'Lindenallee 56, 50667 Köln'),
        ('Fischer', 'Sarah', 'DevOps Engineer', 'Bahnhofstraße 12, 60329 Frankfurt'),
        ('Schneider', 'Michael', 'IT Consultant', 'Parkweg 89, 70173 Stuttgart'),
        ('Becker', 'Julia', 'UX Designer', 'Rosenstraße 34, 04109 Leipzig'),
        ('Wagner', 'Daniel', 'System Administrator', 'Bergstraße 67, 30159 Hannover'),
        ('Koch', 'Nina', 'Business Analyst', 'Waldweg 45, 01067 Dresden'),
        ('Hoffmann', 'Felix', 'Cloud Architect', 'Seeweg 23, 24103 Kiel')
    ]
    
    try:
        # Verbindung herstellen
        with psycopg.connect(**conn_params) as conn:
            with conn.cursor() as cur:
                
                # Prüfe ob bereits Bewerber vorhanden sind
                cur.execute("SELECT COUNT(*) FROM bewerber;")
                existing_count = cur.fetchone()[0]
                
                if existing_count > 0:
                    print(f"=== Es sind bereits {existing_count} Bewerber in der Datenbank ===\n")
                    antwort = input("Möchten Sie weitere Beispiel-Bewerber hinzufügen? (j/n): ").strip().lower()
                    if antwort not in ['j', 'ja', 'y', 'yes']:
                        print("\n✓ Keine neuen Bewerber hinzugefügt.")
                        print("\n=== Alle Bewerber in der Datenbank ===\n")
                        cur.execute("""
                            SELECT id, nachname, vorname, beruf, adresse 
                            FROM bewerber 
                            ORDER BY id;
                        """)
                        for row in cur.fetchall():
                            print(f"ID {row[0]}: {row[2]} {row[1]} - {row[3]}")
                            print(f"         Adresse: {row[4]}\n")
                        return
                else:
                    print("=== Die Bewerber-Tabelle ist leer ===\n")
                    antwort = input("Möchten Sie 10 Beispiel-Bewerber anlegen? (j/n): ").strip().lower()
                    if antwort not in ['j', 'ja', 'y', 'yes']:
                        print("\n✓ Abgebrochen. Keine Bewerber hinzugefügt.")
                        return
                
                print("\n=== Füge Beispiel-Bewerber hinzu ===\n")
                
                # Bewerber einfügen
                for nachname, vorname, beruf, adresse in bewerber_daten:
                    cur.execute("""
                        INSERT INTO bewerber (nachname, vorname, beruf, adresse)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id;
                    """, (nachname, vorname, beruf, adresse))
                    
                    bewerber_id = cur.fetchone()[0]
                    print(f"✓ Bewerber hinzugefügt: ID={bewerber_id}, {vorname} {nachname} - {beruf}")
                
                # Commit
                conn.commit()
                
                # Alle Bewerber anzeigen
                print("\n=== Alle Bewerber in der Datenbank ===\n")
                cur.execute("""
                    SELECT id, nachname, vorname, beruf, adresse 
                    FROM bewerber 
                    ORDER BY id;
                """)
                
                for row in cur.fetchall():
                    print(f"ID {row[0]}: {row[2]} {row[1]} - {row[3]}")
                    print(f"         Adresse: {row[4]}\n")
                
                # Statistik
                cur.execute("SELECT COUNT(*) FROM bewerber;")
                total = cur.fetchone()[0]
                print(f"\n✓ Gesamt: {total} Bewerber in der Datenbank")
                
    except psycopg.Error as e:
        print(f"✗ Fehler beim Einfügen der Daten: {e}")
        raise

if __name__ == "__main__":
    insert_beispiel_bewerber()