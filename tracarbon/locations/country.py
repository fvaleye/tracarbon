import csv
import importlib.resources
from datetime import datetime, timedelta
from typing import Any, Optional

import requests
import ujson
from aiocache import cached
from loguru import logger

from tracarbon.conf import tracarbon_configuration as conf
from tracarbon.exceptions import CloudProviderRegionIsMissing, CountryIsMissing
from tracarbon.hardwares import CloudProviders
from tracarbon.locations.location import Location


class Country(Location):
    """
    Country definition.
    """

    name: str
    co2g_kwh: float
    co2g_kwh_source: str = "file"

    @classmethod
    def from_eu_file(cls, country_name_alpha_iso_2: str) -> "Country":
        """
        Get the country from the file.

        :param country_name_alpha_iso_2: the alpha_iso_2 name of the country
        :return:
        """
        with importlib.resources.path(
            "tracarbon.locations.data", "co2-emission-intensity-9.exhibit.json"
        ) as resource:
            with open(str(resource)) as json_file:
                countries_values = ujson.load(json_file)["countries"]
                for country in countries_values:
                    if country_name_alpha_iso_2 == country["name"]:
                        return cls.parse_obj(country)
        raise CountryIsMissing(
            f"The country [{country_name_alpha_iso_2}] is not in the co2 emission file."
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
        country_name_alpha_iso_2: Optional[str] = None,
        api_activated: bool = conf.api_activated,
    ) -> "Country":
        """
        Get the current location automatically: on cloud provider or a country.
        If country_name_alpha_iso_2 is provided, the country will be configured from the local carbon emission file.

        :param country_name_alpha_iso_2: the alpha iso 2 country name.
        :param api_activated: activation of the live carbon emissions from available country's APIs.
        :return: the country
        """
        # Cloud Providers
        cloud_provider = CloudProviders.auto_detect()
        if cloud_provider:
            return AWSLocation(region_name=cloud_provider.region_name)

        # Local
        if country_name_alpha_iso_2:
            return cls.from_eu_file(country_name_alpha_iso_2=country_name_alpha_iso_2)
        country_name_alpha_iso_2 = cls.get_current_country()
        country = cls.from_eu_file(country_name_alpha_iso_2=country_name_alpha_iso_2)
        if api_activated:
            if country.name == "fr":
                country = France(co2g_kwh=country.co2g_kwh)
        return country

    async def get_latest_co2g_kwh(self, today_date: str, hour: str) -> float:
        """
        Get the latest CO2g_kwh for the Location.

        :param today_date: the date for the request
        :param hour: the hour for the request
        :return: the latest CO2g_kwh
        """
        return self.co2g_kwh

    async def get_co2g_kwh(self) -> float:
        """
        Get the CO2g per kwh for the Location.

        :return: the CO2g/kwh.
        """
        return self.co2g_kwh

    def __hash__(self) -> int:
        return hash(self.name)


class France(Country):
    """France Location."""

    name: str = "fr"
    co2g_kwh_source: str = "API"

    @cached()  # type: ignore
    async def get_latest_co2g_kwh(self, today_date: str, hour: str) -> float:
        """
        Get the latest CO2g_kwh for France.

        :param today_date: the date for the request
        :param hour: the hour for the request
        :return: the latest CO2g_kwh
        """
        logger.info(
            f"Request the current emission factor in CO2g/kwh of France at the time of {today_date} {hour}."
        )
        response = await self.request(
            f"https://opendata.reseaux-energies.fr/api/records/1.0/search/?dataset=eco2mix-national-tr&q=&rows=1&facet=taux_co2&facet=date_heure&refine.date={today_date}&refine.heure={hour}"
        )
        try:
            self.co2g_kwh = float(response["records"][0]["fields"]["taux_co2"])
            logger.info(
                f"The emission factor in CO2g/kwh of France is: {self.co2g_kwh} g/kwh."
            )
        except Exception:
            logger.error(
                "Failed to get the latest update of the CO2g/kwh update of France."
            )
        return self.co2g_kwh

    async def get_co2g_kwh(self) -> float:
        """
        Get the latest co2/kwh update from the French's website https://www.rte-france.com/eco2mix.

        :return: the last known CO2g/kwh value
        """
        now = datetime.now()
        today_date = now.strftime("%Y-%m-%d")
        previous_quarter = now - timedelta(minutes=61)
        last_quarter_minute = 15 * (previous_quarter.minute // 15)
        hour = previous_quarter.replace(minute=last_quarter_minute).strftime("%H:%M")
        return await self.get_latest_co2g_kwh(today_date=today_date, hour=hour)


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
