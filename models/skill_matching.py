import pandas as pd
from sentence_transformers import SentenceTransformer, util
from nltk.tokenize import sent_tokenize
import nltk

# -----------------------------------------
# 1. NLTK Modelle laden (falls noch nicht installiert)
# -----------------------------------------
try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt")


# -----------------------------------------
# 2. Pandas Ausgabe erweitern
# -----------------------------------------
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.max_colwidth', None)
pd.set_option('display.expand_frame_repr', False)


# -----------------------------------------
# 3. ESCO Datenbank laden
# -----------------------------------------
skills = pd.read_csv(
    r"C:\Users\Angler1000\Desktop\Masterstudium\4. Semester\Big-Data-Consultingprojekt\Code\skills_de.csv",
    sep=","
)

skills = skills[['preferredLabel', 'description']].dropna(subset=['description'])

print("ESCO-Skills geladen:", len(skills))


# -----------------------------------------
# 4. Embedding-Modell laden
# -----------------------------------------
print("\nLade Embedding-Modell ...")
model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")


# -----------------------------------------
# 5. Prüfen, ob ein Skill in ESCO existiert
# -----------------------------------------
def esco_has_skill(skill_name, skills_df):
    """
    Prüft, ob der Skill irgendwo in ESCO vorkommt.
    Nur True/False – wird nicht für Matching genutzt.
    """
    skill_name = skill_name.lower()

    return any(
        skill_name in str(label).lower()
        for label in skills_df["preferredLabel"]
    )


# -----------------------------------------
# 6. Skill-Embedding erzeugen
# -----------------------------------------
def get_skill_embedding(skill_name, model):
    return model.encode([skill_name], convert_to_tensor=True)


# -----------------------------------------
# 7. Matching: Eigene Skills <-> Sätze
# -----------------------------------------
def match_skills_to_sentences(my_skills, sentences, model, esco_db):
    results = []

    # Alle Satz-Embeddings vorrechnen
    sent_embeddings = model.encode(sentences, convert_to_tensor=True)

    for skill in my_skills:
        skill_emb = get_skill_embedding(skill, model)

        # Ähnlichkeiten Skill ↔ Sätze
        scores = util.cos_sim(skill_emb, sent_embeddings)[0]

        # Bester Treffer
        best_idx = scores.argmax().item()
        best_score = float(scores[best_idx])
        best_sentence = sentences[best_idx]

        # ESCO-Hinweis
        exists_in_esco = esco_has_skill(skill, esco_db)

        results.append({
            "skill": skill,
            "score": best_score,
            "sentence": best_sentence,
            "in_esco": exists_in_esco
        })

    return results


# -----------------------------------------
# 8. Ausgabe formatieren
# -----------------------------------------
def print_results(results, threshold=0.55):
    print("\n🔍 Ergebnis Skill-Matching:\n")

    for r in results:
        check = "✓" if r["score"] >= threshold else "✗"
        esco_info = " (In ESCO)" if r["in_esco"] else " (Nicht in ESCO)"

        print(f"{r['skill']}{esco_info}: {check}   (Score: {r['score']:.3f})")
        print(f"   → Satz: \"{r['sentence']}\"\n")


# -----------------------------------------
# 9. Eigene Skills definieren
# -----------------------------------------
my_skills = [
    "Python (Computerprogrammierung) + Techniken und Grundsätze der Softwareentwicklung wie Analyse, Algorithmen, Programmierung, Testen und Kompilieren von Programmierparadigmen in Python.",
    "Datenwissenschaft + Fachgebiet, das sich mit großen Datenmengen befasst und Techniken der künstlichen Intelligenz wie maschinelle Lernalgorithmen einsetzt, um Muster vorherzusagen und nützliche Informationen für Geschäftsentscheidungen zu erhalten",
]

print("\nEigene Skills für Matching:")
print(my_skills)
print("\n===== Skill-Matching aktiv =====")


# -----------------------------------------
# 10. Nutzer-Eingabe starten
# -----------------------------------------
while True:
    text = input("\nGib Text ein ('exit' zum Beenden): ")

    if text.lower().strip() == "exit":
        break

    sentences = sent_tokenize(text)

    results = match_skills_to_sentences(
        my_skills=my_skills,
        sentences=sentences,
        model=model,
        esco_db=skills
    )

    print_results(results)