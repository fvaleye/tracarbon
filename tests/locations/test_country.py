import asyncio
from urllib.parse import parse_qs
from urllib.parse import urlparse

import pytest

from tracarbon.hardwares.cloud_providers import AWS
from tracarbon.hardwares.cloud_providers import GCP
from tracarbon.hardwares.cloud_providers import Azure
from tracarbon.hardwares.cloud_providers import CloudProviders
from tracarbon.locations import CarbonIntensityMetadata
from tracarbon.locations import CarbonIntensitySource
from tracarbon.locations import Country
from tracarbon.locations.location import EmissionFactorType


@pytest.mark.parametrize("source", [CarbonIntensitySource.CO2SignalAPI, CarbonIntensitySource.ElectricityMapsAPI])
def test_carbon_intensity_cache_expires_across_event_loops(mocker, monkeypatch, source):
    monkeypatch.setenv("AIOCACHE_DISABLE", "0")
    clock = mocker.patch("time.monotonic", return_value=1000.0)
    request = mocker.patch.object(Country, "request", return_value={"carbonIntensity": 100.0})
    country = Country(
        name="cache-expiry",
        co2signal_api_key="API_KEY",
        co2signal_url="https://api.electricitymaps.com/v4/carbon-intensity/latest",
        co2g_kwh_source=source,
        co2g_kwh=100.0,
        carbon_intensity_metadata=CarbonIntensityMetadata(
            source=source,
            co2g_kwh=100.0,
            zone="cache-expiry",
            emission_factor_type=(
                EmissionFactorType.LIFECYCLE if source == CarbonIntensitySource.ElectricityMapsAPI else None
            ),
        ),
    )

    assert asyncio.run(country.get_latest_co2g_kwh()) == 100.0
    request.return_value = {"carbonIntensity": 200.0}
    clock.return_value = 4599.0
    assert asyncio.run(country.get_latest_co2g_kwh()) == 100.0
    assert request.await_count == 1

    clock.return_value = 4600.0
    assert asyncio.run(country.get_latest_co2g_kwh()) == 200.0
    assert request.await_count == 2
    assert country.carbon_intensity_metadata.co2g_kwh == 200.0

    clock.return_value = 8200.0
    request.side_effect = RuntimeError("api failed")
    assert asyncio.run(country.get_latest_co2g_kwh()) == 200.0
    assert country.carbon_intensity_metadata.fallback_used
    clock.return_value = 11799.0
    assert asyncio.run(country.get_latest_co2g_kwh()) == 200.0
    assert request.await_count == 3

    clock.return_value = 11800.0
    request.side_effect = None
    request.return_value = {"carbonIntensity": 300.0}
    assert asyncio.run(country.get_latest_co2g_kwh()) == 300.0
    assert request.await_count == 4
    assert not country.carbon_intensity_metadata.fallback_used


@pytest.mark.parametrize("changed_field", ["name", "co2signal_api_key", "AIOCACHE_DISABLE"])
def test_carbon_intensity_cache_respects_configuration_changes(mocker, monkeypatch, changed_field):
    monkeypatch.setenv("AIOCACHE_DISABLE", "0")
    request = mocker.patch.object(Country, "request", return_value={"carbonIntensity": 100.0})
    country = Country(
        name="FR",
        co2signal_api_key="API_KEY",
        co2g_kwh_source=CarbonIntensitySource.CO2SignalAPI,
    )
    assert asyncio.run(country.get_latest_co2g_kwh()) == 100.0
    assert asyncio.run(country.get_latest_co2g_kwh()) == 100.0
    assert request.await_count == 1

    if changed_field == "AIOCACHE_DISABLE":
        monkeypatch.setenv(changed_field, "1")
    else:
        setattr(country, changed_field, "changed")
    request.return_value = {"carbonIntensity": 200.0}
    assert asyncio.run(country.get_latest_co2g_kwh()) == 200.0
    assert request.await_count == 2


@pytest.mark.asyncio
async def test_france_location_should_return_latest_known(mocker):
    co2_expected = 51.1
    response = {
        "countryCode": "FR",
        "data": {
            "carbonIntensity": co2_expected,
            "datetime": "2017-02-09T08:30:00.000Z",
            "fossilFuelPercentage": 12.028887656434616,
        },
        "status": "ok",
        "units": {"carbonIntensity": "gCO2eq/kWh"},
    }
    mocker.patch.object(Country, "request", return_value=response)
    co2signal_api_key = "API_KEY"

    country = Country(
        name="fr",
        co2signal_api_key=co2signal_api_key,
        co2g_kwh_source=CarbonIntensitySource.CO2SignalAPI,
        co2g_kwh=co2_expected,
    )

    result = await country.get_latest_co2g_kwh()

    assert result == co2_expected
    assert country.name == "fr"
    assert country.co2g_kwh == co2_expected
    assert country.co2g_kwh_source == CarbonIntensitySource.CO2SignalAPI


