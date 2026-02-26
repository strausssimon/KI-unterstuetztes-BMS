""" 
====================================================
Programmname : Ollama-Testskript
Beschreibung : Prüft, ob Ollama läuft und testet mit einem Prompt

====================================================
"""
import sys
import os
# Füge Projekt-Root zum Python-Pfad hinzu
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

import requests
import json
import psycopg
from src.db_config import DB_CONFIG

def check_ollama_running():
    """
    Prüft, ob Ollama auf dem System läuft.
    """
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            print("✓ Ollama läuft und ist erreichbar")
            models = response.json().get('models', [])
            if models:
                print(f"✓ Verfügbare Modelle: {', '.join([m['name'] for m in models])}")
                return True, models
            else:
                print("⚠ Keine Modelle installiert")
                return True, []
        else:
            print(f"✗ Ollama antwortet mit Status {response.status_code}")
            return False, []
    except requests.exceptions.ConnectionError:
        print("✗ Ollama ist nicht erreichbar (läuft der Server?)")
        return False, []
    except Exception as e:
        print(f"✗ Fehler beim Verbinden mit Ollama: {e}")
        return False, []

def test_ollama_prompt(model="phi3:mini", prompt="Beantworte die folgende Frage NUR mit einem einzigen Wort (1 Wort), ohne Zusatz, ohne Satzzeichen, ohne Erklärung: Frage: Wo steht der schiefe Turm von Pisa?!"):
    """
    Testet Ollama mit einem einfachen Prompt.
    """
    url = "http://localhost:11434/api/generate"
    
    data = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    
    print(f"\n📝 Sende Prompt an Ollama (Modell: {model})...")
    print(f"Frage: {prompt}\n")
    
    try:
        response = requests.post(url, json=data, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            answer = result.get('response', '')
            print("🤖 Antwort von Ollama:")
            print("-" * 60)
            print(answer)
            print("-" * 60)
            
            # Zusätzliche Informationen
            if 'total_duration' in result:
                duration_sec = result['total_duration'] / 1_000_000_000
                print(f"\n⏱ Antwortzeit: {duration_sec:.2f} Sekunden")
            
            return True
        else:
            print(f"✗ Fehler: Status {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("✗ Timeout: Ollama hat nicht rechtzeitig geantwortet")
        return False
    except Exception as e:
        print(f"✗ Fehler beim Senden des Prompts: {e}")
        return False


def check_postgres_pgvector():
    """Prüft, ob PostgreSQL erreichbar ist und pgvector installiert ist."""

    print("\n" + "=" * 60)
    print("PostgreSQL / pgvector Test")
    print("=" * 60 + "\n")

    # Verbindung testen
    try:
        with psycopg.connect(**DB_CONFIG, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]
                cur.execute("SELECT current_database();")
                current_db = cur.fetchone()[0]
                print(f"✓ PostgreSQL erreichbar")
                print(f"  Version: {version}")
                print(f"  Datenbank: {current_db}\n")

                # pgvector-Extension prüfen
                cur.execute(
                    """
                    SELECT extname, extversion
                    FROM pg_extension
                    WHERE extname = 'vector';
                    """
                )
                row = cur.fetchone()
                if row:
                    print(f"✓ pgvector Extension installiert (Version {row[1]})\n")
                    return True, True
                else:
                    print("⚠ PostgreSQL läuft, aber pgvector (Extension 'vector') ist nicht installiert")
                    print("  Versuche, die Extension automatisch zu erstellen...")

                    try:
                        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                        conn.commit()

                        cur.execute(
                            """
                            SELECT extname, extversion
                            FROM pg_extension
                            WHERE extname = 'vector';
                            """
                        )
                        row2 = cur.fetchone()
                        if row2:
                            print(f"✓ pgvector Extension wurde installiert (Version {row2[1]})\n")
                            return True, True
                        else:
                            print("✗ Konnte pgvector nicht verifizieren, obwohl CREATE EXTENSION ausgeführt wurde.\n")
                            return True, False
                    except Exception as e:
                        print(f"✗ Fehler beim automatischen Erstellen der pgvector-Extension: {e}\n")
                        print("  Bitte führen Sie ggf. manuell aus:")
                        print("  docker exec postgres_pgvector psql -U postgres -d postgres -c \"CREATE EXTENSION IF NOT EXISTS vector;\"\n")
                        return True, False

    except psycopg.OperationalError as e:
        print("✗ Verbindungsfehler zu PostgreSQL:")
        print(f"  {e}\n")
        print("Bitte prüfen Sie, ob der PostgreSQL-/Docker-Container läuft und die Zugangsdaten stimmen.")
        return False, False
    except Exception as e:
        print(f"✗ Unerwarteter Fehler beim PostgreSQL/pgvector-Test: {e}\n")
        return False, False

def main():
    print("=" * 60)
    print("Ollama Test")
    print("=" * 60)
    
    # Prüfe ob Ollama läuft
    is_running, models = check_ollama_running()
    
    if not is_running:
        print("\n❌ Ollama ist nicht verfügbar. Bitte starten Sie Ollama.")
        sys.exit(1)
    
    if not models:
        print("\n❌ Keine Modelle verfügbar. Bitte installieren Sie ein Modell:")
        print("   Beispiel: ollama pull phi3:mini")
        sys.exit(1)
    
    # Prüfe ob phi3:mini verfügbar ist
    model_name = "phi3:mini"
    available_model_names = [m['name'] for m in models]
    
    if model_name not in available_model_names:
        print(f"\n⚠ Bevorzugtes Modell '{model_name}' nicht gefunden")
        print(f"   Verfügbare Modelle: {', '.join(available_model_names)}")
        print(f"   Verwende stattdessen: {available_model_names[0]}")
        print(f"\n   Zum Installieren von phi3:mini:")
        print(f"   ollama pull phi3:mini\n")
        model_name = available_model_names[0]
    
    # Test PostgreSQL + pgvector
    db_ok, pgvector_ok = check_postgres_pgvector()

    if not db_ok:
        print("\n❌ PostgreSQL ist nicht erreichbar. Bitte Umgebung prüfen.")
        sys.exit(1)

    if not pgvector_ok:
        print("\n❌ pgvector ist nicht installiert oder nicht verfügbar.")
        sys.exit(1)

    # Test-Prompt
    success = test_ollama_prompt(
        model=model_name,
        prompt="Wo steht der schiefe turm von Pisa?"
    )
    
    if success:
        print("\n✅ Ollama-Test erfolgreich abgeschlossen!")
    else:
        print("\n❌ Ollama-Test fehlgeschlagen")
        sys.exit(1)

if __name__ == "__main__":
    main()
