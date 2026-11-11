"""Gruppekanalens kriterier: 4+ værelser, 7.000 kr. pr. person (værelser - 1), dine områder + Sydhavn."""
from pathlib import Path

import pytest

from bolig_bot import notify, state
from bolig_bot.channels import all_channels
from bolig_bot.filters import matches, reject_reason
from bolig_bot.models import Listing
from bolig_bot.sources import kereby

FIX = Path(__file__).parent / "fixtures"
YOU, GROUP = all_channels()


def L(**kw):
    base = dict(id="t:1", landlord="Kereby", title="Testvej 1", url="https://x/",
                postcode=2200, rooms=4, size=110, rent=20000)
    base.update(kw)
    return Listing(**base)


@pytest.mark.parametrize("rooms,rent,ok", [
    (3, 10000, False),            # for få værelser til gruppen
    (4, 21000, True), (4, 21001, False),
    (5, 28000, True), (5, 28001, False),
    (6, 35000, True),
])
def test_group_rent_per_person(rooms, rent, ok):
    assert matches(L(rooms=rooms, rent=rent), GROUP) is ok


def test_sydhavn_only_for_group():
    assert matches(L(postcode=2450), GROUP)
    assert not matches(L(postcode=2450, rooms=3, rent=12000), YOU)


def test_your_channel_unchanged():
    assert YOU.name == "dig" and YOU.topic_env == "NTFY_TOPIC" and YOU.seen_file == "seen.json"
    assert matches(L(rooms=2, rent=16000), YOU)
    assert not matches(L(rooms=4, rent=16001), YOU)
    assert reject_reason(L(rooms=2, rent=16000)) is None      # standard = dig


def test_group_reject_reason_explains_limit():
    assert reject_reason(L(rooms=4, rent=22000), GROUP) == "husleje: 22000 > 21000"


def test_kereby_labels_parsed():
    ls = {l.id: l for l in kereby.parse((FIX / "kereby_bolig.html").read_text(encoding="utf-8"))}
    assert "Delevenlig" in ls["kereby:28262"].labels
    assert "Delevenlig" not in ls["kereby:28453"].labels


def test_group_message_has_per_person_and_delevenlig():
    msg = notify.listing_message(L(rooms=4, rent=21000, labels=["Delevenlig", "Altan"]), state.NEW, GROUP)
    assert "≈ 7.000 kr./person ved 3 personer" in msg["message"]
    assert "✅ Delevenlig" in msg["message"]
    assert "Altan" not in msg["message"]


def test_your_message_unchanged():
    msg = notify.listing_message(L(rooms=3, rent=14500, labels=["Delevenlig"]), state.NEW, YOU)
    assert "/person" not in msg["message"] and "✅" not in msg["message"]
