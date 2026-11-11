"""En kanal = ét ntfy-kanalnavn + ét sæt kriterier + én huskeliste."""
from __future__ import annotations

from dataclasses import dataclass, field

from . import config


@dataclass
class Channel:
    name: str
    topic_env: str
    seen_file: str
    min_rooms: int = 1
    max_rent: int | None = None
    rent_per_person: int | None = None
    min_size: int | None = None
    areas: dict = field(default_factory=dict)
    notify_back: bool = True
    notify_new_reserved: bool = True
    highlight: list[str] = field(default_factory=list)

    def persons(self, rooms: int | None) -> int | None:
        return max(rooms - 1, 1) if rooms else None

    def rent_limit(self, rooms: int | None) -> int | None:
        """Max husleje for en bolig med så mange værelser (None = ingen grænse)."""
        limits = []
        if self.max_rent is not None:
            limits.append(self.max_rent)
        if self.rent_per_person is not None and rooms:
            limits.append(self.rent_per_person * self.persons(rooms))
        return min(limits) if limits else None


def all_channels() -> list[Channel]:
    return [Channel(**c) for c in config.CHANNELS]


def personal() -> Channel:
    """Kanalen med dine egne kriterier (den første)."""
    return all_channels()[0]