@pytest.mark.asyncio
async def test_france_location_with_recent_api_versions_should_return_latest_known(
    mocker,
):
    co2_expected = 83
    response = {
        "zone": "FR",
        "carbonIntensity": co2_expected,
        "datetime": "2023-03-20T17:00:00.000Z",
        "updatedAt": "2023-03-20T16:51:02.892Z",
        "createdAt": "2023-03-17T17:54:01.319Z",
        "emissionFactorType": "lifecycle",
        "isEstimated": True,
        "estimationMethod": "TIME_SLICER_AVERAGE",
    }
    mocker.patch.object(Country, "request", return_value=response)
    co2signal_api_key = "API_KEY"

    country = Country(
        name="fr",
        co2signal_api_key=co2signal_api_key,
        co2g_kwh_source=CarbonIntensitySource.CO2SignalAPI,
        co2g_kwh=co2_expected,
    )

    result = await country.get_latest_co2g_kwh()

    assert result == co2_expected
    assert country.name == "fr"
    assert country.co2g_kwh == co2_expected
    assert country.co2g_kwh_source == CarbonIntensitySource.CO2SignalAPI


@pytest.mark.asyncio
async def test_france_location_should_return_taux_co2():
    co2_expected = 51.1
    co2signal_api_key = ""
    country = Country(co2signal_api_key=co2signal_api_key, name="fr", co2g_kwh=51.1)

    result = await country.get_latest_co2g_kwh()

    assert result == co2_expected
    assert country.name == "fr"
    assert country.co2g_kwh == co2_expected
    assert country.co2g_kwh_source == CarbonIntensitySource.FILE


@pytest.mark.asyncio
async def test_electricity_maps_api_v4_lifecycle(mocker):
    co2_expected = 67.0
    response = {
        "zone": "FR",
        "carbonIntensity": co2_expected,
        "datetime": "2025-01-15T12:00:00.000Z",
        "updatedAt": "2025-01-15T11:51:02.892Z",
        "createdAt": "2025-01-15T11:54:01.319Z",
        "emissionFactorType": "lifecycle",
        "isEstimated": False,
        "estimationMethod": None,
    }
    request = mocker.patch.object(Country, "request", return_value=response)

    country = Country(
        name="FR",
        co2signal_api_key="API_KEY",
        co2signal_url="https://api.electricitymaps.com/v4/carbon-intensity/latest",
        co2g_kwh_source=CarbonIntensitySource.ElectricityMapsAPI,
        emission_factor_type=EmissionFactorType.LIFECYCLE,
    )

    result = await country.get_latest_co2g_kwh()

    assert result == co2_expected
    assert country.co2g_kwh_source == CarbonIntensitySource.ElectricityMapsAPI
    assert country.emission_factor_type == EmissionFactorType.LIFECYCLE
    assert country.carbon_intensity_metadata == CarbonIntensityMetadata(
        source=CarbonIntensitySource.ElectricityMapsAPI,
        co2g_kwh=co2_expected,
        zone="FR",
        datetime="2025-01-15T12:00:00.000Z",
        updated_at="2025-01-15T11:51:02.892Z",
        emission_factor_type=EmissionFactorType.LIFECYCLE,
        is_estimated=False,
        estimation_method=None,
        fallback_used=False,
    )
    parsed_url = urlparse(request.call_args.kwargs["url"])
    assert parsed_url.path == "/v4/carbon-intensity/latest"
    assert parse_qs(parsed_url.query) == {
        "emissionFactorType": ["lifecycle"],
        "zone": ["FR"],
    }


@pytest.mark.asyncio
async def test_electricity_maps_api_v4_direct(mocker):
    co2_expected = 42.0
    response = {
        "zone": "FR",
        "carbonIntensity": co2_expected,
        "datetime": "2025-01-15T12:00:00.000Z",
        "updatedAt": "2025-01-15T11:51:02.892Z",
        "createdAt": "2025-01-15T11:54:01.319Z",
        "emissionFactorType": "direct",
        "isEstimated": False,
        "estimationMethod": None,
    }
    request = mocker.patch.object(Country, "request", return_value=response)

    country = Country(
        name="FR",
        co2signal_api_key="API_KEY",
        co2signal_url="https://api.electricitymaps.com/v4/carbon-intensity/latest",
        co2g_kwh_source=CarbonIntensitySource.ElectricityMapsAPI,
        emission_factor_type=EmissionFactorType.DIRECT,
    )

    result = await country.get_latest_co2g_kwh()

    assert result == co2_expected
    assert country.emission_factor_type == EmissionFactorType.DIRECT
    assert parse_qs(urlparse(request.call_args.kwargs["url"]).query)["emissionFactorType"] == ["direct"]


