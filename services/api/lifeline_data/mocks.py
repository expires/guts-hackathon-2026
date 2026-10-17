# ruff: noqa: E501
"""Built-in mock data, used when live, Redis and Postgres all fail, and always in offline mode.

Mock values are labelled `status="mock"`.
"""

from __future__ import annotations

import re
from datetime import date

from lifeline_contracts.macro import MacroTable
from lifeline_contracts.observation import Observation
from lifeline_data.base import utcnow
from lifeline_data.macro import KEY_SPECS, mock_macro_table

# Postcode area (letters before the first digit) -> (main town, region slug).
POSTCODE_AREAS: dict[str, tuple[str, str]] = {
    "AB": ("Aberdeen", "scotland"), "AL": ("St Albans", "east-of-england"), "B": ("Birmingham", "west-midlands"),
    "BA": ("Bath", "south-west"), "BB": ("Blackburn", "north-west"), "BD": ("Bradford", "yorkshire-and-the-humber"),
    "BH": ("Bournemouth", "south-west"), "BL": ("Bolton", "north-west"), "BN": ("Brighton", "south-east"),
    "BR": ("Bromley", "london"), "BS": ("Bristol", "south-west"), "BT": ("Belfast", "northern-ireland"),
    "CA": ("Carlisle", "north-west"), "CB": ("Cambridge", "east-of-england"), "CF": ("Cardiff", "wales"),
    "CH": ("Chester", "north-west"), "CM": ("Chelmsford", "east-of-england"), "CO": ("Colchester", "east-of-england"),
    "CR": ("Croydon", "london"), "CT": ("Canterbury", "south-east"), "CV": ("Coventry", "west-midlands"),
    "CW": ("Crewe", "north-west"), "DA": ("Dartford", "south-east"), "DD": ("Dundee", "scotland"),
    "DE": ("Derby", "east-midlands"), "DG": ("Dumfries", "scotland"), "DH": ("Durham", "north-east"),
    "DL": ("Darlington", "north-east"), "DN": ("Doncaster", "yorkshire-and-the-humber"), "DT": ("Dorchester", "south-west"),
    "DY": ("Dudley", "west-midlands"), "E": ("London", "london"), "EC": ("London", "london"),
    "EH": ("Edinburgh", "scotland"), "EN": ("Enfield", "london"), "EX": ("Exeter", "south-west"),
    "FK": ("Falkirk", "scotland"), "FY": ("Blackpool", "north-west"), "G": ("Glasgow", "scotland"),
    "GL": ("Gloucester", "south-west"), "GU": ("Guildford", "south-east"), "HA": ("Harrow", "london"),
    "HD": ("Huddersfield", "yorkshire-and-the-humber"), "HG": ("Harrogate", "yorkshire-and-the-humber"),
    "HP": ("Hemel Hempstead", "east-of-england"), "HR": ("Hereford", "west-midlands"), "HS": ("Outer Hebrides", "scotland"),
    "HU": ("Hull", "yorkshire-and-the-humber"), "HX": ("Halifax", "yorkshire-and-the-humber"), "IG": ("Ilford", "london"),
    "IP": ("Ipswich", "east-of-england"), "IV": ("Inverness", "scotland"), "KA": ("Kilmarnock", "scotland"),
    "KT": ("Kingston upon Thames", "london"), "KW": ("Kirkwall", "scotland"), "KY": ("Kirkcaldy", "scotland"),
    "L": ("Liverpool", "north-west"), "LA": ("Lancaster", "north-west"), "LD": ("Llandrindod Wells", "wales"),
    "LE": ("Leicester", "east-midlands"), "LL": ("Llandudno", "wales"), "LN": ("Lincoln", "east-midlands"),
    "LS": ("Leeds", "yorkshire-and-the-humber"), "LU": ("Luton", "east-of-england"), "M": ("Manchester", "north-west"),
    "ME": ("Rochester", "south-east"), "MK": ("Milton Keynes", "south-east"), "ML": ("Motherwell", "scotland"),
    "N": ("London", "london"), "NE": ("Newcastle upon Tyne", "north-east"), "NG": ("Nottingham", "east-midlands"),
    "NN": ("Northampton", "east-midlands"), "NP": ("Newport", "wales"), "NR": ("Norwich", "east-of-england"),
    "NW": ("London", "london"), "OL": ("Oldham", "north-west"), "OX": ("Oxford", "south-east"),
    "PA": ("Paisley", "scotland"), "PE": ("Peterborough", "east-of-england"), "PH": ("Perth", "scotland"),
    "PL": ("Plymouth", "south-west"), "PO": ("Portsmouth", "south-east"), "PR": ("Preston", "north-west"),
    "RG": ("Reading", "south-east"), "RH": ("Redhill", "south-east"), "RM": ("Romford", "london"),
    "S": ("Sheffield", "yorkshire-and-the-humber"), "SA": ("Swansea", "wales"), "SE": ("London", "london"),
    "SG": ("Stevenage", "east-of-england"), "SK": ("Stockport", "north-west"), "SL": ("Slough", "south-east"),
    "SM": ("Sutton", "london"), "SN": ("Swindon", "south-west"), "SO": ("Southampton", "south-east"),
    "SP": ("Salisbury", "south-west"), "SR": ("Sunderland", "north-east"), "SS": ("Southend-on-Sea", "east-of-england"),
    "ST": ("Stoke-on-Trent", "west-midlands"), "SW": ("London", "london"), "SY": ("Shrewsbury", "west-midlands"),
    "TA": ("Taunton", "south-west"), "TD": ("Galashiels", "scotland"), "TF": ("Telford", "west-midlands"),
    "TN": ("Tunbridge Wells", "south-east"), "TQ": ("Torquay", "south-west"), "TR": ("Truro", "south-west"),
    "TS": ("Middlesbrough", "north-east"), "TW": ("Twickenham", "london"), "UB": ("Southall", "london"),
    "W": ("London", "london"), "WA": ("Warrington", "north-west"), "WC": ("London", "london"),
    "WD": ("Watford", "east-of-england"), "WF": ("Wakefield", "yorkshire-and-the-humber"), "WN": ("Wigan", "north-west"),
    "WR": ("Worcester", "west-midlands"), "WS": ("Walsall", "west-midlands"), "WV": ("Wolverhampton", "west-midlands"),
    "YO": ("York", "yorkshire-and-the-humber"), "ZE": ("Lerwick", "scotland"),
}


