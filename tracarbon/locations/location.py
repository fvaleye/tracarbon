from abc import ABC, abstractmethod
from typing import Any, Awaitable, Dict

import aiohttp
import ujson
from aiocache import cached
from loguru import logger
from pydantic import BaseModel


class Location(ABC, BaseModel):
    """
    Generic Location.
    """

    @classmethod
    async def request(cls, url: str) -> Dict[str, Any]:
        """
        Launch an async request.

        :param url: url to request
        :return: the response
        """

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                try:
                    logger.info(f"Sending request to the url: {url}.")
                    text = await response.text()
                    return ujson.loads(text)
                except Exception as exception:
                    logger.exception(f"Failed to request this url: {url}")
                    raise exception

    @classmethod
    async def get_current_country(cls, url: str = "http://ipinfo.io/json") -> str:
        """
        Get the client's country.

        :return: the client's country alpha_iso_2 name.
        """
        response = await cls.request(url=url)
        return response["country"].lower()

    @abstractmethod
    @cached()  # type: ignore
    async def get_latest_co2g_kwh(self, today_date: str, hour: str) -> float:
        """
        Get the latest co2g_kwh for France.

        :param today_date: the date for the request
        :param hour: the hour for the request
        :return: the latest co2g_kwh
        """
        pass

    @abstractmethod
    async def get_co2g_kwh(self) -> float:
        """
        Get the Co2g per kwh.

        :return: the co2g/kwh value
        """
        pass
