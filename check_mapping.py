import pandas as pd

df = pd.read_excel('src/db communication/import/mapping_minicrm_postresql.xlsx')
print('Alle Mappings (PostgreSQL -> miniCRM):')
print('=' * 70)
for i, col in enumerate(df.columns):
    minicrm_col = df.iloc[1][i]
    if pd.notna(minicrm_col):
        print(f'{col:35s} -> {minicrm_col}')
    else:
        print(f'{col:35s} -> [KEIN MAPPING]')
