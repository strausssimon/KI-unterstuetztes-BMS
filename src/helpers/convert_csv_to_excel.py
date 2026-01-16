import pandas as pd

# CSV einlesen
csv_path = r"src\helpers\LeadDelta-Export.csv"
excel_path = r"src\helpers\LeadDelta-Export.xlsx"

# CSV zu DataFrame
df = pd.read_csv(csv_path)

# Als Excel speichern
df.to_excel(excel_path, index=False, sheet_name="LeadDelta Export")

print(f"Excel-Datei erstellt: {excel_path}")
