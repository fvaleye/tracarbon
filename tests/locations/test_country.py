import pytest

from tracarbon.locations import CarbonIntensitySource
from tracarbon.locations import Country
from tracarbon.locations.location import EmissionFactorType


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
async def test_electricity_maps_api_v3_lifecycle(mocker):
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
    mocker.patch.object(Country, "request", return_value=response)

    country = Country(
        name="FR",
        co2signal_api_key="API_KEY",
        co2signal_url="https://api.electricitymaps.com/v3/carbon-intensity/latest",
        co2g_kwh_source=CarbonIntensitySource.ElectricityMapsAPI,
        emission_factor_type=EmissionFactorType.LIFECYCLE,
    )

    result = await country.get_latest_co2g_kwh()

    assert result == co2_expected
    assert country.co2g_kwh_source == CarbonIntensitySource.ElectricityMapsAPI
    assert country.emission_factor_type == EmissionFactorType.LIFECYCLE


@pytest.mark.asyncio
async def test_electricity_maps_api_v3_direct(mocker):
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
    mocker.patch.object(Country, "request", return_value=response)

    country = Country(
        name="FR",
        co2signal_api_key="API_KEY",
        co2signal_url="https://api.electricitymaps.com/v3/carbon-intensity/latest",
        co2g_kwh_source=CarbonIntensitySource.ElectricityMapsAPI,
        emission_factor_type=EmissionFactorType.DIRECT,
    )

    result = await country.get_latest_co2g_kwh()

    assert result == co2_expected
    assert country.emission_factor_type == EmissionFactorType.DIRECT


def test_get_location_detects_electricity_maps_api():
    country = Country.get_location(
        co2signal_api_key="API_KEY",
        co2signal_url="https://api.electricitymaps.com/v3/carbon-intensity/latest",
        country_code_alpha_iso_2="FR",
        emission_factor_type="lifecycle",
    )

    assert country.co2g_kwh_source == CarbonIntensitySource.ElectricityMapsAPI
    assert country.emission_factor_type == EmissionFactorType.LIFECYCLE


def test_get_location_detects_co2signal_api():
    country = Country.get_location(
        co2signal_api_key="API_KEY",
        co2signal_url="https://api.co2signal.com/v1/latest?countryCode=",
        country_code_alpha_iso_2="FR",
    )

    assert country.co2g_kwh_source == CarbonIntensitySource.CO2SignalAPI
