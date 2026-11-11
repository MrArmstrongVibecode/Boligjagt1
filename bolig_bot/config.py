"""Kriterier. Ret her - resten af programmet læser kun fra denne fil.

Øverst står DINE kriterier (kanalen "dig"). Nederst under KANALER står
gruppens kriterier. Boligerne hentes kun én gang pr. kørsel, uanset hvor
mange kanaler der er."""

# --- Filter -----------------------------------------------------------------

MIN_ROOMS = 2
MAX_RENT = 16_000          # kr. pr. måned
MIN_SIZE = None            # m², None = ingen grænse

# Områder du vil have besked om.
# "postnumre": tal eller (fra, til)-intervaller (begge inklusive).
# "navne": stavemåder der kan stå i en boligs bydel/titel (små bogstaver).
# Postnummer vinder altid: kendes postnummeret, bruges kun det.
AREAS = {
    "Indre By": {
        "postnumre": [(1050, 1399), (1450, 1473)],          # København K
        "navne": ["indre by", "city centre", "city center", "københavn k", "kbh k"],
    },
    "Christianshavn": {
        "postnumre": [(1400, 1449)],
        "navne": ["christianshavn"],
    },
    "Vesterbro": {
        "postnumre": [(1500, 1799)],                         # København V
        "navne": ["vesterbro", "københavn v", "kbh v"],
    },
    "Frederiksberg": {
        "postnumre": [(1800, 1999), 2000],                   # Frederiksberg C + 2000
        "navne": ["frederiksberg"],
    },
    "Østerbro": {
        "postnumre": [2100, 2150],                           # 2150 = Nordhavn
        "navne": ["østerbro", "oesterbro", "osterbro", "nordhavn", "københavn ø", "kbh ø"],
    },
    "Nørrebro": {
        "postnumre": [2200],
        "navne": ["nørrebro", "noerrebro", "norrebro", "københavn n", "kbh n"],
    },
    "Amagerbro": {
        # OBS: 2300 dækker også Islands Brygge, Amager Øst og Sundby.
        # Fjern 2300 hvis du kun vil have navne-match på "Amagerbro".
        "postnumre": [2300],
        "navne": ["amagerbro"],
    },
    "Valby": {
        "postnumre": [2500],
        "navne": ["valby"],
    },
}

# --- Notifikationer ---------------------------------------------------------

# Send "ledig igen"-besked hvis en bolig du har fået besked om bliver
# reserveret og derefter ledig igen.
NOTIFY_BACK_AVAILABLE = True

# Send også besked om helt nye boliger der matcher, men allerede er
# reserveret/udlejet, når botten ser dem første gang. Bliver boligen senere
# ledig, får du en almindelig "Ny bolig"-besked.
NOTIFY_NEW_RESERVED = True

# Antal fejlede kørsler i træk før der sendes fejlbesked (1 = med det samme).
# 2 betyder at et enkelt netværksblip ikke giver støj.
FAIL_THRESHOLD = 2

# Boliger der ikke er set i så mange dage fjernes fra seen.json.
FORGET_AFTER_DAYS = 365

# --- Hentning ---------------------------------------------------------------

USER_AGENT = "bolig-bot (privat brug; hentes højst hvert 15. minut)"
TIMEOUT = 30
NTFY_SERVER = "https://ntfy.sh"

# --- KANALER ----------------------------------------------------------------
# Hver kanal har sit eget ntfy-kanalnavn (GitHub Secret), sine egne kriterier
# og sin egen huskeliste i data/. Den første kanal får også fejlbeskeder.
# En kanal uden secret springes bare over (undtagen den første).
#
# "rent_per_person": max husleje pr. person, hvor personer = værelser - 1
# (én fælles stue). 4 vær. = 3 pers. = 21.000 kr., 5 vær. = 28.000 kr. osv.
# "highlight": mærkater der fremhæves i beskeden (kun Kereby har dem).

GROUP_AREAS = {
    **AREAS,
    "Sydhavn": {
        "postnumre": [2450],                                 # København SV
        "navne": ["sydhavn", "københavn sv", "kbh sv"],
    },
}

CHANNELS = [
    {
        "name": "dig",
        "topic_env": "NTFY_TOPIC",
        "seen_file": "seen.json",
        "min_rooms": MIN_ROOMS,
        "max_rent": MAX_RENT,
        "min_size": MIN_SIZE,
        "areas": AREAS,
        "notify_back": NOTIFY_BACK_AVAILABLE,
        "notify_new_reserved": NOTIFY_NEW_RESERVED,
    },
    {
        "name": "gruppe",
        "topic_env": "NTFY_TOPIC_GRUPPE",
        "seen_file": "seen_gruppe.json",
        "min_rooms": 4,
        "rent_per_person": 7_000,
        "min_size": None,
        "areas": GROUP_AREAS,
        "notify_back": True,
        "notify_new_reserved": True,
        "highlight": ["Delevenlig"],
    },
]