@pytest.mark.asyncio
async def test_carbon_intensity_metadata_marks_api_fallback(mocker):
    co2_expected = 74.0
    mocker.patch.object(Country, "request", side_effect=RuntimeError("api failed"))
    country = Country(
        name="FR",
        co2signal_api_key="API_KEY",
        co2signal_url="https://api.electricitymaps.com/v4/carbon-intensity/latest",
        co2g_kwh=co2_expected,
        co2g_kwh_source=CarbonIntensitySource.ElectricityMapsAPI,
        emission_factor_type=EmissionFactorType.LIFECYCLE,
    )

    result = await country.get_latest_co2g_kwh()

    assert result == co2_expected
    assert country.carbon_intensity_metadata == CarbonIntensityMetadata(
        source=CarbonIntensitySource.ElectricityMapsAPI,
        co2g_kwh=co2_expected,
        zone="FR",
        emission_factor_type=EmissionFactorType.LIFECYCLE,
        fallback_used=True,
    )


@pytest.mark.asyncio
async def test_carbon_intensity_api_failure_without_fallback_raises(mocker):
    mocker.patch.object(Country, "request", side_effect=RuntimeError("api failed"))
    country = Country(
        name="FR",
        co2signal_api_key="API_KEY",
        co2signal_url="https://api.electricitymaps.com/v4/carbon-intensity/latest",
        co2g_kwh_source=CarbonIntensitySource.ElectricityMapsAPI,
    )

    with pytest.raises(RuntimeError, match="api failed"):
        await country.get_latest_co2g_kwh()


@pytest.mark.asyncio
async def test_electricity_maps_api_v4_data_center(mocker):
    co2_expected = 35.0
    request = mocker.patch.object(Country, "request", return_value={"carbonIntensity": co2_expected})

    country = Country(
        name="AWS(eu-west-1)",
        co2signal_api_key="API_KEY",
        co2signal_url="https://api.electricitymaps.com/v4/carbon-intensity/latest",
        co2g_kwh_source=CarbonIntensitySource.ElectricityMapsAPI,
        emission_factor_type=EmissionFactorType.LIFECYCLE,
        data_center_provider="aws",
        data_center_region="eu-west-1",
    )

    result = await country.get_latest_co2g_kwh()

    assert result == co2_expected
    assert parse_qs(urlparse(request.call_args.kwargs["url"]).query) == {
        "dataCenterProvider": ["aws"],
        "dataCenterRegion": ["eu-west-1"],
        "emissionFactorType": ["lifecycle"],
    }


def test_get_location_detects_electricity_maps_api():
    country = Country.get_location(
        co2signal_api_key="API_KEY",
        co2signal_url="https://api.electricitymaps.com/v4/carbon-intensity/latest",
        country_code_alpha_iso_2="FR",
        emission_factor_type="lifecycle",
    )

    assert country.co2g_kwh_source == CarbonIntensitySource.ElectricityMapsAPI
    assert country.emission_factor_type == EmissionFactorType.LIFECYCLE


def test_get_location_without_api_key_uses_eu_file(mocker):
    mocker.patch.object(CloudProviders, "auto_detect", return_value=None)

    country = Country.get_location(
        co2signal_api_key="",
        co2signal_url="https://api.electricitymaps.com/v4/carbon-intensity/latest",
        country_code_alpha_iso_2="FR",
    )

    assert country.name == "fr"
    assert country.co2g_kwh == 74.0
    assert country.co2g_kwh_source == CarbonIntensitySource.FILE


@pytest.mark.parametrize(
    ("cloud_provider", "data_center_provider", "country_name"),
    [
        (AWS(region_name="eu-west-1", instance_type="m5.large"), "aws", "AWS(eu-west-1)"),
        (GCP(region_name="europe-west1", instance_type="n2-standard-4"), "gcp", "GCP(europe-west1)"),
        (Azure(region_name="eastus", instance_type="Standard_D2s_v3"), "azure", "Azure(eastus)"),
    ],
)
def test_get_location_uses_electricity_maps_data_center_for_cloud(
    mocker,
    cloud_provider,
    data_center_provider,
    country_name,
):
    mocker.patch.object(
        CloudProviders,
        "auto_detect",
        return_value=cloud_provider,
    )

    country = Country.get_location(
        co2signal_api_key="API_KEY",
        co2signal_url="https://api.electricitymaps.com/v4/carbon-intensity/latest",
        emission_factor_type="lifecycle",
    )

    assert country.name == country_name
    assert country.co2g_kwh_source == CarbonIntensitySource.ElectricityMapsAPI
    assert country.data_center_provider == data_center_provider
    assert country.data_center_region == cloud_provider.region_name


def test_get_location_detects_co2signal_api():
    country = Country.get_location(
        co2signal_api_key="API_KEY",
        co2signal_url="https://api.co2signal.com/v1/latest?countryCode=",
        country_code_alpha_iso_2="FR",
    )

    assert country.co2g_kwh_source == CarbonIntensitySource.CO2SignalAPI
