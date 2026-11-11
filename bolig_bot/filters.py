from __future__ import annotations

from . import config
from .channels import Channel, personal
from .models import AVAILABLE, HOME, Listing, postcode_from_text


def _postcode_matches(pc: int, spec) -> bool:
    for entry in spec:
        if isinstance(entry, (tuple, list)):
            if entry[0] <= pc <= entry[1]:
                return True
        elif pc == entry:
            return True
    return False


def area_for(listing: Listing, areas: dict = None) -> str | None:
    """Returnerer områdenavnet fra AREAS, eller None hvis boligen ligger udenfor.

    1. Postnummer (fra feltet eller udledt af adressen) er afgørende hvis kendt.
    2. Ellers matches bydelsnavnet.
    3. Ellers søges der efter et områdenavn i titel/adresse.
    """
    areas = areas or config.AREAS
    pc = listing.postcode or postcode_from_text(listing.title)
    if pc:
        for name, spec in areas.items():
            if _postcode_matches(pc, spec.get("postnumre", [])):
                return name
        return None
    for text in (listing.district, listing.title):
        if not text:
            continue
        low = text.lower()
        for name, spec in areas.items():
            if any(alias in low for alias in [name.lower(), *spec.get("navne", [])]):
                return name
    return None


def reject_reason(listing: Listing, ch: Channel | None = None) -> str | None:
    """None = boligen matcher kanalens kriterier (standard: dine). Ellers en kort forklaring."""
    ch = ch or personal()
    if listing.kind != HOME:
        return f"type: {listing.kind}"
    if area_for(listing, ch.areas) is None:
        return f"område: {listing.postcode or listing.district or '?'}"
    if listing.rooms is None or listing.rooms < ch.min_rooms:
        return f"værelser: {listing.rooms}"
    limit = ch.rent_limit(listing.rooms)
    if listing.rent is None or (limit is not None and listing.rent > limit):
        return f"husleje: {listing.rent}" + (f" > {limit}" if limit and ch.rent_per_person else "")
    if ch.min_size and (listing.size or 0) < ch.min_size:
        return f"størrelse: {listing.size}"
    return None


def matches(listing: Listing, ch: Channel | None = None) -> bool:
    """Opfylder kriterierne (uanset status)."""
    return reject_reason(listing, ch) is None


def is_available(listing: Listing) -> bool:
    return listing.status == AVAILABLE
