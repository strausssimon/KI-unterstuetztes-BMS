import requests
import json
import sys

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

def test_ollama_prompt(model="llama3.2", prompt="Wo steht der schiefe turm von Pisa? Antworte nur in einem Wort."):
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
        print("   Beispiel: ollama pull llama3.2")
        sys.exit(1)
    
    # Verwende das erste verfügbare Modell
    model_name = models[0]['name']
    
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
