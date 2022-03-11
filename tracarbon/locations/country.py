import importlib.resources
from datetime import datetime, timedelta

import ujson
from aiocache import cached
from loguru import logger

from tracarbon.conf import tracarbon_configuration as conf
from tracarbon.locations.location import Location


class Country(Location):
    """
    Country definition.
    """

    name_alpha_iso_2: str
    co2g_kwh: float

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
                    if country_name_alpha_iso_2 == country["name_alpha_iso_2"]:
                        return cls.parse_obj(country)
        raise ValueError(
            f"The country {country_name_alpha_iso_2} is not in the co2 emission file."
        )

    @classmethod
    @cached()  # type: ignore
    async def get_location(cls, api_activated: bool = conf.api_activated) -> "Country":
        """
        Get the client location.

        :return: the client country.
        """
        country_name_alpha_iso_2 = await cls.get_current_country()
        country = cls.from_eu_file(country_name_alpha_iso_2=country_name_alpha_iso_2)
        if api_activated:
            if country.name_alpha_iso_2 == "fr":
                country = France(co2g_kwh=country.co2g_kwh)
        return country

    async def get_latest_co2g_kwh(self, today_date: str, hour: str) -> float:
        """
        Get the latest co2g_kwh for the Location.

        :param today_date: the date for the request
        :param hour: the hour for the request
        :return: the latest co2g_kwh
        """
        return self.co2g_kwh

    async def get_co2g_kwh(self) -> float:
        """
        Get the Co2g per kwh for the Location.

        :return: the co2g_kwh.
        """
        return self.co2g_kwh

    def __hash__(self) -> int:
        return hash(self.name_alpha_iso_2)


class France(Country):
    """France Location."""

    name_alpha_iso_2 = "fr"

    @cached()  # type: ignore
    async def get_latest_co2g_kwh(self, today_date: str, hour: str) -> float:
        """
        Get the latest co2g_kwh for France.

        :param today_date: the date for the request
        :param hour: the hour for the request
        :return: the latest co2g_kwh
        """
        logger.info(f"Request the current french co2 g/kwh {today_date} {hour}.")
        response = await self.request(
            f"https://opendata.reseaux-energies.fr/api/records/1.0/search/?dataset=eco2mix-national-tr&q=&rows=1&facet=taux_co2&facet=date_heure&refine.date={today_date}&refine.heure={hour}"
        )
        try:
            self.co2g_kwh = float(response["records"][0]["fields"]["taux_co2"])
            logger.info(f"co2g/kwh of France is: {self.co2g_kwh} g/kwh.")
        except Exception:
            logger.exception(
                "Failed to get the latest update of the co2 update for France."
            )
        return self.co2g_kwh

    async def get_co2g_kwh(self) -> float:
        """
        Get the latest co2/kwh update from the French's website https://www.rte-france.com/eco2mix.

        :return: the last known co2g/kwh value
        """
        now = datetime.now()
        today_date = now.strftime("%Y-%m-%d")
        previous_quarter = now - timedelta(minutes=61)
        last_quarter_minute = 15 * (previous_quarter.minute // 15)
        hour = previous_quarter.replace(minute=last_quarter_minute).strftime("%H:%M")
        return await self.get_latest_co2g_kwh(today_date=today_date, hour=hour)
