import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox
import json
import traceback
import psycopg
import pandas as pd

# --------------------------------------------------
# PATH SETUP (allow imports from project root)
# --------------------------------------------------
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.db_config import DB_CONFIG
from src.GUI.Matching import (
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
from src.GUI.Strukturierter_Datenimport_LLM import (
    extract_candidate as llm_extract_candidate,
)
from src.GUI.mail_candidate import (
    generate_email_with_ollama as mail_generate_email_with_ollama,
    generate_fallback_email as mail_generate_fallback_email,
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

def get_column_type(conn, table_name, column_name):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s
        """, (table_name, column_name))
        row = cur.fetchone()
        return row[0] if row else None

def get_smallest_free_candidate_id(conn, id_is_text=False):
    with conn.cursor() as cur:
        if id_is_text:
            cur.execute("""
                SELECT id
                FROM candidates
                WHERE id ~ '^[0-9]+$'
                ORDER BY id::int
            """)
        else:
            cur.execute("SELECT id FROM candidates ORDER BY id")
        rows = cur.fetchall()
    next_id = 1
    for (cid,) in rows:
        if cid is None:
            continue
        try:
            cid_int = int(cid)
        except (TypeError, ValueError):
            continue
        if cid_int == next_id:
            next_id += 1
        elif cid_int > next_id:
            break
    return str(next_id) if id_is_text else next_id

def insert_candidate_record(payload, assign_min_free_id=False):
    conn = psycopg.connect(**DB_CONFIG)
    try:
        columns = get_candidates_columns(conn)
        allowed = list(columns)
        record = {k: payload.get(k) for k in allowed if k in payload}
        if assign_min_free_id and "id" not in record and "id" in allowed:
            id_type = get_column_type(conn, "candidates", "id")
            id_is_text = id_type in {"text", "character varying", "character"}
            record["id"] = get_smallest_free_candidate_id(conn, id_is_text=id_is_text)
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

def fetch_candidate_by_id(conn, candidate_id):
    return fetch_row_safe(conn, "candidates", candidate_id)

def fetch_job_by_id(conn, job_id):
    return fetch_row_safe(conn, "jobs", job_id)

def fetch_candidate_for_email(conn, candidate_id):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, first_name, last_name, e_mail, qualification
            FROM candidates
            WHERE id::text = %s;
        """, (str(candidate_id),))
        row = cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))

def fetch_job_for_email(conn, job_id):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, position, department, ort, klinik, gehalt_von, gehalt_bis
            FROM jobs
            WHERE id::text = %s;
        """, (str(job_id),))
        row = cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))

def get_table_columns(conn, table_name):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position;
        """, (table_name,))
        return cur.fetchall()

def fetch_row_safe(conn, table_name, row_id):
    columns_info = get_table_columns(conn, table_name)
    if not columns_info:
        return None
    timestamp_columns = [
        col for col, dtype in columns_info
        if "timestamp" in dtype.lower() or "date" in dtype.lower()
    ]
    select_parts = []
    for col, _dtype in columns_info:
        if col in timestamp_columns:
            select_parts.append(f"""
                CASE
                    WHEN {col} IS NOT NULL
                         AND EXTRACT(YEAR FROM {col}) BETWEEN 1900 AND 9999
                    THEN {col}::text
                    ELSE NULL
                END as {col}
            """)
        else:
            select_parts.append(col)
    select_clause = ", ".join(select_parts)
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {select_clause} FROM {table_name} WHERE id = %s;",
            (row_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))

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
        "skills_gemeinsam",
        "skills_fehlend",
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
    ("skills_gemeinsam", 220),
    ("skills_fehlend", 220),
    ("datenvollstaendigkeit", 160),
    ("fehlende_daten", 160),
]:
    # Deutsche Spaltenüberschriften für die neuen Skill-Spalten
    heading_text = col
    if col == "skills_gemeinsam":
        heading_text = "Übereinstimmende Skills"
    elif col == "skills_fehlend":
        heading_text = "Fehlende Job-Skills"

    matching_results.heading(col, text=heading_text)
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
            r.get("skills_gemeinsam") or "",
            r.get("skills_fehlend") or "",
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

ttk.Label(search_controls, text="Sonstige Anforderungen").pack(anchor="w")
search_other_input = tk.Text(search_controls, height=2)
search_other_input.pack(fill="x", pady=(4, 8))

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
        "long_note",
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
    ("long_note", 320),
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
            r.get("long_note"),
        ])

def run_search():
    question = search_input.get("1.0", tk.END).strip()
    other_requirements = search_other_input.get("1.0", tk.END).strip()
    if not question and not other_requirements:
        messagebox.showerror(
            "Intelligente Suche",
            "Bitte eine Suchanfrage oder sonstige Anforderungen eingeben."
        )
        return
    try:
        intent = search_extract_intent(question) if question else {}
        if other_requirements:
            intent["sonstige_anforderungen"] = other_requirements
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
                new_id = insert_candidate_record(payload, assign_min_free_id=True)
                messagebox.showinfo("Datenimport LLM", f"Datensatz hinzugefuegt (ID {new_id}).")
                refresh_candidates_table()
            except Exception as exc:
                messagebox.showerror("Datenimport LLM", f"DB-Insert fehlgeschlagen:\n{exc}")
    except Exception as exc:
        messagebox.showerror("Datenimport LLM", f"Extraktion fehlgeschlagen:\n{exc}")

