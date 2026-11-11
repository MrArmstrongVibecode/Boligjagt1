"""Hukommelse mellem kørsler: data/seen.json (boliger) og data/health.json (fejlstatus).

Logikken her er ren (ingen netværk), så den kan testes direkte.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from . import config
from .filters import is_available, matches
from .models import AVAILABLE, Listing

NEW = "new"      # ny bolig der matcher
BACK = "back"    # bolig du har fået besked om, som er ledig igen
NEW_RESERVED = "new_reserved"  # helt ny bolig der matcher, men allerede er reserveret/udlejet


@dataclass
class Event:
    kind: str
    listing: Listing
    prev_status: str | None = None


def load(path: Path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def save(path: Path, data) -> bool:
    """Skriver kun hvis indholdet er ændret. Returnerer True hvis filen blev skrevet."""
    path = Path(path)
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def source_has_history(seen: dict, source: str) -> bool:
    return any(k.startswith(source + ":") for k in seen)


def process(listings: list[Listing], seen: dict, today: date, seed: bool = False,
            notify_back: bool = None, notify_reserved: bool = None, channel=None) -> list[Event]:
    """Sammenligner hentede boliger med seen, opdaterer seen og returnerer events.

    seen[id]["notified"] sættes IKKE her for nye events - det gør mark_sent()
    først når beskeden faktisk er sendt, så en fejlet ntfy-besked prøves igen.
    """
    if notify_back is None:
        notify_back = config.NOTIFY_BACK_AVAILABLE
    if notify_reserved is None:
        notify_reserved = config.NOTIFY_NEW_RESERVED
    events = []
    iso = today.isoformat()
    for lst in listings:
        entry = seen.get(lst.id)
        ok = matches(lst, channel)
        good = ok and is_available(lst)
        if entry is None:
            entry = seen[lst.id] = {"first_seen": iso, "notified": False}
            if not seed:
                # Kun helt nye boliger kan give "allerede reserveret"-besked.
                entry["reserved_notified"] = False
            prev_status = None
        else:
            prev_status = entry.get("status")

        if seed:
            # Første kørsel: husk alt, send intet.
            if good:
                entry["notified"] = True
        elif good and not entry.get("notified"):
            events.append(Event(NEW, lst, prev_status))
        elif (good and notify_back and entry.get("notified")
              and prev_status is not None and prev_status != AVAILABLE):
            events.append(Event(BACK, lst, prev_status))
        elif (notify_reserved and not is_available(lst) and ok
              and entry.get("reserved_notified") is False and not entry.get("notified")):
            events.append(Event(NEW_RESERVED, lst, prev_status))

        entry.update(title=lst.title, url=lst.url, status=lst.status, rent=lst.rent, last_seen=iso)
    return events


def mark_sent(seen: dict, event: Event) -> None:
    if event.kind == NEW_RESERVED:
        # "notified" forbliver False, så du stadig får besked hvis den bliver ledig.
        seen[event.listing.id]["reserved_notified"] = True
    else:
        seen[event.listing.id]["notified"] = True


def revert(seen: dict, event: Event) -> None:
    """Beskeden kunne ikke sendes: sørg for at samme event opstår næste gang."""
    entry = seen[event.listing.id]
    if event.kind == BACK:
        entry["status"] = event.prev_status
    elif event.kind == NEW_RESERVED:
        entry["reserved_notified"] = False
    else:
        entry["notified"] = False


def prune(seen: dict, today: date, days: int = None) -> int:
    days = days or config.FORGET_AFTER_DAYS
    cutoff = (today - timedelta(days=days)).isoformat()
    old = [k for k, v in seen.items() if v.get("last_seen", "9999") < cutoff]
    for k in old:
        del seen[k]
    return len(old)


# --- Fejlstatus -------------------------------------------------------------

ALERT = "alert"
RECOVERED = "recovered"


def update_health(health: dict, source: str, error: str | None, now: str,
                  threshold: int = None) -> str | None:
    """Returnerer ALERT første gang en fejltilstand skal meldes, RECOVERED når
    den er løst (og der var meldt fejl), ellers None."""
    threshold = threshold or config.FAIL_THRESHOLD
    h = health.setdefault(source, {"failures": 0, "alerted": False})
    if error:
        if h.get("failures", 0) == 0:
            h["since"] = now
        h["failures"] = h.get("failures", 0) + 1
        h["error"] = error
        if h["failures"] >= threshold and not h.get("alerted"):
            h["alerted"] = True
            return ALERT
        return None
    was_alerted = h.get("alerted")
    health[source] = {"failures": 0, "alerted": False}
    return RECOVERED if was_alerted else None
