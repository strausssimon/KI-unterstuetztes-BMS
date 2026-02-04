#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
search_all_cv_pdfs.py

Durchsucht alle in der Tabelle candidates gespeicherten CV-PDFs (Spalte
cv_pdf, BYTEA) nach einem freien Suchbegriff.

Ablauf:
- Nutzer gibt einen Suchbegriff ein.
- Optional: unscharfer Matching-Threshold (Standard 70).
- Skript lädt für alle Kandidaten mit cv_pdf den PDF-Text.
- Es führt eine unscharfe Suche analog extract_pdf_search.py durch
  (fuzzywuzzy.partial_ratio pro Satz).
- Für jeden Treffer werden Kandidaten-ID, Name und aussagekräftige
  Textausschnitte mit hervorgehobenem Suchbegriff ausgegeben.
"""

import sys
import os
import io
import re
from typing import List, Tuple

# Projekt-Root zum Python-Pfad hinzufügen
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

import psycopg
from fuzzywuzzy import fuzz
from PyPDF2 import PdfReader
import requests
from src.db_config import DB_CONFIG

# Optionale LLM-Unterstützung über Ollama (mistral)
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral:latest"


def pdf_bytes_to_text(pdf_bytes: bytes) -> str:
    """Extrahiert Text aus PDF-Bytes mittels PyPDF2."""
    if not pdf_bytes:
        return ""

    try:
        with io.BytesIO(pdf_bytes) as bio:
            reader = PdfReader(bio)
            pages_text: List[str] = []
            for page in reader.pages:
                try:
                    page_text = page.extract_text() or ""
                except Exception:
                    page_text = ""
                pages_text.append(page_text)
        return "\n".join(pages_text)
    except Exception:
        return ""


def clean_text(text: str) -> str:
    """Bereinigt Text (ähnlich extract_pdf_search.py)."""
    text = re.sub(r"\s+", " ", text)
    # Optionale weitere Bereinigung könnte ergänzt werden
    return text


def syntactic_search(text: str, query: str, threshold: int = 70) -> List[str]:
    """Unscharfe Satzsuche mit fuzzywuzzy (analog extract_pdf_search.py)."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    q = query.lower()
    matches: List[str] = []
    for sentence in sentences:
        if not sentence.strip():
            continue
        sent_lower = sentence.lower()

        # 1) Exakter (case-insensitiver) Treffer des Suchbegriffs im Satz
        if q in sent_lower:
            matches.append(sentence.strip())
            continue

        # 2) Unscharfer Match via fuzzywuzzy
        if fuzz.partial_ratio(sent_lower, q) >= threshold:
            matches.append(sentence.strip())
    return matches


def highlight_query(text: str, query: str) -> str:
    """Hebt Vorkommen des Suchbegriffs im Text hervor."""
    if not query:
        return text
    pattern = r"(?i)" + re.escape(query)
    return re.sub(pattern, lambda m: f"[{m.group(0)}]", text)


def make_snippet_around_query(text: str, query: str, radius: int = 120, max_len: int = 240) -> str:
    """Erzeugt einen kurzen Ausschnitt rund um den Suchbegriff.

    - Sucht die erste (case-insensitive) Position des Suchbegriffs.
    - Nimmt etwas Kontext davor und danach.
    - Begrenzt die Gesamtlänge auf max_len Zeichen.
    """
    if not text:
        return ""

    lower_text = text.lower()
    lower_query = query.lower()
    idx = lower_text.find(lower_query)

    if idx == -1:
        # Kein direkter Treffer: einfach am Anfang abschneiden
        snippet = text.strip()
        return snippet[:max_len] + ("..." if len(snippet) > max_len else "")

    start = max(0, idx - radius)
    end = min(len(text), idx + len(query) + radius)
    snippet = text[start:end].strip()

    if len(snippet) > max_len:
        snippet = snippet[:max_len] + "..."

    # Präfix/Suffix mit "..." kennzeichnen, falls aus der Mitte geschnitten
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        if not snippet.endswith("..."):
            snippet = snippet + "..."

    return snippet


