import psycopg
import requests
import json
from datetime import date, datetime
from decimal import Decimal

# --------------------------------------------------
# JSON-Serializer für PostgreSQL-Datentypen
# --------------------------------------------------
def json_serializer(obj):
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return str(obj)

# --------------------------------------------------
# 1. Verbindung zur PostgreSQL-Datenbank
# --------------------------------------------------
conn = psycopg.connect(
    host="localhost",
    port=5432,
    dbname="postgres",
    user="postgres",
    password="bigdataconsulting"
)

cur = conn.cursor()

# Tabelle abfragen
cur.execute("SELECT * FROM bewerber;")
rows = cur.fetchall()

# Spaltennamen ermitteln
column_names = [desc[0] for desc in cur.description]

cur.close()
conn.close()

# --------------------------------------------------
# 2. Daten für das LLM aufbereiten
# --------------------------------------------------
data_as_text = []
for row in rows:
    record = dict(zip(column_names, row))
    data_as_text.append(record)

database_content = json.dumps(
    data_as_text,
    ensure_ascii=False,
    indent=2,
    default=json_serializer
)

# --------------------------------------------------
# 3. Frage an das LLM
# --------------------------------------------------
user_question = "Gibt es einen Bewerber mit dem Voornamen Tim?"

# --------------------------------------------------
# 4. Prompt erstellen
# --------------------------------------------------
prompt = f"""
Du bist ein Datenanalyst.
Die folgenden Daten stammen aus einer PostgreSQL-Datenbank (Tabelle: bewerber).

Daten:
{database_content}

Frage:
{user_question}

Antworte präzise und verständlich auf Deutsch.
"""

# --------------------------------------------------
# 5. Anfrage an Ollama (llama2)
# --------------------------------------------------
response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "llama2",
        "prompt": prompt,
        "stream": False
    }
)

result = response.json()

# --------------------------------------------------
# 6. Antwort ausgeben
# --------------------------------------------------
print("\n==============================")
print("Antwort vom LLM:")
print("==============================\n")
print(result["response"])