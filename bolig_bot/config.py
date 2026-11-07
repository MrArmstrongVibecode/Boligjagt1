"""Dine kriterier. Ret her - resten af programmet læser kun fra denne fil."""

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

# Antal fejlede kørsler i træk før der sendes fejlbesked (1 = med det samme).
# 2 betyder at et enkelt netværksblip ikke giver støj.
FAIL_THRESHOLD = 2

# Boliger der ikke er set i så mange dage fjernes fra seen.json.
FORGET_AFTER_DAYS = 365

# --- Hentning ---------------------------------------------------------------

USER_AGENT = "bolig-bot (privat brug; hentes højst 1 gang i timen)"
TIMEOUT = 30
NTFY_SERVER = "https://ntfy.sh"
