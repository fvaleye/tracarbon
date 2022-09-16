import pytest

from tracarbon.locations import CarbonIntensitySource, Country


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
    assert country.co2g_kwh == 51.1
    assert country.co2g_kwh_source == CarbonIntensitySource.CO2SignalAPI


@pytest.mark.asyncio
async def test_france_location_should_return_taux_co2(mocker):
    co2_expected = 51.1
    co2signal_api_key = ""
    country = Country(co2signal_api_key=co2signal_api_key, name="fr", co2g_kwh=51.1)

    result = await country.get_latest_co2g_kwh()

    assert result == co2_expected
    assert country.name == "fr"
    assert country.co2g_kwh == co2_expected
    assert country.co2g_kwh_source == CarbonIntensitySource.FILE
