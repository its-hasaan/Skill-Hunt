"""
Connector registry.

Maps the connector key used in sources_config.json to its class. To add a new
source: write a module with a BaseConnector subclass, import it here, and add
it to CONNECTOR_REGISTRY (plus a block in sources_config.json).
"""

from .base import BaseConnector, NormalizedJob, build_session
from .remoteok import RemoteOKConnector
from .weworkremotely import WeWorkRemotelyConnector
from .arbeitnow import ArbeitnowConnector
from .jobicy import JobicyConnector
from .himalayas import HimalayasConnector
from .jooble import JoobleConnector
from .themuse import TheMuseConnector
from .usajobs import USAJobsConnector
from .generic_scraper import GenericScraperConnector

CONNECTOR_REGISTRY = {
    "remoteok": RemoteOKConnector,
    "weworkremotely": WeWorkRemotelyConnector,
    "arbeitnow": ArbeitnowConnector,
    "jobicy": JobicyConnector,
    "himalayas": HimalayasConnector,
    "jooble": JoobleConnector,
    "themuse": TheMuseConnector,
    "usajobs": USAJobsConnector,
    "generic_scraper": GenericScraperConnector,
}

__all__ = [
    "BaseConnector",
    "NormalizedJob",
    "build_session",
    "CONNECTOR_REGISTRY",
]
