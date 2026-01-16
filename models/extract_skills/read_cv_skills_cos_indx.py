import pandas as pd
import PyPDF2
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import os

def load_skills_database(skills_path="data/skills/digitalSkillsCollection_en.csv"):
    """
    Lädt die Skills-Datenbank aus der CSV-Datei.
    """
    if not os.path.exists(skills_path):
        print(f"Warnung: Skills-Datei nicht gefunden: {skills_path}")
        return pd.DataFrame()
    
    skills_df = pd.read_csv(skills_path)
    print(f"Skills-Datenbank geladen: {len(skills_df)} Skills")
    return skills_df

def extract_text_from_pdf(pdf_path):
    """
    Extrahiert den vollständigen Text aus einem PDF.
    """
    text = ""
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text

def extract_contact_info(cv_text):
    """
    Extrahiert Kontaktinformationen aus dem CV-Text.
    
    Returns:
        Tuple: (contact_info_dict, cleaned_cv_text)
    """
    import re
    
    contact_info = {
        'Name': 'N/A',
        'Email': 'N/A',
        'Telefon': 'N/A',
        'Adresse': 'N/A'
    }
    
    lines = cv_text.split('\n')
    contact_lines = []
    cleaned_lines = []
    email_line_index = -1
    address_section_started = False
    address_lines = []
    
    # E-Mail Regex
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    # Zahlenfolge Pattern (für Telefon)
    number_pattern = r'\d[\d\s\-\(\)\/\+]{7,}'
    
    # Erste Zeilen analysieren (ca. erste 25 Zeilen als Kontaktbereich)
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        
        if not line_stripped or i >= 25:
            if i >= 25:
                cleaned_lines.append(line)
            continue
            
        is_contact_line = False
        
        # E-Mail suchen
        email_match = re.search(email_pattern, line_stripped)
        if email_match:
            contact_info['Email'] = email_match.group()
            email_line_index = i
            is_contact_line = True
        
        # Telefon suchen: Zahlenfolge in der Nähe der E-Mail (±3 Zeilen)
        if email_line_index != -1 and abs(i - email_line_index) <= 3 and contact_info['Telefon'] == 'N/A':
            number_match = re.search(number_pattern, line_stripped)
            if number_match:
                # Prüfe ob es wirklich eine Telefonnummer sein könnte (mind. 8 Ziffern)
                digits_only = re.sub(r'\D', '', number_match.group())
                if len(digits_only) >= 8:
                    contact_info['Telefon'] = number_match.group().strip()
                    is_contact_line = True
        
        # Adresse suchen: Nach dem Wort "Adresse" oder "Address"
        if re.search(r'\b(adresse|address)\b', line_stripped, re.IGNORECASE):
            address_section_started = True
            is_contact_line = True
            continue
        
        # Sammle Adresszeilen nach dem "Adresse"-Keyword
        if address_section_started and contact_info['Adresse'] == 'N/A':
            # Prüfe ob Zeile Adress-relevante Inhalte hat
            if line_stripped and not re.search(email_pattern, line_stripped):
                # Sammle bis zu 3 Zeilen für die Adresse
                address_lines.append(line_stripped)
                is_contact_line = True
                
                # Wenn wir genug Adressinformationen haben (z.B. 2-3 Zeilen), stoppe
                if len(address_lines) >= 2:
                    contact_info['Adresse'] = ', '.join(address_lines)
                    address_section_started = False
        
        # Name aus den ersten 3 Zeilen (falls 2-4 Wörter und keine anderen Kontaktinfos)
        if i < 3 and contact_info['Name'] == 'N/A':
            words = line_stripped.split()
            if 2 <= len(words) <= 4 and not any(char.isdigit() for char in line_stripped):
                if '@' not in line_stripped and not re.search(number_pattern, line_stripped):
                    contact_info['Name'] = line_stripped
                    is_contact_line = True
        
        # Entscheide, ob Zeile zum Kontaktbereich gehört
        if is_contact_line:
            contact_lines.append(line)
        else:
            cleaned_lines.append(line)
    
    # Bereinigter Text ohne Kontaktinformationen
    cleaned_cv_text = '\n'.join(cleaned_lines)
    
    return contact_info, cleaned_cv_text

