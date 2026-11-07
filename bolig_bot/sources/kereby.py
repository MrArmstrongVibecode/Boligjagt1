"""Kereby: https://kereby.dk/bolig/

Listesiden er server-renderet (24 kort, ingen JS-paginering). Hvert kort er et <article data-jorato-card> med
data-attributter (data-card-id, data-state, data-zip, data-rooms, data-rent,
data-size, data-subclass). Kereby har også /wp-json/wp/v2/jorato-cases, men
den mangler husleje, værelser og status, så den kan ikke bruges.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .. import http
from ..models import (AVAILABLE, COMMERCIAL, HOME, PARKING, RENTED, RESERVED,
                      Listing, SourceError, postcode_from_text, to_int)

URL = "https://kereby.dk/bolig/"
LANDLORD = "Kereby"

STATE_MAP = {"available": AVAILABLE, "reserved": RESERVED, "completed": RENTED}


def _kind(subclass: str, headline: str) -> str:
    text = f"{subclass} {headline}".lower()
    if any(w in text for w in ("parking", "parkering", "garage")):
        return PARKING
    if any(w in text for w in ("commercial", "erhverv", "kontor", "butik")):
        return COMMERCIAL
    return HOME


def _text(card, cls: str) -> str:
    el = card.select_one(f".jorato-case-card__{cls}")
    return " ".join(el.get_text(" ").split()) if el else ""


def parse(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("article[data-jorato-card]")
    listings = []
    for card in cards:
        card_id = card.get("data-card-id")
        # Reserverede/udlejede kort har intet link (kun <div class="..__link">).
        # Der sendes aldrig besked om dem, så listesiden bruges som link.
        link = card.select_one("a.jorato-case-card__link[href]") or card.find("a", href=True)
        if not card_id:
            continue
        headline = _text(card, "headline")          # "4-værelses lejlighed på Nørrebro"
        address = _text(card, "location-text")      # "Nørrebrogade 41, 3. th, 2200 København N"
        m = re.search(r"\bpå\s+(.+)$", headline)
        state = (card.get("data-state") or "").strip().lower()
        if not state:  # reserve: den synlige mærkat, fx "Reserveret"
            state = {"reserveret": "reserved", "udlejet": "completed"}.get(
                _text(card, "inactive").lower(), "available" if link else "")
        listings.append(Listing(
            id=f"kereby:{card_id}",
            landlord=LANDLORD,
            title=address or headline,
            url=link["href"] if link else URL,
            postcode=to_int(card.get("data-zip")) or postcode_from_text(address),
            district=m.group(1).strip() if m else None,
            rooms=to_int(card.get("data-rooms")),
            size=to_int(card.get("data-size")),
            rent=to_int(card.get("data-rent")) or to_int(_text(card, "rent")),
            status=STATE_MAP.get(state, state or "ukendt"),
            kind=_kind(card.get("data-subclass") or "", headline),
        ))
    return listings


def fetch() -> list[Listing]:
    listings = parse(http.get(URL).text)
    if not listings:
        raise SourceError("Kereby: 0 boliger fundet på listesiden (ændret opbygning?)")
    return listings