def mock_postcode(postcode: str) -> dict[str, str] | None:
    """Offline lookup by postcode area. Input must already be normalised."""
    m = re.match(r"^([A-Z]{1,2})[0-9]", postcode)
    if not m:
        return None
    hit = POSTCODE_AREAS.get(m.group(1))
    if hit is None:
        return None
    town, region = hit
    return {"region": region, "town": town, "postcode": postcode}


_SERIES_INDEX = {(spec.source, spec.series_id): key for key, spec in KEY_SPECS.items()}


def mock_series(source: str, series_id: str, region: str | None = None, table: MacroTable | None = None) -> list[Observation]:
    """Annual mock observations from the mock MacroTable (dated 1 July). Empty list for unknown series.

    region=None returns UK plus every covered region; a region returns only that region's rows.
    """
    key = _SERIES_INDEX.get((source, series_id)) or _SERIES_INDEX.get((source, series_id.upper()))
    if key is None:
        return []
    spec = KEY_SPECS[key]
    table = table or mock_macro_table()
    now = utcnow()
    out: list[Observation] = []
    for mv in table.values.values():
        if mv.key != key:
            continue
        if region is not None and mv.region != region:
            continue
        out.append(
            Observation(
                series_id=spec.series_id, source=source, date=date(mv.year, 7, 1), value=mv.value, unit=spec.unit,
                region=mv.region, fetched_at=now, status="mock",
            )
        )
    return sorted(out, key=lambda o: (o.region or "", o.date))


__all__ = ["POSTCODE_AREAS", "mock_postcode", "mock_series"]
