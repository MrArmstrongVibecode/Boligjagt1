import pytest

from bolig_bot.filters import area_for, matches, reject_reason
from bolig_bot.models import COMMERCIAL, PARKING, Listing


def L(**kw):
    base = dict(id="t:1", landlord="T", title="Testvej 1", url="https://x/",
                postcode=2200, rooms=2, size=60, rent=12000)
    base.update(kw)
    return Listing(**base)


@pytest.mark.parametrize("pc,area", [
    (1050, "Indre By"), (1454, "Indre By"), (1401, "Christianshavn"),
    (1620, "Vesterbro"), (1850, "Frederiksberg"), (2000, "Frederiksberg"),
    (2100, "Østerbro"), (2200, "Nørrebro"), (2300, "Amagerbro"), (2500, "Valby"),
])
def test_area_by_postcode(pc, area):
    assert area_for(L(postcode=pc)) == area


@pytest.mark.parametrize("pc", [2400, 2450, 2720, 2900, 5210, 2770])
def test_area_outside(pc):
    assert area_for(L(postcode=pc)) is None


def test_postcode_from_address_when_missing():
    assert area_for(L(postcode=None, title="Jagtvej 183, 1. tv, 2100 København Ø")) == "Østerbro"


def test_postcode_wins_over_name():
    # Gadenavnet indeholder "Valby", men postnummeret er Vanløse
    assert area_for(L(postcode=2720, title="Valbyvej 3", district=None)) is None


def test_area_by_district_name_when_no_postcode():
    assert area_for(L(postcode=None, title="Flot lejlighed", district="City Centre")) == "Indre By"
    assert area_for(L(postcode=None, title="Lejlighed på Nørrebro", district=None)) == "Nørrebro"
    assert area_for(L(postcode=None, title="Lejlighed i Hellerup", district="Hellerup")) is None


def test_rooms():
    assert reject_reason(L(rooms=1)) and not matches(L(rooms=1))
    assert matches(L(rooms=2))
    assert not matches(L(rooms=None))


def test_rent():
    assert matches(L(rent=16000))
    assert not matches(L(rent=16001))
    assert not matches(L(rent=None))


def test_no_size_limit():
    assert matches(L(size=None)) and matches(L(size=20))


def test_commercial_and_parking_rejected():
    assert reject_reason(L(kind=COMMERCIAL)) == "type: erhverv"
    assert not matches(L(kind=PARKING))
