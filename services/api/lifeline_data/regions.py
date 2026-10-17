"""Map native region names and codes to canonical region slugs (`lifeline_contracts.observation.REGIONS`).

`None` means the UK (or the widest area the source covers, for example England and Wales).
"""

from __future__ import annotations

import re

from lifeline_contracts.observation import REGIONS

# ONS GSS codes used by Nomis and others.
GSS_TO_REGION: dict[str, str | None] = {
    "E12000001": "north-east",
    "E12000002": "north-west",
    "E12000003": "yorkshire-and-the-humber",
    "E12000004": "east-midlands",
    "E12000005": "west-midlands",
    "E12000006": "east-of-england",
    "E12000007": "london",
    "E12000008": "south-east",
    "E12000009": "south-west",
    "W92000004": "wales",
    "S92000003": "scotland",
    "N92000002": "northern-ireland",
    "K02000001": None,  # United Kingdom
    "K03000001": None,  # Great Britain
    "K04000001": None,  # England and Wales
}

_NAME_ALIASES: dict[str, str | None] = {
    "east": "east-of-england",
    "eastern": "east-of-england",
    "yorkshire-and-humber": "yorkshire-and-the-humber",
    "yorkshire": "yorkshire-and-the-humber",
    "united-kingdom": None,
    "uk": None,
    "great-britain": None,
    "england-and-wales": None,
}


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def region_from_name(name: str | None) -> str | None:
    """Map a region or country name (any case) to a slug. Unknown names raise KeyError."""
    if name is None:
        return None
    slug = slugify(name)
    if slug in REGIONS:
        return slug
    if slug in _NAME_ALIASES:
        return _NAME_ALIASES[slug]
    raise KeyError(f"unknown region name: {name!r}")


def region_from_code(code: str) -> str | None:
    """Map a GSS code to a slug. Unknown codes raise KeyError."""
    return GSS_TO_REGION[code.strip().upper()]
