import requests
import json
from typing import Optional
from pydantic import BaseModel, ValidationError

# --------------------------------------------------
# OLLAMA CONFIG
# --------------------------------------------------
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama2"

# --------------------------------------------------
# ERLAUBTE WERTE
# --------------------------------------------------
POSITIONEN = [
    "assistenzarzt",
    "facharzt",
    "oberarzt",
    "leitender oberarzt",
    "chefarzt",
    "standortleiter",
    "gesellschafter"
]

FACHAUSWAHL = [
    "anästhesie",
    "chirurgie",
    "gynäkologie",
    "innere medizin",
    "kinderradiologie",
    "mammographie",
    "neuroradiologie",
    "nuklearmedizin",
    "orthopädie & uch",
    "pädiatrie/kindermedizin",
    "psychiatrie",
    "radiologie",
    "strahlentherapie"
]

# --------------------------------------------------
# ZIELSCHEMA
# --------------------------------------------------
class CandidateExtract(BaseModel):
    first_name: Optional[str]
    last_name: Optional[str]
    status: Optional[str]
    wohnort: Optional[str]
    wunscharbeitsort: Optional[str]
    regionale_verfuegbarkeit: Optional[str]
    position_now: Optional[str]
    department: Optional[str]
    short_note: Optional[str]

# --------------------------------------------------
# PROMPT MIT DETAILLIERTEN FELDERKLÄRUNGEN
# --------------------------------------------------
def build_prompt(text: str) -> str:
    return f"""
Du bist ein spezialisiertes Extraktionssystem fuer medizinische Recruiting-Daten.
Deine Aufgabe ist es, strukturierte Felder aus Freitext zu extrahieren.
Antworte AUSSCHLIESSLICH mit gueltigem JSON.
KEIN Text, KEINE Erklaerungen ausserhalb des JSON.
Alle Felder muessen einfache Strings oder null sein (keine Objekte, keine Arrays).

WICHTIGE REGELN GEGEN HALLUZINATIONEN
- Nutze NUR Informationen, die explizit im TEXT stehen.
- Keine Vermutungen, kein Weltwissen, keine Ergaenzungen.
- Wenn ein Feld nicht eindeutig und direkt im TEXT belegt ist -> null.
- Jede nicht-null Angabe muss im TEXT belegbar sein.
- Fuer short_note gilt: nur belegbare Zusatzinfos aus dem TEXT, keine neuen Fakten.
- Wenn nichts zusaetzlich belegbares vorhanden ist -> short_note = null.

--------------------------------------------------
FELDER & REGELN
--------------------------------------------------
1) first_name - Vorname der Person - Beispiel: "Anna" - Wenn unklar oder nicht vorhanden -> null
2) last_name - Nachname der Person - Beispiel: "Mueller" - Wenn unklar oder nicht vorhanden -> null
3) status - Gibt an, ob die Person aktuell offen fuer neue Stellen ist
   ERLAUBTE WERTE:
   - "interested" -> aktiv suchend, offen fuer Angebote, wechselbereit
   - "not interested" -> kein Wechselinteresse
   - Wenn kein klares Signal vorhanden -> null
4) wohnort - Aktueller Wohn- oder Arbeitsort (Stadt) - Beispiel: "Koeln" - KEINE Regionen, KEINE Laender - Wenn nicht eindeutig -> null
5) wunscharbeitsort - Bevorzugte Region oder Stadt fuer eine neue Stelle
   Beispiele:
   - "NRW"
   - "Bayern"
   - "Muenchen"
   - Wenn keine Praeferenz genannt -> null
6) regionale_verfuegbarkeit - Dieses Feld entspricht dem Arbeitsweg, also der täglichen Pendelbereitschaft in km (Kilometern). Trage nur die Zahl ein, ohne "km" oder andere Einheiten. Wenn keine klare Angabe zur Pendelbereitschaft gemacht wird, trage null ein.
7) position_now - Aktuelle berufliche Position - MUSS GENAU einer der folgenden Werte sein (kleingeschrieben): {POSITIONEN}
   Synonyme bitte korrekt zuordnen:
   - "Oberaerztin" -> "oberarzt"
   - "Leitender OA" -> "leitender oberarzt"
   - Wenn keine eindeutige Zuordnung moeglich -> null
8) department - Medizinischer Fachbereich - MUSS GENAU einer der folgenden Werte sein (kleingeschrieben): {FACHAUSWAHL}
   Beispiele:
   - "Radiologie" -> "radiologie"
   - "Schwerpunkt Neuroradiologie" -> "neuroradiologie"
   - Wenn kein eindeutiger Match -> null
9) short_note - Alle relevanten Informationen, die NICHT eindeutig einem Feld zugeordnet werden koennen
   Beispiele:
   - KEINE Wiederholung der anderen Felder
   - NUR belegbare Inhalte aus dem TEXT
   - Bei Unsicherheit -> null

SELBSTCHECK VOR AUSGABE
1) Ist jeder nicht-null Wert im TEXT belegbar?
2) Falls nein: setze das betreffende Feld auf null.

--------------------------------------------------
Ordne ausschließlich folgende Infos den Feldern zu:
\"\"\"{text}\"\"\"
JSON:
"""


