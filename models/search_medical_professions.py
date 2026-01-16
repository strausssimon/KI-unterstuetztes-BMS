"""
Interaktives Suchskript für medizinische Berufsbezeichnungen in pgvector.
Verwendet nomic-embed-text für Embeddings und phi3:mini für Erklärungen.
"""

import sys
import requests
import psycopg
from typing import List, Tuple

# Datenbankverbindung
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'postgres',
    'user': 'postgres',
    'password': 'bigdataconsulting'
}

# Ollama Konfiguration
OLLAMA_URL = "http://localhost:11434"
EMBEDDING_MODEL = "nomic-embed-text"
LLM_MODEL = "phi3:mini"


def check_ollama_models():
    """
    Prüft ob Ollama läuft und die benötigten Modelle verfügbar sind.
    """
    print("=== Prüfe Ollama ===")
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            model_names = [m['name'] for m in models]
            
            print(f"✓ Ollama läuft")
            print(f"✓ Verfügbare Modelle: {', '.join(model_names)}")
            
            # Prüfe benötigte Modelle
            has_embedding = EMBEDDING_MODEL in model_names or f"{EMBEDDING_MODEL}:latest" in model_names
            has_llm = LLM_MODEL in model_names or f"{LLM_MODEL}:latest" in model_names or "phi3:mini" in model_names
            
            if not has_embedding:
                print(f"\n✗ Embedding-Modell '{EMBEDDING_MODEL}' nicht gefunden!")
                print(f"   Installieren: ollama pull {EMBEDDING_MODEL}")
                return False
            
            if not has_llm:
                print(f"\n✗ LLM-Modell '{LLM_MODEL}' nicht gefunden!")
                print(f"   Installieren: ollama pull {LLM_MODEL}")
                return False
            
            print(f"✓ Alle benötigten Modelle verfügbar\n")
            return True
        else:
            print(f"✗ Ollama antwortet mit Status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Ollama nicht erreichbar: {e}")
        print("   Starten Sie Ollama")
        return False


def get_embedding(text: str) -> List[float]:
    """
    Erstellt ein Embedding für den Text mit Ollama.
    """
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={
                "model": EMBEDDING_MODEL,
                "prompt": text.replace("\n", " ").strip()
            },
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()['embedding']
        else:
            raise RuntimeError(f"Embedding fehlgeschlagen: Status {response.status_code}")
    except Exception as e:
        print(f"[FEHLER] Embedding-Erstellung: {e}")
        raise


def search_text(conn, query: str, limit: int = 5) -> List[Tuple]:
    """
    Textbasierte Suche (Fallback ohne Embeddings).
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                title,
                category,
                description,
                NULL AS similarity
            FROM medical_professions
            WHERE title ILIKE %s OR description ILIKE %s
            LIMIT %s;
        """, (f'%{query}%', f'%{query}%', limit))
        
        results = cur.fetchall()
    
    return results


def check_embeddings_diversity(conn):
    """
    Prüft ob die Embeddings unterschiedlich sind.
    """
    with conn.cursor() as cur:
        # Hole erste 3 Embeddings
        cur.execute("""
            SELECT title, embedding
            FROM medical_professions
            WHERE embedding IS NOT NULL
            LIMIT 3;
        """)
        
        results = cur.fetchall()
        
        if len(results) < 2:
            return False
        
        # Vergleiche ob sie unterschiedlich sind
        first_embedding = results[0][1]
        different = False
        
        for title, embedding in results[1:]:
            if embedding != first_embedding:
                different = True
                break
        
        return different


def search_professions(conn, query: str, limit: int = 5) -> List[Tuple]:
    """
    Sucht ähnliche Berufsbezeichnungen in der Datenbank.
    """
    print(f"\n🔍 Suche nach: '{query}'")
    
    # 1. Prüfe zuerst Textsuche
    text_results = search_text(conn, query, limit=3)
    if text_results:
        print(f"   ℹ️  Exakte Textübereinstimmungen gefunden: {len(text_results)}")
        for title, _, _, _ in text_results:
            print(f"      - {title}")
    
    # 2. Vektorsuche
    print("   Erstelle Embedding...")
    query_embedding = get_embedding(query)
    
    print(f"   Embedding-Dimension: {len(query_embedding)}")
    print("   Suche in Datenbank...")
    
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                title,
                category,
                description,
                1 - (embedding <=> %s::vector) AS similarity
            FROM medical_professions
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """, (query_embedding, query_embedding, limit))
        
        results = cur.fetchall()
    
    return results


def explain_with_llm(query: str, results: List[Tuple]) -> str:
    """
    Lässt phi3:mini die Suchergebnisse erklären.
    """
    # Baue Kontext aus Suchergebnissen
    results_text = "\n".join([
        f"- {title} ({category}): {description[:100]}..."
        for title, category, description, _ in results[:3]
    ])
    
    prompt = f"""Du bist ein medizinischer Assistent. Ein Benutzer hat nach "{query}" gesucht.

Die relevantesten medizinischen Berufsbezeichnungen sind:
{results_text}

