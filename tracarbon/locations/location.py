from abc import ABC
from abc import abstractmethod
from enum import Enum
from typing import Any
from typing import Dict

import aiohttp
import orjson
from aiocache import cached
from loguru import logger
from pydantic import BaseModel
from pydantic import Field


class CarbonIntensitySource(str, Enum):
    FILE = "file"
    CO2SignalAPI = "CO2SignalAPI"
    ElectricityMapsAPI = "ElectricityMapsAPI"


class EmissionFactorType(str, Enum):
    LIFECYCLE = "lifecycle"
    DIRECT = "direct"


class CarbonIntensityMetadata(BaseModel):
    """
    Metadata about the carbon intensity value used for emission calculations.
    """

    source: CarbonIntensitySource = CarbonIntensitySource.FILE
    co2g_kwh: float | None = None
    zone: str | None = None
    datetime: str | None = None
    updated_at: str | None = None
    emission_factor_type: EmissionFactorType | None = None
    is_estimated: bool | None = None
    estimation_method: str | None = None
    fallback_used: bool = False


class Location(ABC, BaseModel):
    """
    Generic Location.
    """

    name: str
    co2g_kwh_source: CarbonIntensitySource = CarbonIntensitySource.FILE
    co2signal_api_key: str | None = None
    co2signal_url: str | None = None
    co2g_kwh: float = 0.0
    emission_factor_type: EmissionFactorType = EmissionFactorType.LIFECYCLE
    carbon_intensity_metadata: CarbonIntensityMetadata = Field(default_factory=CarbonIntensityMetadata)

    @classmethod
    async def request(cls, url: str, headers: Dict[str, str] | None = None) -> Dict[str, Any]:
        """
        Launch an async request.

        :param url: url to request
        :param headers: headers to add to the request
        :return: the response
        """

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                try:
                    logger.info(f"Sending request to the url: {url}.")
                    text = await response.text()
                    return orjson.loads(text)
                except Exception as exception:
                    logger.exception(f"Failed to request this url: {url}")
                    raise exception

    @abstractmethod
    @cached()
    async def get_latest_co2g_kwh(self) -> float:
        """
        Get the latest co2g_kwh for France.

        :return: the latest co2g_kwh
        """
        pass
