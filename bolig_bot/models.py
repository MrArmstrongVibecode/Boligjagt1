from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

# Fælles statusværdier
AVAILABLE = "ledig"
RESERVED = "reserveret"
RENTED = "udlejet"

# Fælles typer
HOME = "bolig"
COMMERCIAL = "erhverv"
PARKING = "parkering"


@dataclass
class Listing:
    id: str                 # unik på tværs af udlejere, fx "kereby:28453"
    landlord: str           # "Kereby" / "City Apartment"
    title: str              # adresse/overskrift
    url: str
    postcode: int | None = None
    district: str | None = None   # bydel som udlejeren selv skriver den
    rooms: int | None = None
    size: int | None = None       # m²
    rent: int | None = None       # kr./md.
    status: str = AVAILABLE
    kind: str = HOME
    available_from: str | None = None
    labels: list[str] = field(default_factory=list)   # fx ["Delevenlig", "Altan"]

    def to_dict(self) -> dict:
        return asdict(self)


class SourceError(Exception):
    """En henter kunne ikke levere et troværdigt resultat."""


def to_int(value) -> int | None:
    """'16.350 kr./md.' -> 16350, '135' -> 135, None/'' -> None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = re.sub(r"[^\d]", "", str(value).split(",")[0])
    return int(digits) if digits else None


POSTCODE_RE = re.compile(r"\b([1-9]\d{3})\s+[A-ZÆØÅa-zæøå]")


def postcode_from_text(text: str | None) -> int | None:
    """Finder '2100' i 'Jagtvej 183, 1. tv, 2100 København Ø'."""
    if not text:
        return None
    m = POSTCODE_RE.search(text)
    return int(m.group(1)) if m else None