Erkläre in 2-3 Sätzen auf Deutsch, welche dieser Fachrichtungen am besten zur Suchanfrage passen und warum."""
    
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": LLM_MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )
        
        if response.status_code == 200:
            return response.json().get('response', '')
        else:
            return "[Erklärung nicht verfügbar]"
    except Exception as e:
        return f"[Fehler bei Erklärung: {e}]"


def display_results(query: str, results: List[Tuple], show_explanation: bool = True):
    """
    Zeigt die Suchergebnisse formatiert an.
    """
    if not results:
        print("\n❌ Keine Ergebnisse gefunden.")
        return
    
    # Prüfe ob alle Ähnlichkeiten identisch sind (Problem!)
    similarities = [sim for _, _, _, sim in results if sim is not None]
    if len(similarities) > 1 and len(set(similarities)) == 1:
        print("\n⚠️  WARNUNG: Alle Ähnlichkeiten sind identisch!")
        print("   Das deutet auf ein Problem mit den Embeddings hin.")
        print("   Möglicherweise wurden sie nicht korrekt gespeichert.\n")
    
    print(f"\n✓ {len(results)} Ergebnisse gefunden:")
    print("=" * 80)
    
    for i, (title, category, description, similarity) in enumerate(results, 1):
        print(f"\n{i}. {title}")
        print(f"   Kategorie: {category}")
        print(f"   Ähnlichkeit: {similarity:.4f} ({similarity*100:.1f}%)")
        print(f"   {description}")
    
    print("\n" + "=" * 80)
    
    # Optionale LLM-Erklärung
    if show_explanation and results:
        print("\n💡 KI-Erklärung (phi3:mini):")
        print("-" * 80)
        explanation = explain_with_llm(query, results)
        print(explanation)
        print("-" * 80)


def interactive_search(conn):
    """
    Interaktive Suchschleife.
    """
    print("\n" + "=" * 80)
    print("Interaktive Suche in medizinischen Berufsbezeichnungen")
    print("=" * 80)
    print("\nBefehle:")
    print("  - Geben Sie einen Suchbegriff ein (z.B. 'Herz', 'Kinder', 'Chirurgie')")
    print("  - 'exit' oder 'quit' zum Beenden")
    print("  - 'help' für diese Hilfe")
    print("=" * 80)
    
    while True:
        try:
            query = input("\n🔍 Suche> ").strip()
            
            if not query:
                continue
            
            # Befehle
            if query.lower() in ['exit', 'quit', 'q']:
                print("\nAuf Wiedersehen!")
                break
            
            if query.lower() in ['help', 'hilfe', '?']:
                print("\nHilfe:")
                print("  Geben Sie medizinische Begriffe ein, z.B.:")
                print("    - 'Herz und Kreislauf'")
                print("    - 'Kinder'")
                print("    - 'Chirurgie'")
                print("    - 'Haut'")
                continue
            
            # Suche durchführen
            results = search_professions(conn, query, limit=5)
            display_results(query, results, show_explanation=True)
            
        except KeyboardInterrupt:
            print("\n\nUnterbrochen. Auf Wiedersehen!")
            break
        except Exception as e:
            print(f"\n[FEHLER] {e}")


def main():
    """Hauptfunktion"""
    print("=" * 80)
    print("Medizinische Berufsbezeichnungen - Suchsystem")
    print("=" * 80)
    
    # 1. Prüfe Ollama
    if not check_ollama_models():
        print("\n❌ Benötigte Ollama-Modelle nicht verfügbar!")
        sys.exit(1)
    
    # 2. Verbinde mit Datenbank
    print("=== Datenbankverbindung ===")
    try:
        conn = psycopg.connect(**DB_CONFIG, connect_timeout=10)
        print("✓ Verbindung zu PostgreSQL hergestellt\n")
    except Exception as e:
        print(f"✗ Datenbankverbindung fehlgeschlagen: {e}")
        print("\nStellen Sie sicher, dass:")
        print("  1. Docker läuft (docker-start.bat)")
        print("  2. PostgreSQL Container aktiv ist")
        print("  3. Tabelle 'medical_professions' existiert")
        sys.exit(1)
    
    try:
        # 3. Prüfe ob Daten vorhanden sind
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM medical_professions;")
            count = cur.fetchone()[0]
            
            if count == 0:
                print("⚠ Keine Daten in der Datenbank!")
                print("   Führen Sie zuerst aus: python models\\load_medical_professions.py")
                sys.exit(1)
            
            print(f"✓ {count} medizinische Berufsbezeichnungen verfügbar")
        
        # 4. Prüfe Embedding-Qualität
        print("   Prüfe Embedding-Diversität...")
        if not check_embeddings_diversity(conn):
            print("⚠️  WARNUNG: Embeddings scheinen identisch zu sein!")
            print("   Führen Sie load_medical_professions.py erneut aus.\n")
        else:
            print("   ✓ Embeddings sind unterschiedlich\n")
        
        # 5. Starte interaktive Suche
        interactive_search(conn)
        
    finally:
        conn.close()
        print("\nDatenbankverbindung geschlossen")


if __name__ == "__main__":
    main()
