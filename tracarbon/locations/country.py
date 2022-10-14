import csv
import importlib.resources
from enum import Enum
from typing import Any, Optional

import requests
import ujson
from aiocache import cached
from loguru import logger

from tracarbon.exceptions import (
    CloudProviderRegionIsMissing,
    CO2SignalAPIKeyIsMissing,
    CountryIsMissing,
)
from tracarbon.hardwares import CloudProviders
from tracarbon.locations.location import Location


class CarbonIntensitySource(Enum):
    FILE: str = "file"
    CO2SignalAPI: str = "CO2SignalAPI"


class Country(Location):
    """
    Country definition.
    """

    co2signal_api_key: Optional[str] = None
    co2g_kwh: float = 0.0
    co2g_kwh_source: CarbonIntensitySource = CarbonIntensitySource.FILE

    @classmethod
    def from_eu_file(cls, country_code_alpha_iso_2: str) -> "Country":
        """
        Get the country from the file.

        :param country_code_alpha_iso_2: the alpha_iso_2 name of the country
        :return:
        """
        with importlib.resources.path(
            "tracarbon.locations.data", "co2-emission-intensity-9.exhibit.json"
        ) as resource:
            with open(str(resource)) as json_file:
                countries_values = ujson.load(json_file)["countries"]
                for country in countries_values:
                    if country_code_alpha_iso_2 == country["name"]:
                        return cls.parse_obj(country)
        raise CountryIsMissing(
            f"The country [{country_code_alpha_iso_2}] is not in the co2 emission file."
        )

    @classmethod
    def get_current_country(cls, url: str = "http://ipinfo.io/json") -> str:
        """
        Get the client's country using an internet access.

        :return: the client's country alpha_iso_2 name.
        """
        try:
            logger.debug(f"Send request to this url: {url}")
            text = requests.get(url).text
            content_json = ujson.loads(text)
            return content_json["country"].lower()
        except Exception as exception:
            logger.error(f"Failed to request this url: {url}")
            raise exception

    @classmethod
    def get_location(
        cls,
        co2signal_api_key: Optional[str] = None,
        country_code_alpha_iso_2: Optional[str] = None,
    ) -> "Country":
        """
        Get the current location automatically: on cloud provider or a country.

        :param country_code_alpha_iso_2: the alpha iso 2 country name.
        :param co2signal_api_key: api key for fetching CO2 Signal API.
        :return: the country
        """
        # Cloud Providers
        cloud_provider = CloudProviders.auto_detect()
        if cloud_provider:
            return AWSLocation(region_name=cloud_provider.region_name)

        # Local
        if not country_code_alpha_iso_2:
            country_code_alpha_iso_2 = cls.get_current_country()
        if co2signal_api_key:
            return cls(
                co2signal_api_key=co2signal_api_key,
                name=country_code_alpha_iso_2,
                co2g_kwh_source=CarbonIntensitySource.CO2SignalAPI,
            )
        return cls.from_eu_file(country_code_alpha_iso_2=country_code_alpha_iso_2)

    @cached(
        ttl=3600,
    )  # type: ignore
    async def get_latest_co2g_kwh(self) -> float:
        """
        Get the latest CO2g_kwh for the Location from https://www.co2signal.com/.

        :return: the latest CO2g_kwh
        """
        if self.co2g_kwh_source == CarbonIntensitySource.FILE:
            return self.co2g_kwh

        logger.info(
            f"Request the latest carbon intensity in CO2g/kwh for your country {self.name}."
        )
        if not self.co2signal_api_key:
            raise CO2SignalAPIKeyIsMissing()
        response = await self.request(
            url=f"https://api.co2signal.com/v1/latest?countryCode={self.name}",
            headers={"auth-token": self.co2signal_api_key},
        )
        try:
            self.co2g_kwh = float(response["data"]["carbonIntensity"])
            logger.info(
                f"The latest carbon intensity of your country {self.name} is: {self.co2g_kwh} CO2g/kwh."
            )
        except Exception:
            logger.error(
                f"Failed to get the latest carbon intensity of your country {self.name}, response: {response}"
            )
        return self.co2g_kwh

    def __hash__(self) -> int:
        return hash(self.name)


class AWSLocation(Country):
    """
    AWS Location.
    """

    def __init__(self, region_name: str, **data: Any) -> None:
        with importlib.resources.path(
            "tracarbon.locations.data", "grid-emissions-factors-aws.csv"
        ) as resource:
            co2g_kwh = None
            with open(str(resource)) as csv_file:
                reader = csv.reader(csv_file)
                for row in reader:
                    if row[0] == region_name:
                        co2g_kwh = float(row[3]) * 1000000
                        super().__init__(
                            name=f"AWS({region_name})", co2g_kwh=co2g_kwh, **data
                        )
                if not co2g_kwh:
                    raise CloudProviderRegionIsMissing(
                        f"The region [{region_name}] is not in the AWS grid emissions factors file."
                    )

    @cached()  # type: ignore
    async def get_latest_co2g_kwh(self, today_date: str, hour: str) -> float:
        """
        Get the latest co2g_kwh for AWS.

        :param today_date: the date for the request
        :param hour: the hour for the request
        :return: the latest co2g_kwh
        """
        return self.co2g_kwh

    async def get_co2g_kwh(self) -> float:
        """
        Get the Co2g per kwh.

        :return: the co2g/kwh value
        """
        return self.co2g_kwh