def find_sentence_with_keyword(text, keyword):
    """
    Findet den Satz im Text, der das Keyword enthält.
    """
    import re
    # Teile Text in Sätze
    sentences = re.split(r'[.!?\n]+', text)
    keyword_lower = keyword.lower()
    
    for sentence in sentences:
        if keyword_lower in sentence.lower():
            return sentence.strip()
    return "Kontext nicht gefunden"

def find_skills_in_cv(cv_text, skills_df, threshold=0.3):
    """
    Findet Skills im CV-Text mithilfe von direktem String-Matching und Cosine Similarity.
    
    Args:
        cv_text: Der vollständige CV-Text
        skills_df: DataFrame mit Skills aus der Datenbank
        threshold: Minimale Cosine Similarity für einen Match (0-1)
    
    Returns:
        DataFrame mit gefundenen Skills und Treffsicherheit
    """
    if skills_df.empty or not cv_text.strip():
        return pd.DataFrame()
    
    cv_text_lower = cv_text.lower()
    results = []
    matched_indices = set()
    
    # Phase 1: Direktes String-Matching (100% Treffsicherheit)
    print("  Phase 1: Direktes String-Matching...")
    for idx, row in skills_df.iterrows():
        # Prüfe preferredLabel
        preferred_label = str(row['preferredLabel']).lower()
        if preferred_label in cv_text_lower and len(preferred_label) >= 3:
            context = find_sentence_with_keyword(cv_text, preferred_label)
            results.append({
                'Skill': row['preferredLabel'],
                'Treffsicherheit': 1.0,
                'SkillType': row.get('skillType', ''),
                'Beschreibung': row.get('description', ''),
                'MatchType': 'Direct',
                'Kontext': context
            })
            matched_indices.add(idx)
            continue
        
        # Prüfe altLabels
        if pd.notna(row.get('altLabels', '')):
            alt_labels = str(row['altLabels']).lower().split('|')
            for alt_label in alt_labels:
                alt_label = alt_label.strip()
                if alt_label and alt_label in cv_text_lower and len(alt_label) >= 3:
                    context = find_sentence_with_keyword(cv_text, alt_label)
                    results.append({
                        'Skill': row['preferredLabel'],
                        'Treffsicherheit': 1.0,
                        'SkillType': row.get('skillType', ''),
                        'Beschreibung': row.get('description', ''),
                        'MatchType': 'Direct (AltLabel)',
                        'Kontext': context
                    })
                    matched_indices.add(idx)
                    break
    
    print(f"    {len(results)} direkte Matches gefunden")
    
    # Phase 2: Cosine Similarity für nicht-gematche Skills
    print("  Phase 2: Cosine Similarity...")
    remaining_skills = skills_df[~skills_df.index.isin(matched_indices)]
    
    if not remaining_skills.empty:
        # Erstelle Liste von Skills für TF-IDF
        skill_texts = []
        for _, row in remaining_skills.iterrows():
            skill_text = row['preferredLabel']
            if pd.notna(row.get('altLabels', '')) and str(row['altLabels']).strip():
                skill_text += " " + str(row['altLabels'])
            if pd.notna(row.get('description', '')) and str(row['description']).strip():
                skill_text += " " + str(row['description'])
            skill_texts.append(skill_text)
        
        # TF-IDF Vektorisierung
        vectorizer = TfidfVectorizer(
            ngram_range=(1, 3),
            min_df=1,
            lowercase=True
        )
        
        # Kombiniere CV-Text mit allen Skills für gemeinsame Vektorisierung
        all_texts = [cv_text] + skill_texts
        tfidf_matrix = vectorizer.fit_transform(all_texts)
        
        # Berechne Cosine Similarity
        cv_vector = tfidf_matrix[0:1]
        skill_vectors = tfidf_matrix[1:]
        similarities = cosine_similarity(cv_vector, skill_vectors)[0]
        
        # Füge Cosine-Matches hinzu
        for idx_local, (idx_global, row) in enumerate(remaining_skills.iterrows()):
            similarity = similarities[idx_local]
            if similarity >= threshold:
                # Versuche Kontext zu finden (erstes Wort des Skills)
                skill_first_word = str(row['preferredLabel']).split()[0]
                context = find_sentence_with_keyword(cv_text, skill_first_word)
                results.append({
                    'Skill': row['preferredLabel'],
                    'Treffsicherheit': round(similarity, 4),
                    'SkillType': row.get('skillType', ''),
                    'Beschreibung': row.get('description', ''),
                    'MatchType': 'Cosine',
                    'Kontext': context
                })
        
        print(f"    {len([r for r in results if r.get('MatchType') == 'Cosine'])} Cosine-Matches gefunden")
    
    # Sortiere nach Treffsicherheit absteigend
    results_df = pd.DataFrame(results)
    if not results_df.empty:
        results_df = results_df.sort_values('Treffsicherheit', ascending=False)
    
    return results_df

