"""ntfy-beskeder. Bruger ntfy's JSON-API, så æøå virker i titlen (HTTP-headere
kan kun bære latin-1). Feltet "click" svarer til Click-headeren."""
from __future__ import annotations

import os

import requests

from . import config
from .filters import area_for
from .models import Listing
from .state import BACK, NEW_RESERVED


def _kr(n) -> str:
    return f"{n:,}".replace(",", ".") + " kr." if n is not None else "? kr."


def listing_message(listing: Listing, kind: str) -> dict:
    area = area_for(listing) or listing.district or ""
    head = {BACK: "Ledig igen", NEW_RESERVED: f"Ny, men {listing.status}"}.get(kind, "Ny bolig")
    lines = [
        f"{listing.title}" + (f" ({area})" if area else ""),
        f"{_kr(listing.rent)}/md · {listing.rooms or '?'} vær. · {listing.size or '?'} m²",
        f"Udlejer: {listing.landlord}",
    ]
    if kind == NEW_RESERVED:
        lines.append(f"Status: {listing.status} allerede. Du får besked, hvis den bliver ledig.")
    if listing.available_from:
        lines.append(f"Ledig fra: {listing.available_from}")
    lines.append(listing.url)
    return {
        "title": f"{head}: {area or listing.landlord} · {_kr(listing.rent)}",
        "message": "\n".join(lines),
        "click": listing.url,
        "tags": ["hourglass"] if kind == NEW_RESERVED else ["house"],
        "priority": 3 if kind == NEW_RESERVED else 4,
    }


def error_message(source: str, error: str, since: str) -> dict:
    return {
        "title": f"Bolig-bot: {source} virker ikke",
        "message": f"Hentning fejler siden {since}.\nFejl: {error}\n"
                   "Du får kun denne besked én gang. Den anden udlejer tjekkes stadig.",
        "tags": ["warning"],
        "priority": 3,
    }


def recovered_message(source: str) -> dict:
    return {
        "title": f"Bolig-bot: {source} virker igen",
        "message": f"Hentning fra {source} virker igen.",
        "tags": ["white_check_mark"],
        "priority": 2,
    }


class Notifier:
    def __init__(self, dry_run: bool):
        self.dry_run = dry_run
        self.topic = os.environ.get("NTFY_TOPIC", "").strip()
        if not dry_run and not self.topic:
            raise SystemExit("NTFY_TOPIC mangler (sæt den som GitHub Secret / miljøvariabel).")

    def send(self, msg: dict) -> bool:
        if self.dry_run:
            print("  [dry-run] ville sende:")
            print("    Titel: " + msg["title"])
            for line in msg["message"].splitlines():
                print("    " + line)
            if msg.get("click"):
                print("    Klik:  " + msg["click"])
            return True
        try:
            r = requests.post(config.NTFY_SERVER, json={"topic": self.topic, **msg}, timeout=config.TIMEOUT)
            r.raise_for_status()
            return True
        except requests.RequestException as e:
            print(f"  ntfy-fejl: {e.__class__.__name__}")
            return False
