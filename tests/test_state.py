from datetime import date

from bolig_bot import state
from bolig_bot.models import AVAILABLE, RENTED, RESERVED, Listing

D1, D2, D3 = date(2026, 11, 1), date(2026, 11, 2), date(2026, 11, 3)


def L(id="k:1", **kw):
    base = dict(id=id, landlord="Kereby", title="Testvej 1, 2200 København N", url=f"https://x/{id}/",
                postcode=2200, rooms=3, size=70, rent=12000, status=AVAILABLE)
    base.update(kw)
    return Listing(**base)


def run(listings, seen, day, seed=False, notify_back=True):
    events = state.process(listings, seen, day, seed=seed, notify_back=notify_back)
    for e in events:
        state.mark_sent(seen, e)
    return events


def test_seed_sends_nothing():
    seen = {}
    assert run([L("k:1"), L("k:2")], seen, D1, seed=True) == []
    assert set(seen) == {"k:1", "k:2"}
    assert run([L("k:1"), L("k:2")], seen, D2) == []


def test_new_listing_after_seed():
    seen = {}
    run([L("k:1")], seen, D1, seed=True)
    ev = run([L("k:1"), L("k:2")], seen, D2)
    assert [(e.kind, e.listing.id) for e in ev] == [(state.NEW, "k:2")]
    assert run([L("k:1"), L("k:2")], seen, D3) == []


def test_non_matching_new_listing_is_silent_but_remembered():
    seen = {}
    run([L("k:1")], seen, D1, seed=True)
    assert run([L("k:1"), L("k:2", rent=30000)], seen, D2) == []
    assert "k:2" in seen


def test_reserved_new_listing_is_silent_until_available():
    seen = {}
    run([L("k:1")], seen, D1, seed=True)
    assert run([L("k:2", status=RESERVED)], seen, D2) == []
    ev = run([L("k:2", status=AVAILABLE)], seen, D3)
    assert [e.kind for e in ev] == [state.NEW]


def test_reserved_at_seed_then_available_notifies():
    seen = {}
    run([L("k:1", status=RESERVED)], seen, D1, seed=True)
    assert [e.kind for e in run([L("k:1")], seen, D2)] == [state.NEW]


def test_disappear_and_return_no_duplicate():
    seen = {}
    run([L("k:1")], seen, D1, seed=True)
    run([L("k:1"), L("k:2")], seen, D1)          # besked om k:2
    assert run([L("k:1")], seen, D2) == []        # k:2 forsvinder
    assert run([L("k:1"), L("k:2")], seen, D3) == []   # kommer tilbage: ingen dublet


def test_back_available_after_reserved():
    seen = {}
    run([L("k:0")], seen, D1, seed=True)
    run([L("k:1")], seen, D1)                         # besked
    assert run([L("k:1", status=RESERVED)], seen, D2) == []
    ev = run([L("k:1")], seen, D3)
    assert [e.kind for e in ev] == [state.BACK]
    assert run([L("k:1")], seen, D3) == []            # kun én gang


def test_back_available_can_be_disabled():
    seen = {}
    run([L("k:0")], seen, D1, seed=True)
    run([L("k:1")], seen, D1)
    run([L("k:1", status=RENTED)], seen, D2)
    assert run([L("k:1")], seen, D3, notify_back=False) == []


def test_failed_send_is_retried():
    seen = {}
    run([L("k:0")], seen, D1, seed=True)
    ev = state.process([L("k:1")], seen, D2, notify_back=True)
    state.revert(seen, ev[0])                       # ntfy fejlede
    ev2 = state.process([L("k:1")], seen, D3, notify_back=True)
    assert [e.kind for e in ev2] == [state.NEW]


def test_rent_drop_into_range_notifies_once():
    seen = {}
    run([L("k:1", rent=17000)], seen, D1, seed=True)
    assert [e.kind for e in run([L("k:1", rent=15500)], seen, D2)] == [state.NEW]
    assert run([L("k:1", rent=15500)], seen, D3) == []


def test_source_history_and_prune():
    seen = {}
    run([L("kereby:1")], seen, D1, seed=True)
    assert state.source_has_history(seen, "kereby")
    assert not state.source_has_history(seen, "cityapartment")
    assert state.prune(seen, date(2028, 1, 1), days=365) == 1 and seen == {}


# --- fejlstatus ---

def test_health_alert_once_and_recover():
    h = {}
    assert state.update_health(h, "kereby", "HTTP 500", "t1", threshold=2) is None
    assert state.update_health(h, "kereby", "HTTP 500", "t2", threshold=2) == state.ALERT
    assert state.update_health(h, "kereby", "parse", "t3", threshold=2) is None
    assert h["kereby"]["since"] == "t1"
    assert state.update_health(h, "kereby", None, "t4", threshold=2) == state.RECOVERED
    assert state.update_health(h, "kereby", None, "t5", threshold=2) is None


def test_single_blip_gives_no_messages():
    h = {}
    assert state.update_health(h, "c", "timeout", "t1", threshold=2) is None
    assert state.update_health(h, "c", None, "t2", threshold=2) is None


def test_health_sources_independent():
    h = {}
    state.update_health(h, "kereby", "x", "t1", threshold=1)
    assert state.update_health(h, "cityapartment", None, "t1", threshold=1) is None
    assert h["kereby"]["alerted"] and not h["cityapartment"]["alerted"]
