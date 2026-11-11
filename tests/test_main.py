"""Hele kørslen med falske hentere og en falsk ntfy."""
import json

import pytest

from bolig_bot import main, notify
from bolig_bot.models import Listing, SourceError


def L(id, **kw):
    base = dict(id=id, landlord="X", title="Testvej 1, 2200 København N", url=f"https://x/{id}/",
                postcode=2200, rooms=3, size=70, rent=12000)
    base.update(kw)
    return Listing(**base)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("NTFY_TOPIC", "test")
    monkeypatch.setattr(main, "SEEN_FILE", tmp_path / "seen.json")
    monkeypatch.setattr(main, "HEALTH_FILE", tmp_path / "health.json")
    sent = []
    monkeypatch.setattr(notify.Notifier, "send", lambda self, msg: sent.append(msg["title"]) or True)
    data = {"a": [L("a:1")], "b": [L("b:1")]}

    def make(name):
        def fetch():
            v = data[name]
            if isinstance(v, Exception):
                raise v
            return v
        return fetch
    monkeypatch.setattr(main, "SOURCES", {"a": make("a"), "b": make("b")})
    return data, sent, tmp_path


def test_full_flow(env, monkeypatch):
    data, sent, tmp = env
    monkeypatch.setattr("bolig_bot.config.FAIL_THRESHOLD", 2)

    main.run()                                   # første kørsel = seed
    assert sent == []
    assert set(json.loads((tmp / "seen.json").read_text())) == {"a:1", "b:1"}

    data["a"] = [L("a:1"), L("a:2")]             # ny bolig hos a
    main.run()
    assert sent == ["Ny bolig: Nørrebro · 12.000 kr."]

    sent.clear()
    data["b"] = SourceError("HTTP 500")          # b går i stykker
    data["a"] = [L("a:1"), L("a:2"), L("a:3")]
    main.run()                                   # 1. fejl: ingen fejlbesked endnu, a virker stadig
    assert sent == ["Ny bolig: Nørrebro · 12.000 kr."]
    sent.clear()
    main.run(); main.run(); main.run()           # fejlbesked præcis én gang
    assert sent == ["Bolig-bot: b virker ikke"]
    assert "b:1" in json.loads((tmp / "seen.json").read_text())   # b's boliger er ikke glemt

    sent.clear()
    data["b"] = [L("b:1")]                       # b virker igen
    main.run()
    assert sent == ["Bolig-bot: b virker igen"]


def test_dry_run_writes_nothing(env):
    _, sent, tmp = env
    main.run(dry_run=True)
    assert not (tmp / "seen.json").exists()


def test_unexpected_exception_is_isolated(env):
    data, sent, tmp = env
    main.run()
    data["a"] = ValueError("parser eksploderede")
    data["b"] = [L("b:1"), L("b:2")]
    main.run()
    assert sent == ["Ny bolig: Nørrebro · 12.000 kr."]


def test_test_notify_sends_one_message_and_touches_no_state(env):
    _, sent, tmp = env
    assert main.main(["--test-notify"]) == 0
    assert len(sent) == 1 and sent[0].startswith("TEST (dig) - Ny bolig: Nørrebro")
    assert not (tmp / "seen.json").exists()


# --- gruppekanal ---

@pytest.fixture
def env2(env, monkeypatch):
    """Som env, men med gruppekanalen slået til og afsender pr. kanal."""
    data, _, tmp = env
    monkeypatch.setenv("NTFY_TOPIC_GRUPPE", "test-gruppe")
    sent = []
    monkeypatch.setattr(notify.Notifier, "send", lambda self, msg: sent.append((self.label, msg["title"])) or True)
    return data, sent, tmp


def big(id, **kw):
    return L(id, rooms=4, size=110, rent=20000, **kw)


def test_group_gets_big_homes_and_you_get_small(env2):
    data, sent, tmp = env2
    main.run()                                        # seed for begge kanaler
    assert sent == []
    assert (tmp / "seen.json").exists() and (tmp / "seen_gruppe.json").exists()
    data["a"] = [L("a:1"), L("a:2"), big("a:3")]      # a:2 lille (3 vær, 12.000), a:3 stor (4 vær, 20.000)
    main.run()
    assert sorted(sent) == [("dig", "Ny bolig: Nørrebro · 12.000 kr."),
                            ("gruppe", "Ny bolig: Nørrebro · 20.000 kr.")]


def test_group_added_later_seeds_without_messages(env, monkeypatch):
    data, sent, tmp = env
    main.run()                                        # kun "dig"
    data["a"] = [L("a:1"), big("a:2")]
    main.run()
    sent.clear()
    monkeypatch.setenv("NTFY_TOPIC_GRUPPE", "test-gruppe")
    main.run()                                        # gruppen tilføjes: seed, ingen besked
    assert sent == []
    data["a"] = [L("a:1"), big("a:2"), big("a:3")]
    main.run()
    assert len(sent) == 1                             # kun gruppen (4 vær, 20.000 > 16.000 for dig)


def test_group_send_failure_does_not_affect_you(env2, monkeypatch):
    data, _, tmp = env2
    main.run()
    sent = []

    def send(self, msg):
        if self.label == "gruppe":
            return False
        sent.append(msg["title"])
        return True
    monkeypatch.setattr(notify.Notifier, "send", send)
    data["a"] = [L("a:1"), L("a:2"), big("a:3")]
    main.run()
    assert sent == ["Ny bolig: Nørrebro · 12.000 kr."]
    seen_g = json.loads((tmp / "seen_gruppe.json").read_text())
    assert seen_g["a:3"]["notified"] is False         # prøves igen næste gang


def test_error_alerts_only_go_to_you(env2, monkeypatch):
    data, sent, _ = env2
    monkeypatch.setattr("bolig_bot.config.FAIL_THRESHOLD", 1)
    main.run()
    data["b"] = SourceError("HTTP 500")
    main.run()
    assert sent == [("dig", "Bolig-bot: b virker ikke")]


def test_test_notify_goes_to_both_channels(env2):
    _, sent, _ = env2
    assert main.main(["--test-notify"]) == 0
    assert [s[0] for s in sent] == ["dig", "gruppe"]
    assert sent[1][1].startswith("TEST (gruppe) - Ny bolig: Sydhavn")
