"""Live source adapters. Each maps one source to `Observation`."""

from lifeline_data.adapters.boe import BoEAdapter
from lifeline_data.adapters.landregistry import LandRegistryAdapter
from lifeline_data.adapters.nomis import NomisAdapter
from lifeline_data.adapters.ons import OnsAdapter
from lifeline_data.adapters.postcodes import PostcodesAdapter

ADAPTERS = {a.source_id: a for a in (BoEAdapter, OnsAdapter, NomisAdapter, LandRegistryAdapter)}

__all__ = ["ADAPTERS", "BoEAdapter", "LandRegistryAdapter", "NomisAdapter", "OnsAdapter", "PostcodesAdapter"]
