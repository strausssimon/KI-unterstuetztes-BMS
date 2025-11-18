# Standard Library
import os
import re
import json
from datetime import datetime
from typing import List, Dict, Tuple, Optional

# Data Processing
import pandas as pd

# PDF Processing - Optional Dependencies
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False
    
try:
    from pdf2image import convert_from_path
    HAS_PDF2IMAGE = True
except ImportError:
    HAS_PDF2IMAGE = False

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

# Date Parsing - Optional
try:
    import dateparser
    HAS_DATEPARSER = True
except ImportError:
    HAS_DATEPARSER = False

# LLM Integration - Optional
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def inspect_pdf(pdf_path: str) -> Tuple[bool, str, List[Dict]]:
    """
    Inspiziert PDF und prüft, ob Text extrahierbar ist.
    Returns: (is_text_based, extracted_text, layout_info)
    """
    print("Inspiziere PDF...")
    
    if HAS_PDFPLUMBER:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                layout_info = []
                
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                    
                    # Extrahiere Layout-Koordinaten
                    words = page.extract_words()
                    for word in words:
                        layout_info.append({
                            'page': page_num,
                            'text': word['text'],
                            'x0': word['x0'],
                            'y0': word['top'],
                            'x1': word['x1'],
                            'y1': word['bottom']
                        })
                
                # Prüfe ob genug Text extrahiert wurde
                if len(text.strip()) > 100:
                    print(f"[OK] PDF ist textbasiert ({len(text)} Zeichen extrahiert)")
                    return True, text, layout_info
                else:
                    print("[WARNUNG] Wenig Text gefunden, PDF könnte gescannt sein")
                    return False, text, layout_info
                    
        except Exception as e:
            print(f"[WARNUNG] Fehler bei pdfplumber: {e}")
    
    # Fallback: Verwende PyPDF2 wenn verfügbar
    if HAS_PYPDF2:
        print("[INFO] pdfplumber nicht verfügbar, verwende PyPDF2 Fallback")
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                
                if len(text.strip()) > 100:
                    print(f"[OK] PyPDF2: Text extrahiert ({len(text)} Zeichen)")
                    return True, text, []
                else:
                    print("[WARNUNG] PyPDF2: Wenig Text gefunden")
                    return False, text, []
        except Exception as e:
            print(f"[FEHLER] PyPDF2-Fehler: {e}")
    
    print("[INFO] Keine PDF-Bibliothek verfügbar")
    return False, "", []


def ocr_pdf(pdf_path: str) -> str:
    """
    Führt OCR auf gescanntem PDF aus.
    """
    print("Führe OCR aus...")
    
    if not HAS_PDF2IMAGE or not HAS_TESSERACT:
        print("[WARNUNG] OCR-Bibliotheken nicht verfügbar (pdf2image/pytesseract)")
        return ""
    
    try:
        # Konvertiere PDF zu Bildern
        images = convert_from_path(pdf_path, dpi=300)
        text = ""
        
        for i, image in enumerate(images):
            print(f"  Verarbeite Seite {i+1}/{len(images)}...")
            page_text = pytesseract.image_to_string(image, lang='deu+eng')
            text += page_text + "\n"
        
        print(f"[OK] OCR abgeschlossen ({len(text)} Zeichen)")
        return text
        
    except Exception as e:
        print(f"[FEHLER] OCR-Fehler: {e}")
        return ""


def is_header_line(line: str) -> bool:
    """
    Erkennt ob eine Zeile eine Überschrift ist.
    Kriterien: UPPERCASE, unterstrichen, endet mit Doppelpunkt, kurz und prägnant
    """
    line = line.strip()
    if not line or len(line) < 3:
        return False
    
    # Überschrift ist komplett in UPPERCASE
    if line.isupper() and len(line) < 50:
        return True
    
    # Endet mit Doppelpunkt
    if line.endswith(':') and len(line) < 50:
        return True
    
    # Typische CV-Überschriften
    header_keywords = [
        'BERUFSERFAHRUNG', 'WORK EXPERIENCE', 'PROFESSIONAL EXPERIENCE', 'EMPLOYMENT',
        'AUSBILDUNG', 'EDUCATION', 'BILDUNG',
        'QUALIFIKATIONEN', 'QUALIFICATIONS', 'SKILLS', 'KOMPETENZEN', 'FÄHIGKEITEN',
        'PROJEKTE', 'PROJECTS',
        'ZERTIFIKATE', 'CERTIFICATES', 'CERTIFICATIONS',
        'SPRACHEN', 'LANGUAGES',
        'PERSÖNLICHE DATEN', 'PERSONAL INFORMATION', 'KONTAKT',
        'ZUSAMMENFASSUNG', 'SUMMARY', 'PROFIL', 'PROFILE'
    ]
    
    line_upper = line.upper().replace(':', '')
    for keyword in header_keywords:
        if keyword in line_upper:
            return True
    
    return False


