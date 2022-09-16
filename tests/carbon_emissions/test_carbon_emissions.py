import datetime

import pytest

from tracarbon import CarbonEmission, EnergyConsumption, MacEnergyConsumption
from tracarbon.locations import Country, Location


@pytest.mark.darwin
def test_carbon_emission_should_convert_watt_hours_to_co2g():
    co2g_per_kwh = 20.3
    watt_hours = 10.1
    carbon_emission = CarbonEmission(
        location=Country(co2g_per_kwh=co2g_per_kwh),
    )
    co2g_expected = 0.20503

    co2g = carbon_emission.co2g_from_watt_hours(
        watt_hours=watt_hours, co2g_per_kwh=co2g_per_kwh
    )

    assert co2g == co2g_expected


@pytest.mark.darwin
def test_carbon_emission_should_convert_watt_hours_to_co2g():
    wattage = 50
    co2g_per_kwh = 20.3
    watt_hours_expected = 0.833
    name_alpha_iso_2 = "fr"
    carbon_emission = CarbonEmission(
        location=Country(name=name_alpha_iso_2, co2g_kwh=co2g_per_kwh),
    )
    one_minute_ago = datetime.datetime.now() - datetime.timedelta(seconds=60)
    carbon_emission.previous_energy_consumption_time = one_minute_ago

    watt_hours = carbon_emission.wattage_to_watt_hours(wattage=wattage)

    assert round(watt_hours, 3) == watt_hours_expected


@pytest.mark.asyncio
@pytest.mark.darwin
async def test_carbon_emission_should_run_to_convert_watt_hours_to_co2g(mocker):
    co2g_per_kwh = 20.0
    co2_expected = 0.0003333333333333334
    name_alpha_iso_2 = "fr"
    mocker.patch.object(Country, "get_latest_co2g_kwh", return_value=co2g_per_kwh)
    mocker.patch.object(MacEnergyConsumption, "run", return_value=60.0)
    carbon_emission = CarbonEmission(
        location=Country(name=name_alpha_iso_2, co2g_kwh=co2g_per_kwh),
    )

    co2g = await carbon_emission.run()

    assert co2g == co2_expected
