from abc import ABC
from abc import abstractmethod
from enum import Enum
from typing import Any
from typing import Dict
from typing import Optional

import aiohttp
import ujson
from aiocache import cached
from loguru import logger
from pydantic import BaseModel


class CarbonIntensitySource(Enum):
    FILE: str = "file"
    CO2SignalAPI: str = "CO2SignalAPI"


class Location(ABC, BaseModel):
    """
    Generic Location.
    """

    name: str
    co2g_kwh_source: CarbonIntensitySource = CarbonIntensitySource.FILE
    co2signal_api_key: Optional[str] = None
    co2signal_url: Optional[str] = None
    co2g_kwh: float = 0.0

    @classmethod
    async def request(cls, url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
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
                    return ujson.loads(text)
                except Exception as exception:
                    logger.exception(f"Failed to request this url: {url}")
                    raise exception

    @abstractmethod
    @cached()  # type: ignore
    async def get_latest_co2g_kwh(self) -> float:
        """
        Get the latest co2g_kwh for France.

        :return: the latest co2g_kwh
        """
        pass
