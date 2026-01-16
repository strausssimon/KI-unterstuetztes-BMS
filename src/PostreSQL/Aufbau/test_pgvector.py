import psycopg
import subprocess
import sys
import time

def check_docker_containers():
    """Prüft ob Docker läuft und die Container aktiv sind"""
    print("=== Docker Container Status ===\n")
    
    try:
        # Prüfe ob Docker läuft
        result = subprocess.run(['docker', 'version'], 
                              capture_output=True, 
                              text=True, 
                              timeout=5)
        if result.returncode != 0:
            print("✗ Docker ist nicht gestartet!")
            print("  Bitte starten Sie Docker Desktop.\n")
            return False
        
        print("✓ Docker läuft\n")
        
        # Prüfe PostgreSQL Container
        result = subprocess.run(['docker', 'ps', '--filter', 'name=postgres_pgvector', '--format', '{{.Status}}'],
                              capture_output=True,
                              text=True,
                              timeout=5)
        
        if not result.stdout.strip():
            print("✗ PostgreSQL Container (postgres_pgvector) läuft nicht!")
            print("  Starten Sie die Container mit: docker-start.bat")
            print("  oder: docker-compose up -d\n")
            return False
        
        status = result.stdout.strip()
        if 'Up' in status:
            print(f"✓ PostgreSQL Container läuft: {status}")
            if 'healthy' in status:
                print("✓ PostgreSQL ist healthy und bereit\n")
            else:
                print("⚠ PostgreSQL startet noch... warte 5 Sekunden\n")
                time.sleep(5)
        else:
            print(f"✗ PostgreSQL Container Status: {status}")
            print("  Der Container wird gerade neu gestartet.\n")
            return False
        
        # Prüfe pgAdmin Container (optional)
        result = subprocess.run(['docker', 'ps', '--filter', 'name=pgadmin4', '--format', '{{.Status}}'],
                              capture_output=True,
                              text=True,
                              timeout=5)
        
        if result.stdout.strip() and 'Up' in result.stdout:
            print(f"✓ pgAdmin4 Container läuft (optional): http://localhost:5050\n")
        else:
            print("ℹ pgAdmin4 Container läuft nicht (Sie können die Desktop-Version verwenden)\n")
        
        return True
        
    except subprocess.TimeoutExpired:
        print("✗ Docker-Befehl Timeout")
        return False
    except FileNotFoundError:
        print("✗ Docker ist nicht installiert oder nicht im PATH")
        return False
    except Exception as e:
        print(f"✗ Fehler beim Prüfen der Docker-Container: {e}")
        return False


def test_postgresql_connection():
    """Testet die Verbindung zu PostgreSQL im Docker-Container"""
    
    # Verbindungsparameter für Docker-PostgreSQL
    conn_params = {
        'host': 'localhost',
        'port': 5432,
        'dbname': 'postgres',
        'user': 'postgres',
        'password': 'bigdataconsulting'
    }
    
    print("=== PostgreSQL Verbindungstest ===\n")
    
    try:
        # Verbindung herstellen
        with psycopg.connect(**conn_params, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                
                # 1. PostgreSQL Version
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]
                print(f"✓ PostgreSQL Version:\n  {version}\n")
                
                # 2. Prüfe Database Info
                cur.execute("""
                    SELECT 
                        current_database() as database,
                        current_user as user,
                        inet_server_addr() as host,
                        inet_server_port() as port
                """)
                db_info = cur.fetchone()
                print(f"✓ Verbindung erfolgreich:")
                print(f"  Database: {db_info[0]}")
                print(f"  User: {db_info[1]}")
                print(f"  Port: {db_info[3]}\n")
                
                return True
                
    except psycopg.OperationalError as e:
        print(f"✗ Verbindungsfehler zur Datenbank:")
        print(f"  {e}\n")
        print("Mögliche Ursachen:")
        print("  - PostgreSQL Container läuft nicht")
        print("  - Verbindungsparameter falsch")
        print("  - Port 5432 bereits belegt\n")
        return False
        
    except Exception as e:
        print(f"✗ Unerwarteter Fehler: {e}\n")
        return False


