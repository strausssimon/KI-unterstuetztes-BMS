"""Prüfe Excel-Datei Struktur"""
import pandas as pd

JOBS_FILE = r"data\db\miniCRM\jobs_examples.xlsx"
MAPPING_FILE = r"src\PostreSQL\import\mapping_minicrm_postresql_jobs.xlsx"

print("=== Jobs Excel Datei ===")
df_jobs = pd.read_excel(JOBS_FILE)
print(f"\nAnzahl Zeilen: {len(df_jobs)}")
print(f"\nSpaltennamen:")
for col in df_jobs.columns:
    print(f"  - '{col}'")
print(f"\nErste Zeile:")
print(df_jobs.head(1))

print("\n\n=== Mapping Excel Datei ===")
df_mapping = pd.read_excel(MAPPING_FILE)
print(f"\nPostgreSQL Spalten (Spaltennamen):")
for col in df_mapping.columns:
    print(f"  - '{col}'")
print(f"\nminiCRM Spalten (erste Zeile):")
first_row = df_mapping.iloc[0]
for i, val in enumerate(first_row):
    if pd.notna(val):
        print(f"  - '{val}' → {df_mapping.columns[i]}")
