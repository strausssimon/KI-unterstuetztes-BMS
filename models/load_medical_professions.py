"""
Skript zum Extrahieren medizinischer Berufsbezeichnungen aus der 
Muster-Weiterbildungsordnung 2018 der Bundesärztekammer und 
Speicherung in pgvector-Datenbank mit Ollama-Embeddings.
"""

import os
import re
import sys
import subprocess
from typing import List, Dict, Tuple
import psycopg
import requests

# PDF Processing
try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False
    print("[WARNUNG] PyPDF2 nicht installiert: pip install PyPDF2")

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False


# Datenbankverbindung konfigurieren
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'postgres',
    'user': 'postgres',
    'password': 'bigdataconsulting'
}

# Ollama Konfiguration
OLLAMA_URL = "http://localhost:11434"
EMBEDDING_MODEL = "nomic-embed-text"  # 768 Dimensionen
EMBEDDING_DIM = 768


def check_ollama_running():
    """
    Prüft, ob Ollama auf dem System läuft.
    """
    print("\n=== Ollama Status ===")
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            print("✓ Ollama läuft und ist erreichbar")
            models = response.json().get('models', [])
            if models:
                model_names = [m['name'] for m in models]
                print(f"✓ Verfügbare Modelle: {', '.join(model_names)}")
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


def install_embedding_model():
    """
    Installiert das Embedding-Modell über Ollama.
    """
    print(f"\nInstalliere Modell '{EMBEDDING_MODEL}'...")
    print("Dies kann einige Minuten dauern...")
    
    try:
        result = subprocess.run(
            ['ollama', 'pull', EMBEDDING_MODEL],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',  # Ignoriere Encoding-Fehler
            timeout=300  # 5 Minuten Timeout
        )
        
        if result.returncode == 0:
            print(f"✓ Modell '{EMBEDDING_MODEL}' erfolgreich installiert")
            return True
        else:
            print(f"✗ Installation fehlgeschlagen: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ Installation-Timeout (dauert zu lange)")
        return False
    except FileNotFoundError:
        print("✗ 'ollama' Befehl nicht gefunden. Ist Ollama installiert?")
        return False
    except Exception as e:
        print(f"✗ Fehler bei Installation: {e}")
        return False


def check_ollama_available() -> bool:
    """
    Prüft ob Ollama läuft und das Embedding-Modell verfügbar ist.
    Installiert das Modell automatisch falls nicht vorhanden.
    """
    is_running, models = check_ollama_running()
    
    if not is_running:
        print("\n❌ Ollama ist nicht verfügbar!")
        print("Starten Sie Ollama oder installieren Sie es von: https://ollama.ai")
        return False
    
    # Prüfe ob Embedding-Modell verfügbar ist
    model_names = [m['name'] for m in models]
    
    if EMBEDDING_MODEL in model_names:
        print(f"✓ Embedding-Modell '{EMBEDDING_MODEL}' ist verfügbar\n")
        return True
    else:
        print(f"\n⚠ Embedding-Modell '{EMBEDDING_MODEL}' nicht gefunden")
        
        # Frage ob Modell installiert werden soll
        response = input(f"Möchten Sie '{EMBEDDING_MODEL}' jetzt installieren? (j/n): ").lower()
        
        if response in ['j', 'ja', 'y', 'yes']:
            return install_embedding_model()
        else:
            print(f"\nInstallieren Sie es manuell mit: ollama pull {EMBEDDING_MODEL}")
            return False


