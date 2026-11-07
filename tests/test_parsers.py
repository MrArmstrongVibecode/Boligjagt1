import json
from pathlib import Path

import pytest

from bolig_bot.models import AVAILABLE, COMMERCIAL, HOME, PARKING, RENTED, RESERVED, SourceError
from bolig_bot.sources import cityapartment, kereby

FIX = Path(__file__).parent / "fixtures"


# --- Kereby -----------------------------------------------------------------

@pytest.fixture(scope="module")
def kereby_listings():
    return kereby.parse((FIX / "kereby_bolig.html").read_text(encoding="utf-8"))


def test_kereby_count_and_ids(kereby_listings):
    assert len(kereby_listings) == 24
    assert len({l.id for l in kereby_listings}) == 24
    assert all(l.id.startswith("kereby:") for l in kereby_listings)


def test_kereby_fields(kereby_listings):
    jagtvej = next(l for l in kereby_listings if l.id == "kereby:28453")
    assert jagtvej.title == "Jagtvej 183, 1. tv, 2100 København Ø"
    assert jagtvej.url == "https://kereby.dk/bolig/jagtvej-183-1-tv-2100-kobenhavn/"
    assert (jagtvej.postcode, jagtvej.rooms, jagtvej.size, jagtvej.rent) == (2100, 5, 160, 26227)
    assert jagtvej.status == AVAILABLE
    assert jagtvej.district == "Østerbro"
    assert jagtvej.kind == HOME
    assert jagtvej.landlord == "Kereby"


def test_kereby_statuses(kereby_listings):
    statuses = {l.status for l in kereby_listings}
    assert statuses == {AVAILABLE, RESERVED, RENTED}
    assert sum(l.status == AVAILABLE for l in kereby_listings) == 4


def test_kereby_empty_page_is_error(monkeypatch):
    class R:
        text = "<html><body>Vi er ved at opdatere siden</body></html>"
    monkeypatch.setattr(kereby.http, "get", lambda url: R())
    with pytest.raises(SourceError):
        kereby.fetch()


# --- City Apartment: JSON ---------------------------------------------------

@pytest.fixture(scope="module")
def city_api():
    return cityapartment.parse_api(json.loads((FIX / "cityapartment_rest.json").read_text(encoding="utf-8")))


def test_city_api_count_and_kinds(city_api):
    assert len(city_api) == 25
    kinds = [l.kind for l in city_api]
    assert kinds.count(HOME) == 5
    assert kinds.count(COMMERCIAL) == 12
    assert kinds.count(PARKING) == 8


def test_city_api_fields(city_api):
    w = next(l for l in city_api if "willemoesgade" in l.url)
    assert w.id == "cityapartment:38924"
    assert w.url == "https://cityapartment.dk/cityapartments/willemoesgade-14-4-th/"
    assert (w.postcode, w.rooms, w.size, w.rent) == (2100, 4, 135, 21950)
    assert w.district == "Østerbro"
    assert w.status == AVAILABLE
    assert w.available_from == "15/01/2027"


def test_city_api_reserved_flag():
    items = [{"id": 1, "link": "https://x/1/", "title": {"rendered": "A"},
              "class_list": ["category-private-leases"],
              "acf": {"post_nr": 2200, "pris": 9000, "intro_tekst": "2-room apartment",
                      "reserveret-yes-no": True}}]
    (l,) = cityapartment.parse_api(items)
    assert l.status == RESERVED and l.rooms == 2


def test_city_api_rooms_fallback_to_counts():
    items = [{"id": 2, "link": "https://x/2/", "title": {"rendered": "B &amp; C"},
              "class_list": ["category-private-leases"],
              "acf": {"post_nr": 2200, "pris": 9000, "intro_tekst": "Nice flat",
                      "ikon_antal_stuer": "1", "ikon_antal_sovevaerelser": "2"}}]
    (l,) = cityapartment.parse_api(items)
    assert l.rooms == 3 and l.title == "B & C"


# --- City Apartment: HTML (reserve) -----------------------------------------

@pytest.fixture(scope="module")
def city_html():
    return cityapartment.parse_html((FIX / "cityapartment_all_properties.html").read_text(encoding="utf-8"))


def test_city_html_matches_api(city_html, city_api):
    assert len(city_html) == 25
    by_id = {l.id: l for l in city_api}
    for h in city_html:
        a = by_id[h.id]
        assert (h.kind, h.postcode, h.rent, h.url) == (a.kind, a.postcode, a.rent, a.url), h.id
        if h.kind == HOME:
            assert h.rooms == a.rooms and h.size == a.size, h.id


def test_city_falls_back_to_html(monkeypatch):
    html = (FIX / "cityapartment_all_properties.html").read_text(encoding="utf-8")

    def fake_get(url):
        if "wp-json" in url:
            raise SourceError("HTTP 500")
        class R: text = html
        return R()
    monkeypatch.setattr(cityapartment.http, "get", fake_get)
    assert len(cityapartment.fetch()) == 25


def test_city_both_broken_is_error(monkeypatch):
    def fake_get(url):
        class R:
            text = "<html></html>"
            def json(self): return []
        return R()
    monkeypatch.setattr(cityapartment.http, "get", fake_get)
    with pytest.raises(SourceError):
        cityapartment.fetch()


def test_kereby_reserved_card_without_link(kereby_listings):
    r = next(l for l in kereby_listings if l.id == "kereby:28441")
    assert r.status == RESERVED
    assert r.url == kereby.URL
    assert (r.postcode, r.rooms, r.rent) == (2200, 4, 20447)