# --------------------------------------------------
# NORMALISIERUNG / ABSICHERUNG
# --------------------------------------------------
def normalize_llm_output(data: dict) -> dict:
    out = {}
    
    # Einfache String-Felder
    for f in [
        "first_name",
        "last_name",
        "status",
        "wohnort",
        "wunscharbeitsort",
        "short_note"
    ]:
        out[f] = data.get(f) if isinstance(data.get(f), str) else None

    # Position normalisieren
    pos = data.get("position_now")
    if isinstance(pos, str):
        pos_l = pos.lower()
        out["position_now"] = next((p for p in POSITIONEN if p in pos_l), None)
    else:
        out["position_now"] = None

    # Fachbereich normalisieren
    dep = data.get("department")
    if isinstance(dep, str):
        dep_l = dep.lower()
        out["department"] = next((f for f in FACHAUSWAHL if f in dep_l), None)
    else:
        out["department"] = None

    # Regionale Verfügbarkeit vereinheitlichen
    rv = data.get("regionale_verfuegbarkeit")
    if isinstance(rv, dict):
        parts = []
        if "max_distance" in rv:
            parts.append(f'{rv["max_distance"]} km')
        if "region" in rv:
            parts.append(rv["region"])
        out["regionale_verfuegbarkeit"] = ", ".join(parts) if parts else None
    elif isinstance(rv, int) and not isinstance(rv, bool):
        out["regionale_verfuegbarkeit"] = str(rv)
    elif isinstance(rv, str):
        out["regionale_verfuegbarkeit"] = rv
    else:
        out["regionale_verfuegbarkeit"] = None

    return out

# --------------------------------------------------
# EXTRAKTION
# --------------------------------------------------
def extract_candidate(text: str) -> CandidateExtract:
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": build_prompt(text),
            "stream": False
        },
        timeout=120
    )
    
    raw = response.json().get("response", "").strip()
    
    print("\n--- LLM RAW OUTPUT ---")
    print(raw)
    print("----------------------\n")
    
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        parsed = json.loads(raw[start:end])
        normalized = normalize_llm_output(parsed)
        return CandidateExtract(**normalized)
    except (json.JSONDecodeError, ValidationError, ValueError) as e:
        raise RuntimeError(f"❌ Ungültige LLM-Antwort:\n{raw}") from e

# --------------------------------------------------
# DEMO
# --------------------------------------------------
if __name__ == "__main__":
    raw_text = """
    Peter Pan arbeitet als Oberarzt in einer Chirurgie in Bonn
    """
    candidate = extract_candidate(raw_text)
