import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox
import json
import psycopg
import pandas as pd

# --------------------------------------------------
# PATH SETUP (allow imports from project root)
# --------------------------------------------------
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.db_config import DB_CONFIG
from GUI.Matching_2 import (
    load_job as matching_load_job,
    load_candidates as matching_load_candidates,
    match_candidates as matching_match_candidates,
    export_to_excel as matching_export_to_excel,
)
from src.GUI.intelligente_Suchabfrage_7 import (
    extract_intent as search_extract_intent,
    load_candidates as search_load_candidates,
    match_candidates as search_match_candidates,
    export_to_excel as search_export_to_excel,
)
from GUI.Strukturierter_Datenimport_LLM_1 import (
    extract_candidate as llm_extract_candidate,
)

# --------------------------------------------------
# DATABASE FUNCTIONS (table views)
# --------------------------------------------------
def load_jobs_table():
    conn = psycopg.connect(**DB_CONFIG)
    df = pd.read_sql("""
        SELECT id, position, department, ort, gehalt_von, gehalt_bis
        FROM jobs
        ORDER BY id
    """, conn)
    conn.close()
    return df


def load_candidates_table():
    conn = psycopg.connect(**DB_CONFIG)
    df = pd.read_sql("""
        SELECT id, first_name, last_name, status, position_now, department,
               gehaltswunsch, wohnort, wunscharbeitsort, regionale_verfuegbarkeit
        FROM candidates
        ORDER BY id
    """, conn)
    conn.close()
    return df

