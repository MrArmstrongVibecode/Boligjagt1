"""Bolig-bot: henter lejeboliger, filtrerer og sender ntfy-besked om nye.

  python -m bolig_bot              # normal kørsel (bruges af GitHub Action)
  python -m bolig_bot --dry-run    # vis hvad der ville blive sendt; intet sendes eller gemmes
  python -m bolig_bot --seed       # gem alle nuværende boliger som "set" uden at sende
  python -m bolig_bot --dry-run --no-seed   # vis hvilke boliger der ville give besked i dag
"""
from __future__ import annotations

import argparse
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from . import notify, state
from .filters import area_for, is_available, reject_reason
from .models import SourceError
from .sources import SOURCES

DATA = Path(__file__).resolve().parent.parent / "data"
SEEN_FILE = DATA / "seen.json"
HEALTH_FILE = DATA / "health.json"


def _fmt(lst) -> str:
    rent = f"{lst.rent or 0:,}".replace(",", ".")
    return (f"{lst.title[:42]:42} {lst.postcode or '':>4} {str(lst.rooms or '?'):>2} vær "
            f"{str(lst.size or '?'):>4} m² {rent:>7} kr  {lst.status:10} {lst.kind}")


def run(dry_run: bool = False, seed: bool = False, no_seed: bool = False,
        only: list[str] | None = None) -> int:
    now = datetime.now(timezone.utc)
    today = now.date()
    seen = state.load(SEEN_FILE, {})
    health = state.load(HEALTH_FILE, {})
    notifier = notify.Notifier(dry_run)

    for name, fetch in SOURCES.items():
        if only and name not in only:
            continue
        print(f"\n=== {name}")
        try:
            listings = fetch()
            error = None
        except SourceError as e:
            listings, error = [], str(e)
        except Exception as e:  # parserfejl o.l. må ikke stoppe den anden udlejer
            traceback.print_exc()
            listings, error = [], f"Uventet fejl: {e.__class__.__name__}: {e}"

        # Fejlstatus (kun én besked pr. fejltilstand)
        transition = state.update_health(health, name, error, now.isoformat(timespec="minutes"))
        if error:
            print(f"  FEJL: {error} (fejl i træk: {health[name]['failures']})")
        if transition == state.ALERT:
            msg = notify.error_message(name, error, health[name]["since"])
            if not notifier.send(msg):
                health[name]["alerted"] = False   # prøv igen næste gang
        elif transition == state.RECOVERED:
            notifier.send(notify.recovered_message(name))
        if error:
            continue

        # Oversigt
        print(f"  {len(listings)} opslag hentet")
        for lst in listings:
            why = reject_reason(lst)
            if why is None and not is_available(lst):
                why = f"status: {lst.status}"
            mark = "MATCH" if why is None else f"nej ({why})"
            print(f"  {_fmt(lst)}  -> {mark}" + (f" [{area_for(lst)}]" if why is None else ""))

        # Ny-logik. Første gang en kilde ses, seedes den automatisk.
        source_seed = seed or (not no_seed and not state.source_has_history(seen, name))
        if source_seed:
            print("  SEED: gemmer nuværende boliger som 'set' - ingen boligbeskeder sendes.")
        events = state.process(listings, seen, today, seed=source_seed)
        if not events:
            print("  Ingen nye matchende boliger.")
        for ev in events:
            label = {state.NEW: "NY", state.BACK: "LEDIG IGEN", state.NEW_RESERVED: "NY (RESERVERET)"}[ev.kind]
            print(f"  {label}: {ev.listing.title}")
            if notifier.send(notify.listing_message(ev.listing, ev.kind)):
                state.mark_sent(seen, ev)
            else:
                state.revert(seen, ev)

    removed = state.prune(seen, today)
    if removed:
        print(f"\nGlemte {removed} gamle boliger.")

    if dry_run:
        print("\n[dry-run] Intet er sendt og state-filerne er ikke ændret.")
    else:
        changed = state.save(SEEN_FILE, seen) | state.save(HEALTH_FILE, health)
        print("\nState gemt." if changed else "\nIngen ændringer i state.")
    return 0


def send_test(dry_run: bool = False) -> int:
    """Sender én testbesked med en opdigtet bolig. Henter intet og ændrer ingen state."""
    from .models import Listing
    demo = Listing(id="test:0", landlord="Kereby (TEST)", title="Testgade 1, 2. th, 2200 København N",
                   url="https://kereby.dk/bolig/", postcode=2200, rooms=3, size=75, rent=14500)
    msg = notify.listing_message(demo, state.NEW)
    msg["title"] = "TEST - " + msg["title"]
    msg["message"] = "Dette er en test. Virker linket, er alt sat rigtigt op.\n\n" + msg["message"]
    ok = notify.Notifier(dry_run).send(msg)
    print("Testbesked sendt." if ok else "Testbesked kunne IKKE sendes - se fejlen ovenfor.")
    return 0 if ok else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="bolig_bot", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="send intet og gem intet")
    p.add_argument("--seed", action="store_true", help="markér alle nuværende boliger som set uden besked")
    p.add_argument("--no-seed", action="store_true",
                   help="slå automatisk seed fra (brug med --dry-run for at se hvad der ville blive sendt)")
    p.add_argument("--test-notify", action="store_true",
                   help="send én testbesked til ntfy og stop (henter intet, gemmer intet)")
    p.add_argument("--only", nargs="+", choices=list(SOURCES), help="kør kun bestemte udlejere")
    a = p.parse_args(argv)
    if a.test_notify:
        return send_test(dry_run=a.dry_run)
    return run(dry_run=a.dry_run, seed=a.seed, no_seed=a.no_seed, only=a.only)


if __name__ == "__main__":
    sys.exit(main())