def test_pgvector():
    """Testet pgvector Extension und Funktionalität"""
    
    conn_params = {
        'host': 'localhost',
        'port': 5432,
        'dbname': 'postgres',
        'user': 'postgres',
        'password': 'bigdataconsulting'
    }
    
    print("=== pgvector Extension Test ===\n")
    
    try:
        with psycopg.connect(**conn_params) as conn:
            with conn.cursor() as cur:
                
                # 1. Prüfe ob Extension bereits installiert ist
                cur.execute("""
                    SELECT extname, extversion
                    FROM pg_extension
                    WHERE extname = 'vector';
                """)
                installed = cur.fetchone()
                
                if installed:
                    print(f"✓ pgvector Extension bereits installiert (Version {installed[1]})\n")
                else:
                    # Extension ist noch nicht installiert, prüfe ob verfügbar
                    cur.execute("""
                        SELECT name, default_version
                        FROM pg_available_extensions 
                        WHERE name = 'vector';
                    """)
                    available = cur.fetchone()
                    
                    if not available:
                        print("✗ pgvector Extension nicht verfügbar!")
                        print("  Dies sollte nicht passieren, da Sie das Docker-Image verwenden.\n")
                        return False
                    
                    print(f"⚠ pgvector ist verfügbar (v{available[1]}) aber noch nicht installiert")
                    print("  Installiere Extension...")
                    try:
                        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                        conn.commit()
                        print("✓ Extension erfolgreich installiert!\n")
                    except Exception as e:
                        print(f"✗ Fehler beim Installieren: {e}\n")
                        return False
                
                # 2. Test: Vektor-Operationen
                print("=== pgvector Funktionalitätstest ===\n")
                
                # Lösche alte Test-Tabelle
                cur.execute("DROP TABLE IF EXISTS pgvector_test;")
                
                # Erstelle Test-Tabelle
                cur.execute("""
                    CREATE TABLE pgvector_test (
                        id serial PRIMARY KEY,
                        name text,
                        embedding vector(3)
                    );
                """)
                print("✓ Test-Tabelle erstellt (vector(3))")
                
                # Füge Test-Daten ein
                test_data = [
                    ('Python', '[0.1, 0.2, 0.3]'),
                    ('JavaScript', '[0.4, 0.5, 0.6]'),
                    ('Java', '[0.7, 0.8, 0.9]'),
                    ('C++', '[0.15, 0.25, 0.35]'),
                    ('Ruby', '[0.45, 0.55, 0.65]')
                ]
                
                for name, vector in test_data:
                    cur.execute(
                        "INSERT INTO pgvector_test (name, embedding) VALUES (%s, %s)",
                        (name, vector)
                    )
                print(f"✓ {len(test_data)} Test-Vektoren eingefügt\n")
                
                # Test: L2 Distance Search
                query_vector = '[0.2, 0.3, 0.4]'
                print(f"Test: Similarity Search mit Query-Vektor {query_vector}")
                print("Operator: <-> (L2-Distanz)\n")
                
                cur.execute("""
                    SELECT 
                        name,
                        embedding,
                        embedding <-> %s::vector AS l2_distance,
                        1 - (embedding <=> %s::vector) AS cosine_similarity
                    FROM pgvector_test
                    ORDER BY embedding <-> %s::vector
                    LIMIT 3;
                """, (query_vector, query_vector, query_vector))
                
                print("Top 3 ähnlichste Ergebnisse:")
                print("-" * 70)
                for row in cur.fetchall():
                    print(f"  {row[0]:15} | Vector: {row[1]} | L2: {row[2]:.4f} | Cosine: {row[3]:.4f}")
                print()
                
                # Test: Cosine Distance
                print("Test: Cosine Distance Search")
                cur.execute("""
                    SELECT 
                        name,
                        embedding <=> %s::vector AS cosine_distance
                    FROM pgvector_test
                    ORDER BY embedding <=> %s::vector
                    LIMIT 3;
                """, (query_vector, query_vector))
                
                print("Top 3 nach Cosine-Distanz:")
                for row in cur.fetchall():
                    print(f"  {row[0]:15} | Cosine Distance: {row[1]:.4f}")
                print()
                
                # Test: Inner Product
                print("Test: Inner Product Search")
                cur.execute("""
                    SELECT 
                        name,
                        embedding <#> %s::vector AS inner_product
                    FROM pgvector_test
                    ORDER BY embedding <#> %s::vector DESC
                    LIMIT 3;
                """, (query_vector, query_vector))
                
                print("Top 3 nach Inner Product:")
                for row in cur.fetchall():
                    print(f"  {row[0]:15} | Inner Product: {row[1]:.4f}")
                print()
                
                # Aufräumen
                cur.execute("DROP TABLE pgvector_test;")
                conn.commit()
                
                print("✓ Alle pgvector-Tests erfolgreich!\n")
                return True
                
    except Exception as e:
        print(f"✗ Fehler beim Testen von pgvector: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Hauptfunktion für alle Tests"""
    
    print("\n" + "=" * 70)
    print(" PostgreSQL + pgvector Docker Setup - Systemtest")
    print("=" * 70 + "\n")
    
    # Test 1: Docker Container
    if not check_docker_containers():
        print("\n" + "=" * 70)
        print("✗ FEHLER: Docker-Container nicht bereit")
        print("=" * 70)
        print("\nLösung: Führen Sie 'docker-start.bat' aus oder:")
        print("  docker-compose up -d\n")
        sys.exit(1)
    
    # Test 2: PostgreSQL Verbindung
    if not test_postgresql_connection():
        print("\n" + "=" * 70)
        print("✗ FEHLER: PostgreSQL-Verbindung fehlgeschlagen")
        print("=" * 70 + "\n")
        sys.exit(1)
    
    # Test 3: pgvector Extension
    if not test_pgvector():
        print("\n" + "=" * 70)
        print("✗ FEHLER: pgvector-Tests fehlgeschlagen")
        print("=" * 70 + "\n")
        sys.exit(1)
    
    # Alles erfolgreich!
    print("=" * 70)
    print("✓✓✓ ALLE TESTS ERFOLGREICH! ✓✓✓")
    print("=" * 70)
    print("\nIhr System ist bereit!")
    print("\nNächste Schritte:")
    print("  1. Öffnen Sie pgAdmin4 (Desktop oder http://localhost:5050)")
    print("  2. Verbinden Sie mit:")
    print("     - Host: localhost")
    print("     - Port: 5432")
    print("     - User: postgres")
    print("     - Password: bigdataconsulting")
    print("\n  3. Führen Sie pgvector-demo.sql aus für weitere Beispiele")
    print("\nDatenbank-Management:")
    print("  - Container stoppen: docker-compose stop")
    print("  - Container starten: docker-compose start")
    print("  - Logs anzeigen: docker-compose logs -f postgres\n")


if __name__ == "__main__":
    main()
