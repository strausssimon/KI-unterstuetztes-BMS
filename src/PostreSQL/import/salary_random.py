'''
Docstring for PostreSQL.import.salary_random
# --------------------------------------------------
# POSITIONEN UND FACHBEREICHE
# --------------------------------------------------
POSITIONEN = [
    "assistenzarzt",
    "facharzt",
    "oberarzt",
    "leitender oberarzt",
    "chefarzt",
    "standortleiter",
    "gesellschafter"
]

FACHAUSWAHL = [
    "anästhesie",
    "chirurgie",
    "gynäkologie",
    "innere medizin",
    "kinderradiologie",
    "mammographie",
    "neuroradiologie",
    "nuklearmedizin",
    "orthopädie & uch",
    "pädiatrie/kindermedizin",
    "psychiatrie",
    "radiologie",
    "strahlentherapie"
]

# --------------------------------------------------
# KARRIEREPFADE
# --------------------------------------------------
KARRIERE_PFADE = {
    "assistenzarzt": {"assistenzarzt", "facharzt"},
    "facharzt": {"facharzt", "oberarzt", "leitender oberarzt", "chefarzt", "standortleiter"},
    "oberarzt": {"oberarzt", "leitender oberarzt", "chefarzt", "standortleiter"},
    "leitender oberarzt": {"leitender oberarzt", "chefarzt", "standortleiter", "gesellschafter"},
    "chefarzt": {"chefarzt", "standortleiter", "gesellschafter"},
    "standortleiter": {"standortleiter", "gesellschafter"},
    "gesellschafter": {"gesellschafter"}
}

# --------------------------------------------------
# LÄNDER (Name -> Abkürzungen)
# --------------------------------------------------
LAENDER = {
    "deutschland": ["deutschland", "de", "ger", "germany"],
    "schweiz": ["schweiz", "ch", "switzerland"],
    "österreich": ["österreich", "oesterreich", "at", "austria"],
    "frankreich": ["frankreich", "fr", "france"],
    "belgien": ["belgien", "be", "belgium"],
    "niederlande": ["niederlande", "nl", "netherlands", "holland"],
    "luxemburg": ["luxemburg", "lu", "luxembourg"],
    "dänemark": ["dänemark", "daenemark", "dk", "denmark"],
    "polen": ["polen", "pl", "poland"],
    "tschechien": ["tschechien", "cz", "czech", "tschechische republik"]
}

'''
