import csv
import random
import pandas as pd

first_names = [
    "Philipp", "Alexander", "Anna", "Marie", "Lena", "Jonas", "Maximilian",
    "Sophia", "Leon", "Paul", "Laura", "Julia", "Niklas", "Felix", "David",
    "Lukas", "Sarah", "Hannah", "Tim", "Jan", "Fabian", "Tobias", "Moritz",
    "Lisa", "Katharina", "Nina", "Markus", "Daniel", "Sebastian", "Florian",
    "Emma", "Mia", "Ben", "Noah", "Emilia", "Hannah", "Elias", "Finn",
    "Mila", "Ella", "Oskar", "Matteo", "Ida", "Mathilda", "Clara", "Sofia",
    "Charlotte", "Emily", "Henry", "Theo", "Jakob", "Louis", "Amelie",
    "Johanna", "Luise", "Anton", "Emil", "Lea", "Greta", "Frieda",
    "Leonard", "Jonathan", "Samuel", "Simon", "Melissa", "Vanessa",
    "Christian", "Michael", "Thomas", "Andreas", "Stefan", "Martin",
    "Oliver", "Frank", "Matthias", "Peter", "Klaus", "Jürgen", "Sabine",
    "Sandra", "Andrea", "Petra", "Claudia", "Susanne", "Monika", "Birgit"
]

last_names = [
    "Maier", "Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Wagner",
    "Becker", "Hoffmann", "Schäfer", "Koch", "Richter", "Klein", "Wolf",
    "Schröder", "Neumann", "Braun", "Zimmermann", "Hofmann", "Hartmann",
    "Lange", "Schmitz", "Werner", "Krause", "Meier", "Lehmann", "Schmid",
    "Schulz", "Kaiser", "Vogel", "Keller", "Günther", "Frank", "Berger",
    "Winkler", "Roth", "Beck", "Baumann", "Krüger", "Schubert", "Sommer",
    "Jung", "Hahn", "Vogel", "Schumacher", "Vogt", "Huber", "Böhm",
    "Kurz", "Arnold", "Stein", "Sauer", "Busch", "Horn", "Engel",
    "Herrmann", "Walter", "Böhm", "Krämer", "Ritter", "Schuster",
    "Schwarz", "Zimmermann", "Groß", "König", "Otto", "Seidel", "Ludwig",
    "Möller", "Albrecht", "Simon", "Scholz", "Peters", "Haas"
]

headline_titles = ["Dr.", "", "Prof. Dr.", "Dr. med.", "PD", "Dr. med."]
positions = [
    "Assistenzarzt", "Facharzt", "MTRA", "sonstige",
    "Oberarzt", "Chefarzt", "Ltd. OA", "Standortleiter", "Gesellschafter"
]
specialties = [
    "Diagnostische und Interventionelle Radiologie",
    "Neuroradiologie", "Kinderradiologie", "Mammographie",
    "Nuklearmedizin", "Orthopädie & UCH", "Anästhesie", "Pädiatrie",
    "Chirurgie", "Innere Medizin", "Pädiatrie/ Kindermedizin",
    "Psychiatrie", "Gynäkologie"
]


# Städte aus CSV laden
def load_cities_from_csv():
    """Lädt deutsche Städte aus der CSV-Datei"""
    csv_path = r"data\Staedte_Deutschland.csv"
    try:
        df = pd.read_csv(csv_path)
        # Duplikate entfernen basierend auf Stadt und Bundesland
        cities_df = df[['place', 'state']].drop_duplicates()
        # Liste von Tupeln erstellen (Stadt, Bundesland)
        cities = list(zip(cities_df['place'], cities_df['state']))
        return cities
    except Exception as e:
        print(f"Fehler beim Laden der Städte-CSV: {e}")
        # Fallback auf einige Standard-Städte
        return [
            ("Stuttgart", "Baden-Württemberg"),
            ("München", "Bayern"),
            ("Berlin", "Berlin"),
            ("Hamburg", "Hamburg"),
            ("Köln", "Nordrhein-Westfalen")
        ]


def random_date_connected():
    # ein zufälliges Datum (Jahr 2023–2026) im LinkedIn-Format
    year = random.randint(2023, 2026)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    hour = random.randint(8, 18)
    minute = random.randint(0, 59)
    return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}"


def generate_linkedin_url(first_name, last_name):
    base = f"{first_name.lower()}-{last_name.lower()}"
    suffix = random.randint(100000, 999999)
    return f"https://www.linkedin.com/in/{base}-{suffix}/"


def generate_profile_pic():
    # generische, zufällige Bild-URL im LinkedIn-Stil
    token = ''.join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=43))
    return (
        "https://media.licdn.com/dms/image/v2/"
        f"C5603AQF{token}/profile-displayphoto-shrink_200_200/"
        "0/1634918689088?e=2147483647&v=beta&t=ANtxAwI7SwAKbYJ-yaUuLBaL61Ea4ybtVAYfj1oFSCM"
    )


def main():
    filename = r"data\db\leaddelta\LeadDelta-Export-synthetic-contacts.csv"
    
    header = [
        "First Name", "Last Name", "Headline", "Job Title", "Company",
        "Location", "Industry", "Email", "Linkedin", "Profile Picture",
        "Languages", "Date of Birth", "Followers", "Enriched Private Email",
        "Enriched Business Email", "Enriched Phone", "Notes", "Tags",
        "Last contact date", "Date Connected", "Mutual Connection"
    ]
    
    # Städte aus CSV laden
    print("Lade deutsche Städte aus CSV...")
    cities = load_cities_from_csv()
    print(f"{len(cities)} Städte geladen.")
    
    num_rows = 500  # Anzahl der gewünschten Einträge
    
    with open(filename, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        
        for _ in range(num_rows):
            # 30% Chance für Doppelnamen im Vornamen
            if random.random() < 0.3:
                first = random.choice(first_names) + random.choice(first_names)
            else:
                first = random.choice(first_names)
            
            last = random.choice(last_names)
            
            title = random.choice(headline_titles)
            position = random.choice(positions)
            specialty = random.choice(specialties)
            
            if title:
                headline = f"{title} | {position} | {specialty} | EBIR"
            else:
                headline = f"{position} | {specialty} | EBIR"
            
            job_title = f"{position}, Klinik für {specialty}"
            
            city, state = random.choice(cities)
            country = "Germany"
            location_str = f"{country}, {city}, {state}, {country}"
            
            company = f"Klinikum {city}"
            industry = "Medical Practices"
            
            # einfache E-Mail-Generierung
            email = f"{first.lower()}.{last.lower()}@mail.de"
            
            linkedin_url = generate_linkedin_url(first, last)
            profile_pic_url = generate_profile_pic()
            
            languages = ""          # leer
            date_of_birth = ""      # leer
            followers = ""          # leer
            enriched_private = ""   # leer
            enriched_business = ""  # leer
            enriched_phone = ""     # leer
            notes = ""              # leer
            tags = "LinkedIn,LinkedIn 1st"
            last_contact_date = ""  # leer
            date_connected = random_date_connected()
            mutual_connection = "No"
            
            row = [
                first,
                last,
                headline,
                job_title,
                company,
                location_str,
                industry,
                email,
                linkedin_url,
                profile_pic_url,
                languages,
                date_of_birth,
                followers,
                enriched_private,
                enriched_business,
                enriched_phone,
                notes,
                tags,
                last_contact_date,
                date_connected,
                mutual_connection
            ]
            
            writer.writerow(row)
    
    print(f"Datei '{filename}' mit {num_rows} Einträgen erzeugt.")


if __name__ == "__main__":
    main()