def segment_document(text: str, layout_info: List[Dict]) -> List[Dict]:
    """
    Segmentiert Dokument in Blöcke basierend auf Überschriften.
    Erkennt Überschriften (UPPERCASE, mit Doppelpunkt, etc.) und erstellt Blöcke.
    """
    print("Segmentiere Dokument in Blöcke...")
    
    blocks = []
    lines = text.split('\n')
    current_block = []
    current_header = None
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Prüfe ob Zeile eine Überschrift ist
        if is_header_line(line):
            # Speichere vorherigen Block
            if current_block:
                block_text = '\n'.join(current_block)
                if len(block_text.strip()) > 20:  # Nur wenn genug Inhalt
                    blocks.append({
                        'header': current_header,
                        'content': block_text
                    })
            
            # Starte neuen Block
            current_header = line
            current_block = []
        elif line:
            # Füge Zeile zum aktuellen Block hinzu
            current_block.append(line)
    
    # Letzten Block speichern
    if current_block:
        block_text = '\n'.join(current_block)
        if len(block_text.strip()) > 20:
            blocks.append({
                'header': current_header if current_header else 'Allgemein',
                'content': block_text
            })
    
    print(f"[OK] {len(blocks)} Blöcke gefunden")
    for i, block in enumerate(blocks):
        print(f"  Block {i+1}: {block['header']}")
    
    return blocks


def extract_all_date_ranges_from_text(text: str) -> List[Tuple[Optional[str], Optional[str], int]]:
    """
    Extrahiert ALLE Datumsangaben aus dem Text.
    Returns: Liste von (start_date, end_date, position_in_text)
    """
    # Regex-Patterns für Datumsbereiche
    date_patterns = [
        (r'(\d{1,2}[./]\d{4})\s*[-–]\s*(\d{1,2}[./]\d{4})', 2),  # 01/2020 - 12/2022
        (r'(\d{4})\s*[-–]\s*(\d{4})', 2),  # 2020 - 2022
        (r'(\w{3,}\s+\d{4})\s*[-–]\s*(\w{3,}\s+\d{4})', 2),  # Jan 2020 - Dez 2022
        (r'(\d{1,2}[./]\d{4})\s*[-–]\s*(present|heute|current|jetzt)', 2),  # 01/2020 - present
        (r'(\d{4})\s*[-–]\s*(present|heute|current|jetzt)', 2),  # 2020 - present
        (r'(seit|since)\s+(\d{4})', 1),  # seit 2020
    ]
    
    found_dates = []
    
    for pattern, group_count in date_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            start_raw = match.group(1)
            end_raw = match.group(2) if group_count >= 2 else None
            
            # Normalisiere mit dateparser
            if HAS_DATEPARSER:
                start_date = dateparser.parse(start_raw)
                start_str = start_date.strftime('%Y-%m-%d') if start_date else start_raw
                
                if end_raw and end_raw.lower() in ['present', 'heute', 'current', 'jetzt', 'seit', 'since']:
                    end_str = None  # Aktuell noch tätig
                elif end_raw:
                    end_date = dateparser.parse(end_raw)
                    end_str = end_date.strftime('%Y-%m-%d') if end_date else end_raw
                else:
                    end_str = None
                
                found_dates.append((start_str, end_str, match.start()))
            else:
                found_dates.append((start_raw, end_raw, match.start()))
    
    return found_dates


