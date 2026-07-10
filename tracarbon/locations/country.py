import csv
import importlib.resources
import os
from typing import Any
from typing import cast
from urllib.parse import urlencode
from urllib.parse import urlparse

import orjson
import requests
from aiocache import cached
from loguru import logger

from tracarbon.exceptions import CloudProviderRegionIsMissing
from tracarbon.exceptions import CO2SignalAPIKeyIsMissing
from tracarbon.exceptions import CountryIsMissing
from tracarbon.hardwares import AWS
from tracarbon.hardwares import GCP
from tracarbon.hardwares import Azure
from tracarbon.hardwares import CloudProviders
from tracarbon.locations.location import CarbonIntensityMetadata
from tracarbon.locations.location import CarbonIntensitySource
from tracarbon.locations.location import EmissionFactorType
from tracarbon.locations.location import Location

__all__ = [
    "Country",
    "AWSLocation",
    "CloudLocation",
    "GCPLocation",
    "AzureLocation",
]


class Country(Location):
    """
    Country definition.
    """

    data_center_provider: str | None = None
    data_center_region: str | None = None

    def _update_carbon_intensity_metadata(
        self,
        response: dict[str, Any] | None = None,
        fallback_used: bool = False,
    ) -> None:
        payload = response.get("data", response) if response else {}
        emission_factor_type = payload.get("emissionFactorType")
        if not emission_factor_type and self.co2g_kwh_source == CarbonIntensitySource.ElectricityMapsAPI:
            emission_factor_type = self.emission_factor_type.value
        self.carbon_intensity_metadata = CarbonIntensityMetadata(
            source=self.co2g_kwh_source,
            co2g_kwh=self.co2g_kwh,
            zone=payload.get("zone") or (response or {}).get("countryCode") or self.name,
            datetime=payload.get("datetime"),
            updated_at=payload.get("updatedAt"),
            emission_factor_type=EmissionFactorType(emission_factor_type) if emission_factor_type else None,
            is_estimated=payload.get("isEstimated"),
            estimation_method=payload.get("estimationMethod"),
            fallback_used=fallback_used,
        )

    @classmethod
    def from_eu_file(cls, country_code_alpha_iso_2: str) -> "Country":
        """
        Get the country from the file.

        :param country_code_alpha_iso_2: the alpha_iso_2 name of the country
        :return:
        """
        resource_file = importlib.resources.files("tracarbon.locations.data").joinpath("eu-co2-emission-intensity.json")
        with resource_file.open("rb") as json_file:
            countries_values = orjson.loads(json_file.read())["countries"]
            for country in countries_values:
                if country_code_alpha_iso_2.lower() == country["name"]:
                    return cls.model_validate(country)
        raise CountryIsMissing(f"The country [{country_code_alpha_iso_2}] is not in the co2 emission file.")

    @classmethod
    def get_current_country(
        cls,
        url: str = "https://ipinfo.io/json",
        timeout: int = 10,
        token: str | None = None,
    ) -> str:
        """
        Get the client's country using an internet access.

        :param url: the url to fetch the country from IP
        :param timeout: the timeout in seconds for the request
        :param token: an ipinfo.io API token to lift the anonymous rate limit,
            falling back to the TRACARBON_IPINFO_TOKEN environment variable
        :return: the client's country alpha_iso_2 name.
        """
        token = token or os.environ.get("TRACARBON_IPINFO_TOKEN")
        headers = {"Authorization": f"Bearer {token}"} if token else None
        try:
            logger.debug(f"Send request to this url: {url}, timeout {timeout}s")
            text = requests.get(url, timeout=timeout, headers=headers).text
            content_json = orjson.loads(text)
            return content_json["country"]
        except Exception as exception:
            logger.error(f"Failed to request this url: {url}")
            raise exception

    @classmethod
    def get_location(
        cls,
        co2signal_api_key: str | None = None,
        co2signal_url: str | None = None,
        country_code_alpha_iso_2: str | None = None,
        emission_factor_type: str | None = None,
    ) -> "Country":
        """
        Get the current location automatically: on cloud provider or a country.

        :param country_code_alpha_iso_2: the alpha iso 2 country name.
        :param co2signal_api_key: api key for fetching CO2 Signal API or Electricity Maps API.
        :param co2signal_url: api url for fetching the carbon intensity API endpoint.
        :param emission_factor_type: the emission factor type (lifecycle or direct) for Electricity Maps API.
        :return: the country
        """
        is_electricity_maps = False
        if co2signal_url:
            host = urlparse(co2signal_url).hostname or ""
            is_electricity_maps = host == "electricitymaps.com" or host.endswith(".electricitymaps.com")
        factor_type = EmissionFactorType(emission_factor_type) if emission_factor_type else EmissionFactorType.LIFECYCLE

        # Cloud Providers
        cloud_provider = CloudProviders.auto_detect()
        if cloud_provider:
            provider_display_name = type(cloud_provider).__name__
            if co2signal_api_key and is_electricity_maps:
                return cls(
                    co2signal_api_key=co2signal_api_key,
                    co2signal_url=co2signal_url,
                    name=f"{provider_display_name}({cloud_provider.region_name})",
                    co2g_kwh_source=CarbonIntensitySource.ElectricityMapsAPI,
                    emission_factor_type=factor_type,
                    data_center_provider=provider_display_name.lower(),
                    data_center_region=cloud_provider.region_name,
                )
            if isinstance(cloud_provider, AWS):
                return AWSLocation(region_name=cloud_provider.region_name)
            if isinstance(cloud_provider, GCP):
                return GCPLocation(region_name=cloud_provider.region_name)
            if isinstance(cloud_provider, Azure):
                return AzureLocation(region_name=cloud_provider.region_name)

        # Local
        if not country_code_alpha_iso_2:
            country_code_alpha_iso_2 = cls.get_current_country()
        if co2signal_api_key:
            source = (
                CarbonIntensitySource.ElectricityMapsAPI if is_electricity_maps else CarbonIntensitySource.CO2SignalAPI
            )
            return cls(
                co2signal_api_key=co2signal_api_key,
                co2signal_url=co2signal_url,
                name=country_code_alpha_iso_2,
                co2g_kwh_source=source,
                emission_factor_type=factor_type,
            )
        return cls.from_eu_file(country_code_alpha_iso_2=country_code_alpha_iso_2)

    @cached(
        ttl=3600,
    )
    async def get_latest_co2g_kwh(self) -> float:
        """
        Get the latest CO2g_kwh for the Location from Electricity Maps API or CO2 Signal API.

        :return: the latest CO2g_kwh
        """
        if self.co2g_kwh_source == CarbonIntensitySource.FILE:
            if self.co2g_kwh is None:
                raise CountryIsMissing(f"No carbon intensity is available for {self.name}.")
            self._update_carbon_intensity_metadata()
            return self.co2g_kwh

        logger.info(f"Request the latest carbon intensity in Co2g/kwh for your country {self.name}.")
        if not self.co2signal_api_key:
            raise CO2SignalAPIKeyIsMissing()

        if self.co2g_kwh_source == CarbonIntensitySource.ElectricityMapsAPI:
            query = {
                "emissionFactorType": self.emission_factor_type.value,
            }
            if self.data_center_provider and self.data_center_region:
                query["dataCenterProvider"] = self.data_center_provider
                query["dataCenterRegion"] = self.data_center_region
            else:
                query["zone"] = self.name
            url = f"{self.co2signal_url}?{urlencode(query)}"
        else:
            url = f"{self.co2signal_url}{self.name}"

        response = {}
        try:
            response = await self.request(
                url=url,
                headers={"auth-token": self.co2signal_api_key},
            )
            logger.debug(f"Response from the {url}: {response}.")
            raw_response = response
            if "data" in response:
                response = response["data"]
            self.co2g_kwh = float(response["carbonIntensity"])
            self._update_carbon_intensity_metadata(response=raw_response)
            logger.info(f"The latest carbon intensity of your country {self.name} is: {self.co2g_kwh} CO2g/kwh.")
        except Exception:
            if self.co2g_kwh is None:
                raise
            self._update_carbon_intensity_metadata(response=response if response else None, fallback_used=True)
            logger.error(
                f"Failed to get the latest carbon intensity of your country {self.name} {response if response else ''}."
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
        resource_file = importlib.resources.files("tracarbon.locations.data").joinpath("grid-emissions-factors-aws.csv")
        co2g_kwh = None
        with resource_file.open("r", encoding="utf-8") as csv_file:
            reader = csv.reader(csv_file)
            for row in reader:
                if row[0] == region_name:
                    co2g_kwh = float(row[3]) * 1000000
                    super().__init__(name=f"AWS({region_name})", co2g_kwh=co2g_kwh, **data)
            if not co2g_kwh:
                raise CloudProviderRegionIsMissing(
                    f"The region [{region_name}] is not in the AWS grid emissions factors file."
                )

    @cached()
    async def get_latest_co2g_kwh(self) -> float:
        """
        Get the latest co2g_kwh for AWS.

        :return: the latest co2g_kwh
        """
        self._update_carbon_intensity_metadata()
        return cast(float, self.co2g_kwh)

    async def get_co2g_kwh(self) -> float:
        """
        Get the Co2g per kwh.

        :return: the co2g/kwh value
        """
        return cast(float, self.co2g_kwh)


class CloudLocation(Country):
    """
    Base class for cloud provider locations.
    """

    @classmethod
    def _get_csv_filename(cls) -> str:
        """Get the CSV filename for this cloud provider."""
        raise NotImplementedError

    @classmethod
    def _get_provider_name(cls) -> str:
        """Get the provider name for display."""
        raise NotImplementedError

    @classmethod
    def _get_conversion_factor(cls) -> float:
        """
        Get the conversion factor to convert CSV value to gCO2/kWh.

        :return: Conversion factor (1.0 if already in gCO2/kWh, 1000000 if in metric tons/kWh)
        """
        return 1000000.0  # Default: convert from metric tons/kWh to gCO2/kWh

    def __init__(self, region_name: str, **data: Any) -> None:
        resource_file = importlib.resources.files("tracarbon.locations.data").joinpath(self._get_csv_filename())
        provider_name = self._get_provider_name()
        conversion_factor = self._get_conversion_factor()
        co2g_kwh = None
        with resource_file.open("r", encoding="utf-8") as csv_file:
            reader = csv.reader(csv_file)
            header = next(reader)  # Get header to determine format
            # Determine CO2e column index based on header
            # AWS: Region,Country,NERC Region,CO2e (metric ton/kWh),Source -> index 3
            # Azure: Region,Location,CO2e (metric ton/kWh),Source -> index 2
            # GCP: Google Cloud Region,Location,Google CFE,Grid carbon intensity (gCO2eq / kWh) -> index 3
            co2e_col_idx = None
            for idx, col in enumerate(header):
                if "CO2e" in col or "carbon intensity" in col.lower():
                    co2e_col_idx = idx
                    break

            if co2e_col_idx is None:
                raise ValueError(f"Could not find CO2e column in {provider_name} CSV header: {header}")

            for row in reader:
                if row[0] == region_name:
                    # Apply conversion factor (1.0 for GCP, 1000000 for AWS/Azure)
                    co2g_kwh = float(row[co2e_col_idx]) * conversion_factor
                    super().__init__(name=f"{provider_name}({region_name})", co2g_kwh=co2g_kwh, **data)
                    return
        if not co2g_kwh:
            raise CloudProviderRegionIsMissing(
                f"The region [{region_name}] is not in the {provider_name} grid emissions factors file."
            )

    @cached()
    async def get_latest_co2g_kwh(self) -> float:
        """
        Get the latest co2g_kwh for this cloud provider.

        :return: the latest co2g_kwh
        """
        self._update_carbon_intensity_metadata()
        return cast(float, self.co2g_kwh)

    async def get_co2g_kwh(self) -> float:
        """
        Get the Co2g per kwh.

        :return: the co2g/kwh value
        """
        return cast(float, self.co2g_kwh)


class GCPLocation(CloudLocation):
    """GCP Location."""

    @classmethod
    def _get_csv_filename(cls) -> str:
        return "grid-emissions-factors-gcp.csv"

    @classmethod
    def _get_provider_name(cls) -> str:
        return "GCP"

    @classmethod
    def _get_conversion_factor(cls) -> float:
        """
        GCP CSV has Grid carbon intensity already in gCO2eq/kWh, no conversion needed.

        :return: 1.0 (no conversion)
        """
        return 1.0  # GCP values are already in gCO2/kWh

    def __init__(self, region_name: str, **data: Any) -> None:
        """Initialize GCP location with region name."""
        super().__init__(region_name=region_name, **data)


class AzureLocation(CloudLocation):
    """Azure Location."""

    @classmethod
    def _get_csv_filename(cls) -> str:
        return "grid-emissions-factors-azure.csv"

    @classmethod
    def _get_provider_name(cls) -> str:
        return "Azure"

    def __init__(self, region_name: str, **data: Any) -> None:
        super().__init__(region_name=region_name, **data)
