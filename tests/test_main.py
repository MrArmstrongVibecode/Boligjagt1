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
