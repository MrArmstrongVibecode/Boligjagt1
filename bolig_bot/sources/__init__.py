from . import cityapartment, kereby

# Hver henter: navn -> funktion der returnerer list[Listing] eller kaster en fejl.
SOURCES = {
    "kereby": kereby.fetch,
    "cityapartment": cityapartment.fetch,
}
