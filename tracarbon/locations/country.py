import csv
import importlib.resources
from typing import Any
from typing import Optional

import requests
import ujson
from aiocache import cached
from loguru import logger

from tracarbon.exceptions import CloudProviderRegionIsMissing
from tracarbon.exceptions import CO2SignalAPIKeyIsMissing
from tracarbon.exceptions import CountryIsMissing
from tracarbon.hardwares import CloudProviders
from tracarbon.locations.location import CarbonIntensitySource
from tracarbon.locations.location import Location


class Country(Location):
    """
    Country definition.
    """

    @classmethod
    def from_eu_file(cls, country_code_alpha_iso_2: str) -> "Country":
        """
        Get the country from the file.

        :param country_code_alpha_iso_2: the alpha_iso_2 name of the country
        :return:
        """
        with importlib.resources.path("tracarbon.locations.data", "co2-emission-intensity-9.exhibit.json") as resource:
            with open(str(resource)) as json_file:
                countries_values = ujson.load(json_file)["countries"]
                for country in countries_values:
                    if country_code_alpha_iso_2.lower() == country["name"]:
                        return cls.parse_obj(country)
        raise CountryIsMissing(f"The country [{country_code_alpha_iso_2}] is not in the co2 emission file.")

    @classmethod
    def get_current_country(cls, url: str = "http://ipinfo.io/json", timeout: int = 300) -> str:
        """
        Get the client's country using an internet access.

        :param url: the url to fetch the country from IP
        :param timeout: the timeout for the request
        :return: the client's country alpha_iso_2 name.
        """
        try:
            logger.debug(f"Send request to this url: {url}, timeout {timeout}s")
            text = requests.get(url, timeout=timeout).text
            content_json = ujson.loads(text)
            return content_json["country"]
        except Exception as exception:
            logger.error(f"Failed to request this url: {url}")
            raise exception

    @classmethod
    def get_location(
        cls,
        co2signal_api_key: Optional[str] = None,
        co2signal_url: Optional[str] = None,
        country_code_alpha_iso_2: Optional[str] = None,
    ) -> "Country":
        """
        Get the current location automatically: on cloud provider or a country.

        :param country_code_alpha_iso_2: the alpha iso 2 country name.
        :param co2signal_api_key: api key for fetching CO2 Signal API.
        :param co2signal_url: api url for fetching CO2 Signal API endpoint.
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
                co2signal_url=co2signal_url,
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

        logger.info(f"Request the latest carbon intensity in Co2g/kwh for your country {self.name}.")
        if not self.co2signal_api_key:
            raise CO2SignalAPIKeyIsMissing()
        url = f"{self.co2signal_url}{self.name}"
        response = {}
        try:
            response = await self.request(
                url=url,
                headers={"auth-token": self.co2signal_api_key},
            )
            logger.debug(f"Response from the {url}: {response}.")
            if "data" in response:
                response = response["data"]
            self.co2g_kwh = float(response["carbonIntensity"])
            logger.info(f"The latest carbon intensity of your country {self.name} is: {self.co2g_kwh} CO2g/kwh.")
        except Exception:
            logger.error(
                f'Failed to get the latest carbon intensity of your country {self.name} {response if response else ""}.'
                f"Please check your API configuration."
                f"Fallback to use the last known CO2g/kWh of your location {self.co2g_kwh}"
            )
        return self.co2g_kwh

    def __hash__(self) -> int:
        return hash(self.name)


class AWSLocation(Country):
    """
    AWS Location.
    """

    def __init__(self, region_name: str, **data: Any) -> None:
        with importlib.resources.path("tracarbon.locations.data", "grid-emissions-factors-aws.csv") as resource:
            co2g_kwh = None
            with open(str(resource)) as csv_file:
                reader = csv.reader(csv_file)
                for row in reader:
                    if row[0] == region_name:
                        co2g_kwh = float(row[3]) * 1000000
                        super().__init__(name=f"AWS({region_name})", co2g_kwh=co2g_kwh, **data)
                if not co2g_kwh:
                    raise CloudProviderRegionIsMissing(
                        f"The region [{region_name}] is not in the AWS grid emissions factors file."
                    )

    @cached()  # type: ignore
    async def get_latest_co2g_kwh(self) -> float:
        """
        Get the latest co2g_kwh for AWS.

        :return: the latest co2g_kwh
        """
        return self.co2g_kwh

    async def get_co2g_kwh(self) -> float:
        """
        Get the Co2g per kwh.

        :return: the co2g/kwh value
        """
        return self.co2g_kwh