def call_ollama_summary(text: str, query: str) -> str | None:
    """Erzeugt eine kurze LLM-Zusammenfassung der Treffer mit Ollama (mistral).

    Nutzt nur einen gekürzten Ausschnitt des Textes, um Ressourcen zu schonen.
    """
    if not text:
        return None

    snippet = text[:2000]
    prompt = (
        "Fasse in 2-3 kurzen Stichpunkten zusammen, warum der folgende CV-Text "
        f"zum Suchbegriff '{query}' passt. Antworte auf Deutsch.\n\n" + snippet
    )

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "top_p": 0.9},
            },
            timeout=60,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("response", "").strip() or None
    except Exception as e:
        print(f"⚠ Fehler bei Ollama-Anfrage: {e}")
    return None


def main() -> int:
    print("=" * 80)
    print("Suche in allen CV-PDFs (candidates.cv_pdf)")
    print("=" * 80)

    # 1. Suchbegriff abfragen
    query = input("\nSuchbegriff: ").strip()
    if not query:
        print("\n✗ Kein Suchbegriff angegeben – Vorgang abgebrochen.")
        return 1

    # 2. Threshold abfragen (optional)
    threshold_input = input("Unscharfer Matching-Threshold (Standard 70): ").strip()
    if threshold_input:
        try:
            threshold = int(threshold_input)
        except ValueError:
            print("\n⚠ Ungültiger Threshold, verwende Standard 70.")
            threshold = 70
    else:
        threshold = 70

    # 3. Optional: LLM-Unterstützung aktivieren
    llm_enabled = False
    use_llm = input("LLM-Zusammenfassung mit Ollama (mistral) verwenden? (j/n): ").strip().lower()
    if use_llm in ["j", "ja", "y", "yes"]:
        llm_enabled = True

    # 4. DB-Verbindung
    try:
        conn = psycopg.connect(**DB_CONFIG)
    except Exception as e:
        print(f"\n✗ Fehler bei der Datenbankverbindung: {e}")
        return 1

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, first_name, last_name, cv_pdf
                FROM candidates
                WHERE cv_pdf IS NOT NULL
                ORDER BY id
                """
            )
            rows: List[Tuple[str, str, str, bytes]] = cur.fetchall()

        if not rows:
            print("\nℹ Keine Kandidaten mit CV-PDFs gefunden.")
            conn.close()
            return 0

        print(f"\n✓ {len(rows)} Kandidaten mit CV-PDF gefunden. Starte Suche ...")

        total_matches = 0
        for cand_id, first_name, last_name, cv_pdf in rows:
            text = pdf_bytes_to_text(cv_pdf)
            if not text:
                continue

            text_clean = clean_text(text)
            matches = syntactic_search(text_clean, query, threshold)

            if not matches:
                continue

            total_matches += 1
            print("\n" + "-" * 80)
            print(f"Kandidat {cand_id}: {first_name} {last_name}")
            print("Treffer:")
            for sentence in matches[:5]:  # max. 5 Sätze anzeigen
                snippet = make_snippet_around_query(sentence, query)
                highlighted = highlight_query(snippet, query)
                print(f"  • {highlighted}")
            if len(matches) > 5:
                print(f"  ... und {len(matches) - 5} weitere Sätze")

            # Optional: LLM-Zusammenfassung pro Kandidat
            if llm_enabled:
                joined_matches = " \n".join(matches[:10])  # Kontext für das LLM
                summary = call_ollama_summary(joined_matches, query)
                if summary:
                    print("  LLM-Zusammenfassung (mistral):")
                    for line in summary.splitlines():
                        print(f"    {line}")

        if total_matches == 0:
            print("\nKeine Treffer in den vorhandenen CV-PDFs gefunden.")
        else:
            print("\n" + "=" * 80)
            print(f"Fertig. Treffer bei {total_matches} Kandidat(en).")

        conn.close()
        return 0

    except Exception as e:
        print(f"\n✗ Unerwarteter Fehler: {e}")
        import traceback

        traceback.print_exc()
        try:
            conn.close()
        except Exception:
            pass
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
