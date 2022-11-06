import pytest

from tracarbon import CarbonEmission, MacEnergyConsumption, Power
from tracarbon.locations import Country


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