def main():
    """
    Hauptfunktion: Lädt CV, durchsucht nach Skills und gibt Ergebnisse aus.
    """
    # Pfade
    # cv_path = "data/db/documents/cvs/3M_Polo Yu_Finance Manager.pdf"
    # cv_path = "data/db/documents/cvs/Android-developer-resume-example-26.pdf"
    cv_path = "data/db/documents/cvs/AndrewClarkResume.pdf"
    skills_path = "data/skills/digitalSkillsCollection_en.csv"
    output_path = "results/cv_skills_matches.txt"
    
    print("=== CV Skills Matching ===\n")
    
    # 1. Lade Skills-Datenbank
    print("Lade Skills-Datenbank...")
    skills_df = load_skills_database(skills_path)
    
    if skills_df.empty:
        print("Fehler: Keine Skills geladen.")
        return
    
    # Ausgabe der ersten drei Skills
    print("\nErste 3 Skills aus der Datenbank:")
    print(skills_df[['preferredLabel', 'skillType', 'description']].head(3).to_string(index=False))
    print()
    
    # 2. Extrahiere Text aus CV
    print(f"\nExtrahiere Text aus CV: {cv_path}")
    cv_text = extract_text_from_pdf(cv_path)
    print(f"CV-Text extrahiert: {len(cv_text)} Zeichen\n")
    
    # 2b. Extrahiere Kontaktinformationen
    print("Extrahiere Kontaktinformationen...")
    contact_info, cleaned_cv_text = extract_contact_info(cv_text)
    print(f"Kontaktinformationen extrahiert:")
    for key, value in contact_info.items():
        print(f"  {key}: {value}")
    print(f"Bereinigter CV-Text: {len(cleaned_cv_text)} Zeichen\n")
    
    # 3. Finde Skills im CV (mit bereinigtem Text)
    print("Durchsuche CV nach Skills (Threshold: 0.3)...")
    found_skills = find_skills_in_cv(cleaned_cv_text, skills_df, threshold=0.3)
    
    # 4. Ausgabe der Ergebnisse
    if found_skills.empty:
        print("\nKeine Skills gefunden.")
    else:
        print(f"\n{len(found_skills)} Skills gefunden:\n")
        print(found_skills.to_string(index=False))
        
        # Speichere Ergebnisse in TXT-Datei
        os.makedirs("results", exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=== CV Skills Matching Ergebnisse ===\n\n")
            
            # Kontaktinformationen zuerst ausgeben
            f.write("--- Kontaktinformationen ---\n")
            for key, value in contact_info.items():
                f.write(f"{key}: {value}\n")
            f.write("\n")
            
            # Skills-Matches
            f.write("--- Gefundene Skills ---\n")
            f.write(f"Anzahl gefundener Skills: {len(found_skills)}\n\n")
            f.write(found_skills.to_string(index=False))
        print(f"\nErgebnisse gespeichert: {output_path}")

if __name__ == "__main__":
    main()