def extract_with_llm(block_text: str, block_header: str = None) -> Optional[Dict]:
    """
    Nutzt Ollama LLM zur Extraktion von strukturierten Daten aus unregelmäßigen CVs.
    """
    if not HAS_REQUESTS:
        return None
    
    header_info = f" (Block: {block_header})" if block_header else ""
    print(f"Verwende LLM für Extraktion...{header_info}")
    print(f"  Text-Vorschau: {block_text[:100]}...")
    
    prompt = f"""Analysiere den folgenden Lebenslauf-Abschnitt und extrahiere die Informationen als JSON.

Format:
{{
    "start_date": "YYYY-MM-DD oder 'YYYY' oder null",
    "end_date": "YYYY-MM-DD oder 'YYYY' oder null (null wenn 'present'/'aktuell')",
    "title": "Jobtitel/Position",
    "company": "Firma/Organisation",
    "description": "Tätigkeitsbeschreibung"
}}

Text:
{block_text}

JSON:"""
    
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.2",
                "prompt": prompt,
                "stream": False
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            answer = result.get('response', '')
            
            # Extrahiere JSON aus Antwort
            json_match = re.search(r'\{.*\}', answer, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return data
    except Exception as e:
        print(f"[WARNUNG] LLM-Extraktion fehlgeschlagen: {e}")
    
    return None


def parse_cv_blocks(blocks: List[Dict], use_llm: bool = False) -> List[Dict]:
    """
    Parst CV-Blöcke und extrahiert strukturierte Informationen.
    Extrahiert ALLE Zeiträume aus jedem Block als separate Einträge.
    """
    print("Parse CV-Blöcke...")
    entries = []
    
    for i, block_dict in enumerate(blocks):
        block = block_dict['content']
        header = block_dict['header']
        
        if len(block.strip()) < 20:  # Zu kurz, überspringe
            continue
        
        print(f"\nVerarbeite Block '{header}':")
        
        # Versuche LLM-Extraktion wenn aktiviert
        if use_llm:
            llm_result = extract_with_llm(block, header)
            if llm_result:
                entries.append({
                    'Beginndatum': llm_result.get('start_date', 'N/A'),
                    'Enddatum': llm_result.get('end_date', 'N/A'),
                    'Titel': llm_result.get('title', 'N/A') if llm_result.get('title') else 'N/A',
                    'Beschreibung': llm_result.get('description', 'N/A') if llm_result.get('description') else 'N/A'
                })
                continue
        
        # Fallback: Regex + Heuristiken - Finde ALLE Datumsangaben
        date_ranges = extract_all_date_ranges_from_text(block)
        
        if date_ranges:
            print(f"  {len(date_ranges)} Zeiträume gefunden")
            lines = [l.strip() for l in block.split('\n') if l.strip()]
            
            # Für jede gefundene Datumsangabe einen Eintrag erstellen
            for idx, (start_date, end_date, position) in enumerate(date_ranges):
                # Finde die Zeile, die das Datum enthält
                current_line_idx = 0
                char_count = 0
                
                for line_idx, line in enumerate(lines):
                    if char_count <= position < char_count + len(line):
                        current_line_idx = line_idx
                        break
                    char_count += len(line) + 1  # +1 für Newline
                
                # Titel: Zeile mit Datum oder die nächste Zeile
                title = lines[current_line_idx] if current_line_idx < len(lines) else "N/A"
                
                # Entferne Datumsangabe aus Titel
                title = re.sub(r'\d{1,2}[./]\d{4}\s*[-–]\s*\d{1,2}[./]\d{4}', '', title)
                title = re.sub(r'\d{4}\s*[-–]\s*\d{4}', '', title)
                title = re.sub(r'\d{4}\s*[-–]\s*(present|heute|current|jetzt)', '', title, flags=re.IGNORECASE)
                title = title.strip()
                
                if not title:
                    # Versuche nächste Zeile
                    if current_line_idx + 1 < len(lines):
                        title = lines[current_line_idx + 1]
                    else:
                        title = "N/A"
                
                # Beschreibung: Sammle Zeilen bis zur nächsten Datumsangabe oder Ende
                description_lines = []
                start_collecting = current_line_idx + 1
                
                # Finde die Position der nächsten Datumsangabe
                next_date_pos = date_ranges[idx + 1][2] if idx + 1 < len(date_ranges) else len(block)
                
                char_count = 0
                for line_idx, line in enumerate(lines):
                    if line_idx > current_line_idx:
                        if char_count >= next_date_pos:
                            break
                        # Ignoriere Zeilen, die nur aus Datum bestehen
                        if not re.match(r'^\d{1,2}[./]\d{4}\s*[-–]', line):
                            description_lines.append(line)
                    char_count += len(line) + 1
                
                description = ' '.join(description_lines).strip() if description_lines else "N/A"
                
                entries.append({
                    'Beginndatum': start_date,
                    'Enddatum': end_date if end_date else 'Aktuell',
                    'Titel': title if title else "N/A",
                    'Beschreibung': description if description else "N/A"
                })
        else:
            # Kein Datum gefunden - trotzdem als Eintrag speichern
            print(f"  Keine Zeiträume gefunden")
            lines = [l.strip() for l in block.split('\n') if l.strip()]
            entries.append({
                'Beginndatum': 'N/A',
                'Enddatum': 'N/A',
                'Titel': lines[0] if lines else header,
                'Beschreibung': ' '.join(lines[1:]) if len(lines) > 1 else "N/A"
            })
    
    print(f"\n[OK] Gesamt {len(entries)} Einträge extrahiert")
    return entries


def validate_entries(entries: List[Dict]) -> List[Dict]:
    """
    Validiert und bereinigt extrahierte Einträge.
    Sortiert nach Beginndatum in absteigender Reihenfolge.
    """
    print("Validiere Einträge...")
    validated = []
    
    for entry in entries:
        # Normalisiere 'Present' zu None
        if entry['Enddatum'] in ['present', 'heute', 'current', 'jetzt', 'Aktuell']:
            entry['Enddatum'] = None
        
        # Stelle sicher, dass Titel und Beschreibung nicht leer sind
        if not entry.get('Titel') or entry['Titel'].strip() == '':
            entry['Titel'] = 'N/A'
        if not entry.get('Beschreibung') or entry['Beschreibung'].strip() == '':
            entry['Beschreibung'] = 'N/A'
        
        validated.append(entry)
    
    # Sortiere nach Beginndatum (absteigend)
    def get_sort_key(entry):
        date_str = entry['Beginndatum']
        if date_str == 'N/A' or not date_str:
            return datetime.min
        try:
            # Versuche verschiedene Formate zu parsen
            if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
                return datetime.strptime(date_str, '%Y-%m-%d')
            elif re.match(r'^\d{4}$', date_str):
                return datetime.strptime(date_str, '%Y')
            elif re.match(r'^\d{1,2}[./]\d{4}$', date_str):
                return datetime.strptime(date_str.replace('.', '/'), '%m/%Y')
            else:
                return datetime.min
        except:
            return datetime.min
    
    validated.sort(key=get_sort_key, reverse=True)
    
    return validated

def extract_cv_with_llm(cv_text: str) -> List[Dict]:
    """
    Nutzt Ollama LLM zur vollständigen Extraktion aller CV-Einträge.
    """
    if not HAS_REQUESTS:
        print("[WARNUNG] LLM nicht verfügbar, kann keine Extraktion durchführen")
        return []
    
    print("Verwende LLM für vollständige CV-Extraktion...")
    print(f"  Text-Länge: {len(cv_text)} Zeichen")
    
    prompt = f"""Analysiere den folgenden Lebenslauf und extrahiere ALLE Berufserfahrungen, Ausbildungen und relevanten Stationen als JSON-Array.

Erstelle für jeden Eintrag (Job, Ausbildung, Projekt, etc.) ein JSON-Objekt mit folgenden Feldern:
- "Beginndatum": Start-Datum im Format "YYYY-MM-DD" oder "YYYY" (oder null wenn nicht vorhanden)
- "Enddatum": End-Datum im Format "YYYY-MM-DD" oder "YYYY", oder null wenn aktuell/present
- "Titel": Position/Jobtitel/Ausbildung
- "Beschreibung": Firma/Institution und Tätigkeitsbeschreibung

Sortiere die Einträge nach Beginndatum absteigend (neueste zuerst).

Format:
[
  {{
    "Beginndatum": "2020-01",
    "Enddatum": "2023-12",
    "Titel": "Senior Developer",
    "Beschreibung": "ABC Company - Entwicklung von Web-Anwendungen..."
  }},
  ...
]

Lebenslauf:
{cv_text}

JSON-Array:"""
    
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.2",
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            answer = result.get('response', '')
            
            print(f"  LLM-Antwort erhalten ({len(answer)} Zeichen)")
            
            # Extrahiere JSON-Array aus Antwort
            json_match = re.search(r'\[.*\]', answer, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                print(f"  {len(data)} Einträge vom LLM extrahiert")
                
                # Validiere und normalisiere Einträge
                validated_entries = []
                for entry in data:
                    validated_entries.append({
                        'Beginndatum': entry.get('Beginndatum', 'N/A'),
                        'Enddatum': entry.get('Enddatum', 'N/A'),
                        'Titel': entry.get('Titel', 'N/A'),
                        'Beschreibung': entry.get('Beschreibung', 'N/A')
                    })
                
                return validated_entries
            else:
                print("[WARNUNG] Kein JSON-Array in LLM-Antwort gefunden")
                return []
                
    except json.JSONDecodeError as e:
        print(f"[FEHLER] JSON-Parsing fehlgeschlagen: {e}")
        return []
    except Exception as e:
        print(f"[FEHLER] LLM-Extraktion fehlgeschlagen: {e}")
        return []
    
    return []


def create_cv_excel(pdf_path: str, output_path: str, use_llm: bool = True):
    """
    Hauptfunktion: Liest CV aus PDF und erstellt Excel-Tabelle.
    
    Args:
        pdf_path: Pfad zur PDF-Datei
        output_path: Pfad zur Excel-Ausgabedatei
        use_llm: Ob LLM (Ollama) für Extraktion verwendet werden soll
    """
    print(f"Lese PDF-Datei: {pdf_path}")
    print("=" * 60)
    
    # Schritt 1: Extrahiere Text mit PyPDF2
    if not HAS_PYPDF2:
        print("[FEHLER] PyPDF2 nicht verfügbar")
        return None
    
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            cv_text = ""
            print(f"PDF hat {len(pdf_reader.pages)} Seiten")
            
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                if page_text:
                    cv_text += page_text + "\n"
                print(f"  Seite {page_num + 1}: {len(page_text)} Zeichen")
            
            print(f"\n[OK] Text extrahiert ({len(cv_text)} Zeichen)")
    except Exception as e:
        print(f"[FEHLER] Fehler beim Lesen der PDF: {e}")
        return None
    
    if len(cv_text.strip()) < 100:
        print("[FEHLER] Zu wenig Text extrahiert")
        return None
    
    print("\n--- Extrahierter Text (erste 500 Zeichen) ---")
    print(cv_text[:500])
    print("--- Ende Vorschau ---\n")
    
    # Schritt 2: Verwende LLM zur Extraktion
    if use_llm and HAS_REQUESTS:
        entries = extract_cv_with_llm(cv_text)
    else:
        print("[WARNUNG] LLM nicht verfügbar oder deaktiviert")
        entries = []
    
    if not entries:
        print("[WARNUNG] Keine Einträge vom LLM extrahiert, erstelle Fallback-Eintrag...")
        entries = [{
            'Beginndatum': 'N/A',
            'Enddatum': 'N/A',
            'Titel': 'Siehe Beschreibung',
            'Beschreibung': cv_text[:1000]  # Erste 1000 Zeichen
        }]
    
    # Schritt 3: Validierung und Sortierung
    entries = validate_entries(entries)
    
    # Schritt 4: Export zu Excel
    df = pd.DataFrame(entries)
    
    print(f"\nErstelle Excel-Datei: {output_path}")
    df.to_excel(output_path, index=False, sheet_name='Lebenslauf')
    
    print(f"\n[OK] Excel-Datei erfolgreich erstellt!")
    print(f"[OK] Anzahl der Einträge: {len(entries)}")
    print("\nVorschau der Daten:")
    print(df.to_string(index=False))
    print("=" * 60)
    
    return df

if __name__ == "__main__":
    # Pfade definieren
    pdf_path = r"data\db\documents\cvs\3M_Polo Yu_Finance Manager.pdf"
    output_path = r"data\db\documents\cvs\3M_Polo Yu_Finance Manager_cv.xlsx"
    
    # Prüfe ob PDF existiert
    if not os.path.exists(pdf_path):
        print(f"[FEHLER] PDF-Datei nicht gefunden: {pdf_path}")
        print(f"Aktuelles Verzeichnis: {os.getcwd()}")
    else:
        # Prüfe verfügbare Bibliotheken
        print("Verfügbare Bibliotheken:")
        print(f"  - pdfplumber: {'[OK]' if HAS_PDFPLUMBER else '[FEHLT]'}")
        print(f"  - PyPDF2 (Fallback): {'[OK]' if HAS_PYPDF2 else '[FEHLT]'}")
        print(f"  - pdf2image: {'[OK]' if HAS_PDF2IMAGE else '[FEHLT]'}")
        print(f"  - pytesseract: {'[OK]' if HAS_TESSERACT else '[FEHLT]'}")
        print(f"  - dateparser: {'[OK]' if HAS_DATEPARSER else '[FEHLT]'}")
        print(f"  - requests (für LLM): {'[OK]' if HAS_REQUESTS else '[FEHLT]'}")
        print()
        
        # Excel erstellen (mit LLM-Option)
        use_llm = HAS_REQUESTS  # Aktiviere LLM wenn verfügbar
        create_cv_excel(pdf_path, output_path, use_llm=use_llm)
