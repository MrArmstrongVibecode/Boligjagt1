"""City Apartment: https://cityapartment.dk/all-properties/

WordPress-sitet har et åbent REST-endpoint (/wp-json/wp/v2/cityapartments)
som returnerer alle opslag som JSON inkl. ACF-felter (pris, post_nr, by,
ikon_m2, reserveret ...). Det bruges som primær kilde. Hvis det fejler,
falder vi tilbage til at læse listesidens HTML.

Siden blander boliger, erhverv og parkering. Typen aflæses af WordPress-
kategorien: category-private-leases = bolig.
"""
from __future__ import annotations

import html as htmllib
import re

from bs4 import BeautifulSoup

from .. import http
from ..models import (AVAILABLE, COMMERCIAL, HOME, PARKING, RESERVED, Listing,
                      SourceError, to_int)

API_URL = ("https://cityapartment.dk/wp-json/wp/v2/cityapartments"
           "?per_page=100&_fields=id,link,title,class_list,acf")
HTML_URL = "https://cityapartment.dk/all-properties/"
LANDLORD = "City Apartment"

ROOMS_RE = re.compile(r"(\d+)\s*[- ]?\s*(?:room|værelse|vær\b)", re.I)


def _kind(classes) -> str:
    classes = set(classes or [])
    if "category-private-leases" in classes:
        return HOME
    if "category-parking" in classes:
        return PARKING
    if "category-commercial-leases" in classes:
        return COMMERCIAL
    return "ukendt"


def _rooms_from_text(*texts) -> int | None:
    for t in texts:
        if t:
            m = ROOMS_RE.search(str(t))
            if m:
                return int(m.group(1))
    return None


# --- JSON (primær) ----------------------------------------------------------

def parse_api(items: list[dict]) -> list[Listing]:
    if not isinstance(items, list):
        raise SourceError("City Apartment API: uventet svarformat")
    listings = []
    for it in items:
        acf = it.get("acf") or {}
        if not isinstance(acf, dict):
            acf = {}
        rooms = _rooms_from_text(acf.get("intro_tekst"), acf.get("oversigt_beskrivelse_tekst"),
                                 acf.get("beskrivelse"))
        if rooms is None:
            stuer, sov = to_int(acf.get("ikon_antal_stuer")), to_int(acf.get("ikon_antal_sovevaerelser"))
            if stuer is not None or sov is not None:
                rooms = (stuer or 0) + (sov or 0)
        reserved = bool(acf.get("reserveret-yes-no")) or bool(str(acf.get("reserveret") or "").strip())
        title = (acf.get("overskrift") or htmllib.unescape((it.get("title") or {}).get("rendered", ""))).strip()
        listings.append(Listing(
            id=f"cityapartment:{it.get('id')}",
            landlord=LANDLORD,
            title=title,
            url=it.get("link") or "",
            postcode=to_int(acf.get("post_nr")),
            district=(acf.get("by") or None),
            rooms=rooms,
            size=to_int(acf.get("ikon_m2")),
            rent=to_int(acf.get("pris")),
            status=RESERVED if reserved else AVAILABLE,
            kind=_kind(it.get("class_list")),
            available_from=acf.get("ledig_fra") or None,
        ))
    return listings


# --- HTML (reserve) ---------------------------------------------------------

def parse_html(page: str) -> list[Listing]:
    soup = BeautifulSoup(page, "lxml")
    listings = []
    for art in soup.select("article.ecs-post-loop"):
        classes = art.get("class", [])
        post_id = next((c[5:] for c in classes if re.fullmatch(r"post-\d+", c)), None)
        link = art.find("a", href=re.compile(r"/cityapartments/"))
        if not post_id or not link:
            continue
        parts = list(art.stripped_strings)
        text = " | ".join(parts)
        zip_m = re.search(r"Zip code\s*\|?\s*(\d{4})", text)
        rent_m = re.search(r"([\d.]+)\s*DKK", text)
        size_m = re.search(r"(\d+)\s*m²", text)
        from_m = re.search(r"Available from\s*\|?\s*([^|]+)", text)
        # Titlen er første tekst der ikke er en "123 m²"-badge
        title = next((p for p in parts if not re.fullmatch(r"\d+\s*m²", p)), "")
        district = next((c[9:].replace("-", " ") for c in classes
                         if c.startswith("category-") and c not in
                         ("category-private-leases", "category-commercial-leases", "category-parking")), None)
        listings.append(Listing(
            id=f"cityapartment:{post_id}",
            landlord=LANDLORD,
            title=title,
            url=link["href"],
            postcode=int(zip_m.group(1)) if zip_m else None,
            district=district,
            rooms=_rooms_from_text(text),
            size=int(size_m.group(1)) if size_m else None,
            rent=to_int(rent_m.group(1)) if rent_m else None,
            status=RESERVED if re.search(r"reserveret|reserved", text, re.I) else AVAILABLE,
            kind=_kind(classes),
            available_from=from_m.group(1).strip() if from_m else None,
        ))
    return listings


def fetch() -> list[Listing]:
    api_error = None
    try:
        listings = parse_api(http.get(API_URL).json())
        if listings:
            return listings
        api_error = "0 opslag i API"
    except (SourceError, ValueError) as e:
        api_error = str(e)
    print(f"  City Apartment API fejlede ({api_error}) - prøver HTML-siden")
    listings = parse_html(http.get(HTML_URL).text)
    if not listings:
        raise SourceError(f"City Apartment: 0 opslag i både API ({api_error}) og HTML (ændret opbygning?)")
    return listings