ttk.Button(import_controls, text="Extrahieren", command=run_llm_extract)\
    .pack(anchor="w")

# --------------------------------------------------
# E-MAIL GENERIERUNG TAB
# --------------------------------------------------
email_tab = ttk.Frame(notebook)
notebook.add(email_tab, text="E-Mails")

email_controls = ttk.Frame(email_tab)
email_controls.pack(fill="x", padx=10, pady=10)

ttk.Label(email_controls, text="Job-ID").grid(row=0, column=0, sticky="w")
email_job_id = ttk.Entry(email_controls, width=12)
email_job_id.grid(row=0, column=1, sticky="w", padx=(6, 18))

ttk.Label(email_controls, text="Kandidaten-IDs (kommasepariert)").grid(
    row=0, column=2, sticky="w"
)
email_candidate_ids = ttk.Entry(email_controls, width=40)
email_candidate_ids.grid(row=0, column=3, sticky="w", padx=(6, 0))

email_use_llm = tk.BooleanVar(value=True)
email_debug = tk.BooleanVar(value=False)

email_status = ttk.Label(email_controls, text="")
email_status.grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 0))

email_output = tk.Text(email_tab, height=16, state="disabled", bg="white")
email_output.pack(fill="both", expand=True, padx=10, pady=(0, 10))

def parse_candidate_ids(raw):
    if not raw.strip():
        return []
    ids = []
    for part in raw.replace(",", " ").split():
        p = part.strip()
        if not p:
            continue
        try:
            ids.append(int(p))
        except ValueError:
            continue
    return ids

def append_email_output(text):
    email_output.configure(state="normal")
    email_output.insert(tk.END, text + "\n")
    email_output.configure(state="disabled")
    email_output.see(tk.END)

def run_email_generation():
    try:
        job_id_raw = email_job_id.get().strip()
        if not job_id_raw:
            messagebox.showerror("E-Mails", "Bitte Job-ID eingeben.")
            return
        try:
            job_id = int(job_id_raw)
        except ValueError:
            messagebox.showerror("E-Mails", "Job-ID ist keine Zahl.")
            return

        candidate_ids = parse_candidate_ids(email_candidate_ids.get())
        if not candidate_ids and matching_state.get("results"):
            candidate_ids = [r.get("id") for r in matching_state["results"] if r.get("id")]

        if not candidate_ids:
            messagebox.showerror("E-Mails", "Bitte Kandidaten-IDs angeben oder Matching ausfuehren.")
            return

        conn = psycopg.connect(**DB_CONFIG)
        try:
            job = fetch_job_for_email(conn, job_id)
            if not job:
                messagebox.showerror("E-Mails", f"Job {job_id} nicht gefunden.")
                return
            email_output.configure(state="normal")
            email_output.delete("1.0", tk.END)
            email_output.configure(state="disabled")
            use_llm = email_use_llm.get()
            debug = email_debug.get()
            generated = 0
            for cid in candidate_ids:
                candidate = fetch_candidate_for_email(conn, cid)
                if not candidate:
                    append_email_output(f"[{cid}] Kandidat nicht gefunden.")
                    continue
                try:
                    if debug:
                        append_email_output(f"[DEBUG] job_id={job_id}, candidate_id={cid}")
                        append_email_output(f"[DEBUG] job_keys={', '.join(sorted(job.keys()))}")
                        append_email_output(f"[DEBUG] candidate_keys={', '.join(sorted(candidate.keys()))}")
                    if use_llm:
                        betreff, mail = mail_generate_email_with_ollama(candidate, job)
                        if not betreff or not mail:
                            betreff, mail = mail_generate_fallback_email(candidate, job)
                    else:
                        betreff, mail = mail_generate_fallback_email(candidate, job)
                    if not betreff or not mail:
                        append_email_output(f"[{cid}] Keine E-Mail generiert (leere Antwort).")
                        continue
                    append_email_output(
                        f"Kandidat {cid}: {candidate.get('first_name', '')} {candidate.get('last_name', '')}"
                    )
                    append_email_output(f"BETREFF: {betreff}")
                    append_email_output("MAIL:")
                    append_email_output(mail)
                    append_email_output("-" * 80)
                    generated += 1
                except Exception as exc:
                    append_email_output(f"[{cid}] Fehler bei E-Mail: {exc}")
                    if debug:
                        append_email_output(traceback.format_exc())
                    append_email_output("-" * 80)
            email_status.configure(text=f"{generated} E-Mails generiert")
        finally:
            conn.close()
    except Exception as exc:
        messagebox.showerror("E-Mails", f"Fehler bei der E-Mail-Generierung:\n{exc}")

ttk.Button(email_controls, text="E-Mails generieren", command=run_email_generation).grid(
    row=2, column=0, sticky="w", pady=(8, 0)
)

# --------------------------------------------------
# START
# --------------------------------------------------
root.mainloop()