def get_candidates_columns(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'candidates'
        ORDER BY ordinal_position
    """)
    cols = [r[0] for r in cur.fetchall()]
    cur.close()
    return cols

def insert_candidate_record(payload):
    conn = psycopg.connect(**DB_CONFIG)
    try:
        columns = get_candidates_columns(conn)
        allowed = [c for c in columns if c != "id"]
        record = {k: payload.get(k) for k in allowed if k in payload}
        if not record:
            raise ValueError("Keine passenden Felder fuer candidates gefunden.")
        cols_sql = ", ".join(record.keys())
        placeholders = ", ".join(["%s"] * len(record))
        values = list(record.values())
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO candidates ({cols_sql}) VALUES ({placeholders}) RETURNING id;",
                values,
            )
            new_id = cur.fetchone()[0]
        conn.commit()
        return new_id
    finally:
        conn.close()

# --------------------------------------------------
# MAIN WINDOW
# --------------------------------------------------
root = tk.Tk()
root.title("Bewerbermanagementsystem")
root.geometry("1500x850")
root.configure(bg="#eef1f5")

# --------------------------------------------------
# STYLE
# --------------------------------------------------
style = ttk.Style()
style.theme_use("default")

style.configure("Treeview",
                background="white",
                foreground="#1f2933",
                rowheight=26,
                fieldbackground="white",
                font=("Segoe UI", 10))

style.configure("Treeview.Heading",
                font=("Segoe UI", 10, "bold"),
                background="#e5e7eb")

style.configure("TNotebook.Tab",
                font=("Segoe UI", 11),
                padding=8)

style.configure("Sidebar.TFrame", background="#f8fafc")
style.configure("Chat.TFrame", background="#f1f5f9")

# --------------------------------------------------
# MAIN SPLIT
# --------------------------------------------------
main_pane = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
main_pane.pack(fill="both", expand=True)

# --------------------------------------------------
# LEFT: FILTER SIDEBAR
# --------------------------------------------------
filter_frame = ttk.Frame(main_pane, width=260, style="Sidebar.TFrame")
main_pane.add(filter_frame, weight=1)

tk.Label(filter_frame, text="Filter",
         font=("Segoe UI", 13, "bold"),
         bg="#f8fafc").pack(anchor="w", padx=15, pady=(15, 10))

filters = {}

def add_filter(label):
    tk.Label(filter_frame, text=label, bg="#f8fafc",
             font=("Segoe UI", 9)).pack(anchor="w", padx=15)
    entry = ttk.Entry(filter_frame)
    entry.pack(fill="x", padx=15, pady=(0, 10))
    filters[label] = entry

add_filter("Position")
add_filter("Fachbereich")
add_filter("Ort")
add_filter("Status")

# --------------------------------------------------
# CENTER: DATA AREA
# --------------------------------------------------
data_frame = ttk.Frame(main_pane)
main_pane.add(data_frame, weight=4)

notebook = ttk.Notebook(data_frame)
notebook.pack(fill="both", expand=True, padx=5, pady=5)

# --------------------------------------------------
# JOBS TAB
# --------------------------------------------------
jobs_tab = ttk.Frame(notebook)
notebook.add(jobs_tab, text="Jobs")

jobs_df = load_jobs_table()
jobs_table = ttk.Frame(jobs_tab)
jobs_table.pack(fill="both", expand=True)
jobs_tree = ttk.Treeview(jobs_table, columns=list(jobs_df.columns), show="headings")
jobs_scroll_y = ttk.Scrollbar(jobs_table, orient="vertical", command=jobs_tree.yview)
jobs_scroll_x = ttk.Scrollbar(jobs_table, orient="horizontal", command=jobs_tree.xview)
jobs_tree.configure(yscrollcommand=jobs_scroll_y.set, xscrollcommand=jobs_scroll_x.set)
jobs_tree.grid(row=0, column=0, sticky="nsew")
jobs_scroll_y.grid(row=0, column=1, sticky="ns")
jobs_scroll_x.grid(row=1, column=0, sticky="ew")
jobs_table.rowconfigure(0, weight=1)
jobs_table.columnconfigure(0, weight=1)

for col in jobs_df.columns:
    jobs_tree.heading(col, text=col)
    jobs_tree.column(col, width=130)

def render_jobs(df):
    jobs_tree.delete(*jobs_tree.get_children())
    for _, row in df.iterrows():
        jobs_tree.insert("", "end", values=list(row))

render_jobs(jobs_df)

# --------------------------------------------------
# CANDIDATES TAB
# --------------------------------------------------
cand_tab = ttk.Frame(notebook)
notebook.add(cand_tab, text="Kandidaten")

cand_df = load_candidates_table()
cand_table = ttk.Frame(cand_tab)
cand_table.pack(fill="both", expand=True)
cand_tree = ttk.Treeview(cand_table, columns=list(cand_df.columns), show="headings")
cand_scroll_y = ttk.Scrollbar(cand_table, orient="vertical", command=cand_tree.yview)
cand_scroll_x = ttk.Scrollbar(cand_table, orient="horizontal", command=cand_tree.xview)
cand_tree.configure(yscrollcommand=cand_scroll_y.set, xscrollcommand=cand_scroll_x.set)
cand_tree.grid(row=0, column=0, sticky="nsew")
cand_scroll_y.grid(row=0, column=1, sticky="ns")
cand_scroll_x.grid(row=1, column=0, sticky="ew")
cand_table.rowconfigure(0, weight=1)
cand_table.columnconfigure(0, weight=1)

for col in cand_df.columns:
    cand_tree.heading(col, text=col)
    cand_tree.column(col, width=150)

def render_candidates(df):
    cand_tree.delete(*cand_tree.get_children())
    for _, row in df.iterrows():
        cand_tree.insert("", "end", values=list(row))

render_candidates(cand_df)

# --------------------------------------------------
# FILTER LOGIC
# --------------------------------------------------
def filter_contains(df, column, term):
    if not term:
        return df
    return df[df[column].fillna("").astype(str).str.contains(term, case=False, na=False)]

def refresh_candidates_table():
    global cand_df
    cand_df = load_candidates_table()
    render_candidates(cand_df)

def refresh_jobs_table():
    global jobs_df
    jobs_df = load_jobs_table()
    render_jobs(jobs_df)

def apply_filters():
    global cand_df, jobs_df
    pos = filters["Position"].get().strip()
    dept = filters["Fachbereich"].get().strip()
    ort = filters["Ort"].get().strip()
    status = filters["Status"].get().strip()

    active_tab = notebook.select()
    if active_tab == str(cand_tab):
        cand_df = load_candidates_table()
        df = cand_df.copy()
        df = filter_contains(df, "position_now", pos)
        df = filter_contains(df, "department", dept)
        df = filter_contains(df, "wohnort", ort)
        df = filter_contains(df, "status", status)
        render_candidates(df)
    elif active_tab == str(jobs_tab):
        jobs_df = load_jobs_table()
        df = jobs_df.copy()
        df = filter_contains(df, "position", pos)
        df = filter_contains(df, "department", dept)
        df = filter_contains(df, "ort", ort)
        render_jobs(df)

def reset_filters():
    for entry in filters.values():
        entry.delete(0, tk.END)
    active_tab = notebook.select()
    if active_tab == str(cand_tab):
        refresh_candidates_table()
    elif active_tab == str(jobs_tab):
        refresh_jobs_table()

ttk.Button(filter_frame, text="Filter anwenden", command=apply_filters)\
    .pack(fill="x", padx=15, pady=(10, 5))

ttk.Button(filter_frame, text="Filter zuruecksetzen",
           command=reset_filters)\
    .pack(fill="x", padx=15)

# --------------------------------------------------
# MATCHING TAB (Job -> Kandidaten)
# --------------------------------------------------
matching_tab = ttk.Frame(notebook)
notebook.add(matching_tab, text="Matching")

matching_state = {"job": None, "results": []}

matching_controls = ttk.Frame(matching_tab)
matching_controls.pack(fill="x", padx=10, pady=10)

ttk.Label(matching_controls, text="Stellen-ID").pack(side="left")
matching_job_id = ttk.Entry(matching_controls, width=12)
matching_job_id.pack(side="left", padx=(6, 12))

matching_status = ttk.Label(matching_controls, text="")
matching_status.pack(side="left", padx=10)

matching_results = ttk.Treeview(
    matching_tab,
    columns=[
        "id",
        "name",
        "position_now",
        "department",
        "gehaltswunsch",
        "gehalts_score",
        "fahrtweg_score",
        "fahrtweg_km",
        "gesamt_score",
        "datenvollstaendigkeit",
        "fehlende_daten",
    ],
    show="headings",
)
matching_results.pack(fill="both", expand=True, padx=10, pady=(0, 10))

for col, width in [
    ("id", 70),
    ("name", 160),
    ("position_now", 140),
    ("department", 140),
    ("gehaltswunsch", 120),
    ("gehalts_score", 110),
    ("fahrtweg_score", 120),
    ("fahrtweg_km", 110),
    ("gesamt_score", 110),
    ("datenvollstaendigkeit", 160),
    ("fehlende_daten", 160),
]:
    matching_results.heading(col, text=col)
    matching_results.column(col, width=width)

def render_matching_results(results):
    matching_results.delete(*matching_results.get_children())
    for r in results:
        matching_results.insert("", "end", values=[
            r.get("id"),
            r.get("name"),
            r.get("position_now"),
            r.get("department"),
            r.get("gehaltswunsch"),
            r.get("gehalts_score"),
            r.get("fahrtweg_score"),
            r.get("fahrtweg_km"),
            r.get("gesamt_score"),
            f"{int((r.get('datenvollstaendigkeit') or 0) * 100)}%",
            ", ".join(r.get("fehlende_daten") or []),
        ])

def run_matching():
    job_id = matching_job_id.get().strip()
    if not job_id:
        messagebox.showerror("Matching", "Bitte eine Stellen-ID eingeben.")
        return
    try:
        job = matching_load_job(job_id)
        candidates = matching_load_candidates()
        results = matching_match_candidates(job, candidates)
        matching_state["job"] = job
        matching_state["results"] = results
        render_matching_results(results)
        matching_status.configure(text=f"{len(results)} Kandidaten gefunden")
    except Exception as exc:
        messagebox.showerror("Matching", f"Fehler beim Matching:\n{exc}")

ttk.Button(matching_controls, text="Matching starten", command=run_matching)\
    .pack(side="left")

matching_export = ttk.Frame(matching_tab)
matching_export.pack(fill="x", padx=10, pady=(0, 10))

ttk.Label(matching_export, text="Export Anzahl (leer = alle)").pack(side="left")
matching_export_count = ttk.Entry(matching_export, width=8)
matching_export_count.pack(side="left", padx=6)

def export_matching():
    job = matching_state.get("job")
    results = matching_state.get("results") or []
    if not job or not results:
        messagebox.showerror("Matching", "Keine Ergebnisse zum Exportieren.")
        return
    count_raw = matching_export_count.get().strip()
    if count_raw:
        try:
            count = int(count_raw)
        except ValueError:
            messagebox.showerror("Matching", "Export-Anzahl ist keine Zahl.")
            return
        if count < 1:
            messagebox.showerror("Matching", "Export-Anzahl muss > 0 sein.")
            return
        results_to_export = results[:count]
    else:
        results_to_export = results
    try:
        filepath = matching_export_to_excel(job, None, results_to_export)
        if filepath:
            messagebox.showinfo("Matching", f"Excel exportiert:\n{filepath}")
    except Exception as exc:
        messagebox.showerror("Matching", f"Export fehlgeschlagen:\n{exc}")

ttk.Button(matching_export, text="Excel exportieren", command=export_matching)\
    .pack(side="left", padx=8)

# --------------------------------------------------
# INTELLIGENTE SUCHE TAB
# --------------------------------------------------
search_tab = ttk.Frame(notebook)
notebook.add(search_tab, text="Intelligente Suche")

search_state = {"intent": None, "results_raw": [], "results": []}

search_controls = ttk.Frame(search_tab)
search_controls.pack(fill="x", padx=10, pady=10)

ttk.Label(search_controls, text="Suchanfrage").pack(anchor="w")
search_input = tk.Text(search_controls, height=3)
search_input.pack(fill="x", pady=(4, 8))

search_status = ttk.Label(search_controls, text="")
search_status.pack(anchor="w")

search_results = ttk.Treeview(
    search_tab,
    columns=[
        "kandidat_id",
        "name",
        "position",
        "fachbereich",
        "wohnort",
        "wunscharbeitsort",
        "entfernung_km",
    ],
    show="headings",
)
search_results.pack(fill="both", expand=True, padx=10, pady=(0, 10))

for col, width in [
    ("kandidat_id", 90),
    ("name", 160),
    ("position", 140),
    ("fachbereich", 140),
    ("wohnort", 160),
    ("wunscharbeitsort", 180),
    ("entfernung_km", 110),
]:
    search_results.heading(col, text=col)
    search_results.column(col, width=width)

def render_search_results(results):
    search_results.delete(*search_results.get_children())
    for r in results:
        search_results.insert("", "end", values=[
            r.get("kandidat_id"),
            r.get("name"),
            r.get("position"),
            r.get("fachbereich"),
            r.get("wohnort"),
            r.get("wunscharbeitsort"),
            r.get("entfernung_km"),
        ])

def run_search():
    question = search_input.get("1.0", tk.END).strip()
    if not question:
        messagebox.showerror("Intelligente Suche", "Bitte eine Suchanfrage eingeben.")
        return
    try:
        intent = search_extract_intent(question)
        candidates = search_load_candidates()
        results, results_raw = search_match_candidates(intent, candidates)
        search_state["intent"] = intent
        search_state["results_raw"] = results_raw
        search_state["results"] = results
        render_search_results(results)
        search_status.configure(text=f"{len(results)} Kandidaten gefunden")
    except Exception as exc:
        messagebox.showerror("Intelligente Suche", f"Fehler bei der Suche:\n{exc}")

ttk.Button(search_controls, text="Suchen", command=run_search).pack(anchor="w")

def export_search():
    intent = search_state.get("intent")
    results_raw = search_state.get("results_raw") or []
    if not intent or not results_raw:
        messagebox.showerror("Intelligente Suche", "Keine Ergebnisse zum Exportieren.")
        return
    try:
        search_export_to_excel(intent, results_raw)
        messagebox.showinfo("Intelligente Suche", "Excel exportiert.")
    except Exception as exc:
        messagebox.showerror("Intelligente Suche", f"Export fehlgeschlagen:\n{exc}")

ttk.Button(search_controls, text="Excel exportieren", command=export_search)\
    .pack(anchor="w", pady=(6, 0))

# --------------------------------------------------
# STRUKTURIERTER DATENIMPORT (LLM) TAB
# --------------------------------------------------
import_tab = ttk.Frame(notebook)
notebook.add(import_tab, text="Datenimport LLM")

import_controls = ttk.Frame(import_tab)
import_controls.pack(fill="x", padx=10, pady=10)

ttk.Label(import_controls, text="Freitext").pack(anchor="w")
import_input = tk.Text(import_controls, height=6)
import_input.pack(fill="x", pady=(4, 8))

import_output = tk.Text(import_tab, height=12, state="disabled", bg="white")
import_output.pack(fill="both", expand=True, padx=10, pady=(0, 10))

def run_llm_extract():
    raw_text = import_input.get("1.0", tk.END).strip()
    if not raw_text:
        messagebox.showerror("Datenimport LLM", "Bitte Freitext eingeben.")
        return
    try:
        candidate = llm_extract_candidate(raw_text)
        payload = candidate.model_dump() if hasattr(candidate, "model_dump") else candidate.dict()
        formatted = json.dumps(payload, indent=2, ensure_ascii=False)
        import_output.configure(state="normal")
        import_output.delete("1.0", tk.END)
        import_output.insert(tk.END, formatted)
        import_output.configure(state="disabled")
        if messagebox.askyesno("Datenimport LLM", "Datensatz zur DB hinzufuegen?"):
            try:
                new_id = insert_candidate_record(payload)
                messagebox.showinfo("Datenimport LLM", f"Datensatz hinzugefuegt (ID {new_id}).")
                refresh_candidates_table()
            except Exception as exc:
                messagebox.showerror("Datenimport LLM", f"DB-Insert fehlgeschlagen:\n{exc}")
    except Exception as exc:
        messagebox.showerror("Datenimport LLM", f"Extraktion fehlgeschlagen:\n{exc}")

ttk.Button(import_controls, text="Extrahieren", command=run_llm_extract)\
    .pack(anchor="w")

# --------------------------------------------------
# RIGHT: CHAT SIDEBAR
# --------------------------------------------------
chat_frame = ttk.Frame(main_pane, width=360, style="Chat.TFrame")
main_pane.add(chat_frame, weight=1)

tk.Label(chat_frame, text="LLM Assistenz",
         font=("Segoe UI", 13, "bold"),
         bg="#f1f5f9").pack(anchor="w", padx=15, pady=(15, 5))

chat_display = tk.Text(chat_frame, wrap="word", state="disabled",
                       bg="white", font=("Segoe UI", 10))
chat_display.pack(fill="both", expand=True, padx=15)

chat_input = ttk.Entry(chat_frame)
chat_input.pack(fill="x", padx=15, pady=10)

def send_msg():
    msg = chat_input.get().strip()
    if not msg:
        return
    chat_display.configure(state="normal")
    chat_display.insert(tk.END, f"User: {msg}\nLLM: (LLM folgt spaeter)\n\n")
    chat_display.configure(state="disabled")
    chat_display.see(tk.END)
    chat_input.delete(0, tk.END)

ttk.Button(chat_frame, text="Senden", command=send_msg)\
    .pack(padx=15, pady=(0, 15))

# --------------------------------------------------
# START
# --------------------------------------------------
root.mainloop()
