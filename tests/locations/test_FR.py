import pytest

from tracarbon.locations import France


@pytest.mark.asyncio
async def test_france_location_should_return_latest_known(mocker):
    co2_expected = 51.1
    response = {"records": [{"fields": {}}]}
    mocker.patch.object(France, "request", return_value=response)

    france = France(name_alpha_iso_2="fr", co2g_kwh=co2_expected)

    result = await france.get_latest_co2g_kwh(today_date=None, hour=None)

    assert result == co2_expected
    assert france.name == "fr"
    assert france.co2g_kwh == 51.1
    assert france.co2g_kwh_source == "API"


@pytest.mark.asyncio
async def test_france_location_should_return_taux_co2(mocker):
    co2_expected = 70.0
    response = {"records": [{"fields": {"taux_co2": co2_expected}}]}
    mocker.patch.object(France, "request", return_value=response)

    france = France(name_alpha_iso_2="fr", co2g_kwh=51.1)

    result = await france.get_latest_co2g_kwh(today_date=None, hour=None)

    assert result == co2_expected
    assert france.name == "fr"
    assert france.co2g_kwh == 70.0
    assert france.co2g_kwh_source == "API"
