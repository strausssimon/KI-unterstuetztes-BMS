import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Beispieldaten für Bewerber
bewerber_daten = {
    'Vorname': [
        'Max',
        'Anna',
        'Thomas',
        'Sarah',
        'Michael',
        'Julia',
        'David',
        'Laura',
        'Stefan',
        'Maria'
    ],
    'Nachname': [
        'Müller',
        'Schmidt',
        'Weber',
        'Meyer',
        'Wagner',
        'Becker',
        'Schulz',
        'Hoffmann',
        'Koch',
        'Bauer'
    ],
    'Adresse': [
        'Hauptstraße 12, 10115 Berlin',
        'Lindenweg 5, 80331 München',
        'Bahnhofstraße 23, 50667 Köln',
        'Gartenweg 8, 20095 Hamburg',
        'Kirchplatz 15, 60311 Frankfurt',
        'Schulstraße 34, 70173 Stuttgart',
        'Marktplatz 7, 01067 Dresden',
        'Bergstraße 19, 30159 Hannover',
        'Seestraße 42, 04109 Leipzig',
        'Waldweg 11, 90402 Nürnberg'
    ],
    'Email': [
        'max.mueller@email.de',
        'anna.schmidt@email.de',
        'thomas.weber@email.de',
        'sarah.meyer@email.de',
        'michael.wagner@email.de',
        'julia.becker@email.de',
        'david.schulz@email.de',
        'laura.hoffmann@email.de',
        'stefan.koch@email.de',
        'maria.bauer@email.de'
    ],
    'Telefon': [
        '+49 30 12345678',
        '+49 89 23456789',
        '+49 221 34567890',
        '+49 40 45678901',
        '+49 69 56789012',
        '+49 711 67890123',
        '+49 351 78901234',
        '+49 511 89012345',
        '+49 341 90123456',
        '+49 911 01234567'
    ],
    'Stelle': [
        'Softwareentwickler',
        'Marketing Manager',
        'Softwareentwickler',
        'Projektmanager',
        'Data Analyst',
        'Marketing Manager',
        'Softwareentwickler',
        'HR Manager',
        'Data Analyst',
        'Projektmanager'
    ]
}

# DataFrame erstellen
df = pd.DataFrame(bewerber_daten)

# Parquet-Datei erstellen
output_path = 'data/bewerber_beispiel.parquet'
df.to_parquet(output_path, engine='pyarrow', compression='snappy', index=False)

print(f"Parquet-Datei erfolgreich erstellt: {output_path}")
print(f"\nAnzahl der Bewerber: {len(df)}")
print("\nVorschau der Daten:")
print(df.to_string(index=False))