def get_embedding(text: str) -> list[float]:
    """
    Erstellt ein Embedding für den gegebenen Text mit Ollama.
    
    Args:
        text: Der zu embedende Text
        
    Returns:
        Liste von Float-Werten (Embedding-Vektor, 768 Dimensionen)
    """
    text = text.replace("\n", " ").strip()
    
    if not text:
        raise ValueError("Text darf nicht leer sein")
    
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={
                "model": EMBEDDING_MODEL,
                "prompt": text
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['embedding']
        else:
            raise RuntimeError(f"Ollama Embedding fehlgeschlagen: Status {response.status_code}")
            
    except Exception as e:
        print(f"[FEHLER] Embedding-Erstellung fehlgeschlagen: {e}")
        raise


def extract_pdf_text(pdf_path: str) -> str:
    """
    Extrahiert Text aus PDF-Datei.
    
    Args:
        pdf_path: Pfad zur PDF-Datei
        
    Returns:
        Extrahierter Text
    """
    print(f"Extrahiere Text aus: {pdf_path}")
    
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF-Datei nicht gefunden: {pdf_path}")
    
    text = ""
    
    # Versuche zuerst pdfplumber (bessere Textextraktion)
    if HAS_PDFPLUMBER:
        print("  Verwende pdfplumber...")
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                    if page_num % 10 == 0:
                        print(f"    Verarbeitet: {page_num} Seiten...")
            
            print(f"[OK] Text extrahiert: {len(text)} Zeichen")
            return text
        except Exception as e:
            print(f"[WARNUNG] pdfplumber fehlgeschlagen: {e}")
    
    # Fallback: PyPDF2
    if HAS_PYPDF2:
        print("  Verwende PyPDF2...")
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                    if page_num % 10 == 0:
                        print(f"    Verarbeitet: {page_num} Seiten...")
            
            print(f"[OK] Text extrahiert: {len(text)} Zeichen")
            return text
        except Exception as e:
            print(f"[FEHLER] PyPDF2 fehlgeschlagen: {e}")
            raise
    
    raise RuntimeError("Keine PDF-Bibliothek verfügbar. Installieren Sie: pip install PyPDF2 pdfplumber")


def extract_medical_professions(text: str) -> List[Dict[str, str]]:
    """
    Extrahiert medizinische Berufsbezeichnungen aus dem Text.
    
    Args:
        text: Extrahierter PDF-Text
        
    Returns:
        Liste von Dictionaries mit Berufsbezeichnung und Beschreibung
    """
    print("\nExtrahiere medizinische Berufsbezeichnungen...")
    
    professions = []
    
    # Pattern 1: Facharzt/Fachärztin für [Fachgebiet]
    pattern1 = r'(Facharzt|Fachärztin|Arzt|Ärztin)\s+für\s+([A-ZÄÖÜ][a-zäöüß\-\s]+(?:und\s+[A-ZÄÖÜ][a-zäöüß\-\s]+)?)'
    matches1 = re.finditer(pattern1, text, re.MULTILINE)
    
    for match in matches1:
        title = f"{match.group(1)} für {match.group(2).strip()}"
        professions.append({
            'title': title,
            'category': 'Facharzt',
            'description': f"Medizinische Fachrichtung: {match.group(2).strip()}"
        })
    
    # Pattern 2: Schwerpunkt/Zusatzweiterbildung
    pattern2 = r'(Schwerpunkt|Zusatzweiterbildung|Zusatz-Weiterbildung)[:\s]+([A-ZÄÖÜ][a-zäöüß\-\s]+)'
    matches2 = re.finditer(pattern2, text, re.MULTILINE)
    
    for match in matches2:
        category = match.group(1)
        specialization = match.group(2).strip()
        professions.append({
            'title': f"{category}: {specialization}",
            'category': category,
            'description': f"Medizinische Spezialisierung: {specialization}"
        })
    
    # Pattern 3: Kapitel-Überschriften mit Abschnittsnummern (z.B. "1. Innere Medizin")
    pattern3 = r'^\s*\d+\.?\s+([A-ZÄÖÜ][a-zäöüß\-\s]{10,50})\s*$'
    matches3 = re.finditer(pattern3, text, re.MULTILINE)
    
    for match in matches3:
        title = match.group(1).strip()
        # Filtere allgemeine Begriffe aus
        if not any(word in title.lower() for word in ['weiterbildung', 'ordnung', 'inhalt', 'präambel', 'definition']):
            professions.append({
                'title': title,
                'category': 'Fachgebiet',
                'description': f"Medizinisches Fachgebiet: {title}"
            })
    
    # Duplikate entfernen (basierend auf title)
    seen = set()
    unique_professions = []
    for prof in professions:
        title_normalized = prof['title'].lower().strip()
        if title_normalized not in seen and len(title_normalized) > 5:
            seen.add(title_normalized)
            unique_professions.append(prof)
    
    print(f"[OK] {len(unique_professions)} Berufsbezeichnungen gefunden")
    
    # Zeige erste 10 als Vorschau
    print("\nVorschau (erste 10):")
    for i, prof in enumerate(unique_professions[:10], 1):
        print(f"  {i}. {prof['title']} ({prof['category']})")
    
    if len(unique_professions) > 10:
        print(f"  ... und {len(unique_professions) - 10} weitere")
    
    return unique_professions


def create_medical_professions_table(conn):
    """
    Erstellt die Tabelle für medizinische Berufsbezeichnungen mit pgvector.
    """
    print("\nErstelle/Prüfe Datenbanktabelle...")
    
    with conn.cursor() as cur:
        # Prüfe ob pgvector Extension verfügbar ist
        cur.execute("""
            SELECT EXISTS(
                SELECT 1 FROM pg_extension WHERE extname = 'vector'
            );
        """)
        
        has_vector = cur.fetchone()[0]
        
        if not has_vector:
            print("  Erstelle pgvector Extension...")
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            conn.commit()
        
        # Prüfe ob Tabelle existiert und die richtige Dimension hat
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'medical_professions'
            );
        """)
        
        table_exists = cur.fetchone()[0]
        
        if table_exists:
            # Prüfe die aktuelle Dimension des Embeddings
            cur.execute("""
                SELECT atttypmod 
                FROM pg_attribute 
                WHERE attrelid = 'medical_professions'::regclass 
                AND attname = 'embedding';
            """)
            result = cur.fetchone()
            
            if result:
                current_dim = result[0]
                if current_dim != EMBEDDING_DIM:
                    print(f"  ⚠ Tabelle hat falsche Dimension ({current_dim} statt {EMBEDDING_DIM})")
                    print(f"  Lösche alte Tabelle und erstelle neu...")
                    cur.execute("DROP TABLE medical_professions CASCADE;")
                    conn.commit()
                    table_exists = False
        
        # Erstelle Tabelle (falls nicht vorhanden oder neu erstellt)
        if not table_exists:
            print(f"  Erstelle Tabelle mit {EMBEDDING_DIM} Dimensionen...")
            cur.execute(f"""
                CREATE TABLE medical_professions (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(500) NOT NULL UNIQUE,
                    category VARCHAR(100),
                    description TEXT,
                    embedding vector({EMBEDDING_DIM}),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Erstelle Index für schnellere Vektorsuche
            cur.execute("""
                CREATE INDEX medical_professions_embedding_idx 
                ON medical_professions 
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
            """)
            
            conn.commit()
            print("[OK] Tabelle 'medical_professions' erstellt")
        else:
            print("[OK] Tabelle 'medical_professions' existiert bereits")


def insert_professions_with_embeddings(conn, professions: List[Dict[str, str]]):
    """
    Fügt Berufsbezeichnungen mit Embeddings in die Datenbank ein.
    """
    print(f"\nFüge {len(professions)} Berufsbezeichnungen in Datenbank ein...")
    
    inserted = 0
    skipped = 0
    errors = 0
    
    with conn.cursor() as cur:
        for i, prof in enumerate(professions, 1):
            try:
                # Erstelle Embedding für Titel + Beschreibung
                text_to_embed = f"{prof['title']} - {prof['description']}"
                embedding = get_embedding(text_to_embed)
                
                # Füge in Datenbank ein
                cur.execute("""
                    INSERT INTO medical_professions (title, category, description, embedding)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (title) DO NOTHING;
                """, (
                    prof['title'],
                    prof['category'],
                    prof['description'],
                    embedding
                ))
                
                if cur.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1
                
                # Fortschritt anzeigen
                if i % 10 == 0:
                    print(f"  Verarbeitet: {i}/{len(professions)} (eingefügt: {inserted}, übersprungen: {skipped})")
                
            except Exception as e:
                errors += 1
                print(f"  [FEHLER] Fehler bei '{prof['title']}': {e}")
        
        conn.commit()
    
    print(f"\n[OK] Abgeschlossen:")
    print(f"  Eingefügt: {inserted}")
    print(f"  Übersprungen (bereits vorhanden): {skipped}")
    print(f"  Fehler: {errors}")


def search_similar_professions(conn, query: str, limit: int = 5):
    """
    Sucht ähnliche Berufsbezeichnungen basierend auf Vektorsuche.
    """
    print(f"\nSuche nach: '{query}'")
    
    # Erstelle Embedding für Query
    query_embedding = get_embedding(query)
    
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                title,
                category,
                description,
                1 - (embedding <=> %s::vector) AS similarity
            FROM medical_professions
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """, (query_embedding, query_embedding, limit))
        
        results = cur.fetchall()
        
        print(f"\nTop {limit} Ergebnisse:")
        for i, (title, category, description, similarity) in enumerate(results, 1):
            print(f"\n{i}. {title}")
            print(f"   Kategorie: {category}")
            print(f"   Ähnlichkeit: {similarity:.4f}")
            print(f"   {description}")


def main():
    """Hauptfunktion"""
    print("=" * 70)
    print("Medizinische Berufsbezeichnungen in pgvector laden (Ollama)")
    print("=" * 70)
    
    # Pfade
    pdf_path = r"data\medizin\20250703_MWBO-2018.pdf"
    
    # 1. Prüfe ob Ollama verfügbar ist und installiere Modell falls nötig
    if not check_ollama_available():
        print("\n❌ Ollama oder Embedding-Modell nicht verfügbar!")
        sys.exit(1)
    
    # 2. PDF-Text extrahieren
    try:
        text = extract_pdf_text(pdf_path)
    except Exception as e:
        print(f"[FEHLER] Konnte PDF nicht lesen: {e}")
        sys.exit(1)
    
    # 3. Berufsbezeichnungen extrahieren
    professions = extract_medical_professions(text)
    
    if not professions:
        print("[FEHLER] Keine Berufsbezeichnungen gefunden!")
        sys.exit(1)
    
    # 4. Datenbankverbindung herstellen
    try:
        print("\nVerbinde mit PostgreSQL...")
        conn = psycopg.connect(**DB_CONFIG, connect_timeout=10)
        print("[OK] Verbindung hergestellt")
    except Exception as e:
        print(f"[FEHLER] Datenbankverbindung fehlgeschlagen: {e}")
        print("\nStellen Sie sicher, dass:")
        print("  1. Docker läuft (docker-start.bat)")
        print("  2. PostgreSQL Container aktiv ist")
        sys.exit(1)
    
    try:
        # 5. Tabelle erstellen
        create_medical_professions_table(conn)
        
        # 6. Daten einfügen
        insert_professions_with_embeddings(conn, professions)
        
        # 7. Test-Suche durchführen
        print("\n" + "=" * 70)
        print("Test-Suche")
        print("=" * 70)
        search_similar_professions(conn, "Herz und Kreislauf", limit=5)
        
        print("\n" + "=" * 70)
        print("[OK] Erfolgreich abgeschlossen!")
        print("=" * 70)
        
    finally:
        conn.close()
        print("\nDatenbankverbindung geschlossen")


if __name__ == "__main__":
    main()
