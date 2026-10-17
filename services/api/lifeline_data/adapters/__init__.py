"""Live source adapters. Each maps one source to `Observation`."""

from lifeline_data.adapters.boe import BoEAdapter
from lifeline_data.adapters.calendar_weather import BankHolidaysAdapter, OpenMeteoAdapter
from lifeline_data.adapters.energy import CarbonIntensityAdapter, OctopusAdapter
from lifeline_data.adapters.keyed import (
    AdzunaAdapter,
    CompaniesHouseAdapter,
    DvlaAdapter,
    DvsaMotAdapter,
    EpcAdapter,
    StatXploreAdapter,
)
from lifeline_data.adapters.landregistry import LandRegistryAdapter
from lifeline_data.adapters.market import CoinGeckoAdapter, FrankfurterAdapter, FredAdapter, YahooAdapter
from lifeline_data.adapters.nomis import NomisAdapter
from lifeline_data.adapters.ons import OnsAdapter
from lifeline_data.adapters.place import EnvironmentAgencyAdapter, PoliceAdapter
from lifeline_data.adapters.postcodes import PostcodesAdapter

ADAPTERS = {
    a.source_id: a
    for a in (
        BoEAdapter,
        OnsAdapter,
        NomisAdapter,
        LandRegistryAdapter,
        BankHolidaysAdapter,
        OpenMeteoAdapter,
        FrankfurterAdapter,
        CoinGeckoAdapter,
        YahooAdapter,
        FredAdapter,
        OctopusAdapter,
        CarbonIntensityAdapter,
        PoliceAdapter,
        EnvironmentAgencyAdapter,
        CompaniesHouseAdapter,
        EpcAdapter,
        StatXploreAdapter,
        AdzunaAdapter,
        DvlaAdapter,
        DvsaMotAdapter,
    )
}

__all__ = [
    "ADAPTERS",
    "AdzunaAdapter",
    "BankHolidaysAdapter",
    "BoEAdapter",
    "CarbonIntensityAdapter",
    "CoinGeckoAdapter",
    "CompaniesHouseAdapter",
    "DvlaAdapter",
    "DvsaMotAdapter",
    "EnvironmentAgencyAdapter",
    "EpcAdapter",
    "FrankfurterAdapter",
    "FredAdapter",
    "LandRegistryAdapter",
    "NomisAdapter",
    "OctopusAdapter",
    "OnsAdapter",
    "OpenMeteoAdapter",
    "PoliceAdapter",
    "PostcodesAdapter",
    "StatXploreAdapter",
    "YahooAdapter",
]
