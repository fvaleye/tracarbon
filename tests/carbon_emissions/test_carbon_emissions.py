import asyncio
import datetime
import time
from unittest import mock

import pytest

from tracarbon import CarbonEmission
from tracarbon import CarbonUsage
from tracarbon import CarbonUsageUnit
from tracarbon import EnergyUsage
from tracarbon import LinuxEnergyConsumption
from tracarbon import MacEnergyConsumption
from tracarbon import UsageType
from tracarbon.emissions import carbon_emissions
from tracarbon.locations import CarbonIntensityMetadata
from tracarbon.locations import CarbonIntensitySource
from tracarbon.locations import Country


def one_minute_ago() -> datetime.datetime:
    return datetime.datetime.now() - datetime.timedelta(seconds=60)


@pytest.mark.asyncio
@pytest.mark.darwin
async def test_carbon_emission_should_run_to_convert_watt_hours_to_co2g_on_mac(mocker):
    co2g_per_kwh = 20.0
    carbon_usage_expected = 0.02
    energy_usage = 60.0
    energy_usage = EnergyUsage(
        host_energy_usage=energy_usage,
        cpu_energy_usage=energy_usage,
        memory_energy_usage=energy_usage,
        gpu_energy_usage=energy_usage,
    )
    name_alpha_iso_2 = "fr"
    mocker.patch.object(Country, "get_latest_co2g_kwh", return_value=co2g_per_kwh)
    mocker.patch.object(MacEnergyConsumption, "get_energy_usage", return_value=energy_usage)
    carbon_emission = CarbonEmission(
        location=Country(name=name_alpha_iso_2, co2g_kwh=co2g_per_kwh),
        previous_energy_consumption_time=one_minute_ago(),
    )

    co2g = await carbon_emission.get_co2_usage()

    assert round(co2g.host_carbon_usage, 3) == carbon_usage_expected
    assert round(co2g.cpu_carbon_usage, 3) == carbon_usage_expected
    assert round(co2g.memory_carbon_usage, 3) == carbon_usage_expected
    assert round(co2g.gpu_carbon_usage, 3) == carbon_usage_expected


@pytest.mark.asyncio
@pytest.mark.darwin
async def test_carbon_emission_should_report_nothing_on_the_first_measurement(mocker):
    co2g_per_kwh = 20.0
    energy_usage = EnergyUsage(host_energy_usage=60.0, cpu_energy_usage=60.0)
    mocker.patch.object(Country, "get_latest_co2g_kwh", return_value=co2g_per_kwh)
    mocker.patch.object(MacEnergyConsumption, "get_energy_usage", return_value=energy_usage)
    carbon_emission = CarbonEmission(location=Country(name="fr", co2g_kwh=co2g_per_kwh))

    co2g = await carbon_emission.get_co2_usage()

    assert co2g.host_carbon_usage == 0.0
    assert co2g.cpu_carbon_usage is None


@pytest.mark.asyncio
@pytest.mark.linux
async def test_carbon_emission_should_run_to_convert_watt_hours_to_co2g_on_linux(
    mocker,
):
    co2g_per_kwh = 20.0
    carbon_usage_expected = 0.02
    name_alpha_iso_2 = "fr"
    energy_usage = EnergyUsage(host_energy_usage=60.0)
    mocker.patch.object(Country, "get_latest_co2g_kwh", return_value=co2g_per_kwh)
    mocker.patch.object(LinuxEnergyConsumption, "get_energy_usage", return_value=energy_usage)
    carbon_emission = CarbonEmission(
        location=Country(name=name_alpha_iso_2, co2g_kwh=co2g_per_kwh),
        previous_energy_consumption_time=one_minute_ago(),
    )

    co2g = await carbon_emission.get_co2_usage()

    assert round(co2g.host_carbon_usage, 3) == carbon_usage_expected


@pytest.mark.asyncio
@pytest.mark.darwin
async def test_carbon_emission_measures_a_window_a_clock_correction_cannot_reverse(mocker):
    co2g_per_kwh = 74.0
    mocker.patch.object(Country, "get_latest_co2g_kwh", return_value=co2g_per_kwh)
    mocker.patch.object(MacEnergyConsumption, "get_energy_usage", return_value=EnergyUsage(host_energy_usage=60.0))
    carbon_emission = CarbonEmission(location=Country(name="fr", co2g_kwh=co2g_per_kwh))
    await carbon_emission.get_co2_usage()
    carbon_emission._measured_at = time.monotonic() - 60

    class SteppedBackwards(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.datetime.now() - datetime.timedelta(minutes=1)

    with mock.patch.object(carbon_emissions, "datetime", SteppedBackwards):
        co2g = await carbon_emission.get_co2_usage()

    # 60 W over a minute is a watt-hour, whichever way the wall clock moved in between.
    assert round(co2g.host_carbon_usage, 3) == 0.074


@pytest.mark.asyncio
@pytest.mark.darwin
async def test_carbon_emission_measures_the_window_between_the_readings(mocker):
    co2g_per_kwh = 74.0
    seconds_the_lookup_takes = 5.0

    async def a_slow_carbon_intensity_lookup() -> float:
        await asyncio.sleep(seconds_the_lookup_takes)
        return co2g_per_kwh

    mocker.patch.object(Country, "get_latest_co2g_kwh", side_effect=a_slow_carbon_intensity_lookup)
    mocker.patch.object(MacEnergyConsumption, "get_energy_usage", return_value=EnergyUsage(host_energy_usage=60.0))
    carbon_emission = CarbonEmission(location=Country(name="fr", co2g_kwh=co2g_per_kwh))
    await carbon_emission.get_co2_usage()
    carbon_emission._measured_at = time.monotonic() - 60

    co2g = await carbon_emission.get_co2_usage()

    # The window runs from one reading of the hardware to the next. Closing it after the lookup
    # instead would hand back the 60 W of a 55 second window, 0.068 g.
    assert round(co2g.host_carbon_usage, 3) == 0.074


def test_carbon_usage_with_type_and_conversion():
    host_carbon_usage = 12.4
    cpu_carbon_usage = 8.4
    memory_carbon_usage = 3
    gpu_carbon_usage = 1

    carbon_usage = CarbonUsage(
        host_carbon_usage=host_carbon_usage,
        cpu_carbon_usage=cpu_carbon_usage,
        memory_carbon_usage=memory_carbon_usage,
        gpu_carbon_usage=gpu_carbon_usage,
    )

    assert carbon_usage.get_carbon_usage_on_type(UsageType.HOST) == host_carbon_usage
    assert carbon_usage.get_carbon_usage_on_type(UsageType.CPU) == cpu_carbon_usage
    assert carbon_usage.get_carbon_usage_on_type(UsageType.MEMORY) == memory_carbon_usage
    assert carbon_usage.get_carbon_usage_on_type(UsageType.GPU) == gpu_carbon_usage
    assert carbon_usage.unit == CarbonUsageUnit.CO2_G

    carbon_usage.convert_unit(CarbonUsageUnit.CO2_MG)

    assert carbon_usage.get_carbon_usage_on_type(UsageType.HOST) == host_carbon_usage * 1000
    assert carbon_usage.get_carbon_usage_on_type(UsageType.CPU) == cpu_carbon_usage * 1000
    assert carbon_usage.get_carbon_usage_on_type(UsageType.MEMORY) == memory_carbon_usage * 1000
    assert carbon_usage.get_carbon_usage_on_type(UsageType.GPU) == gpu_carbon_usage * 1000
    assert carbon_usage.unit == CarbonUsageUnit.CO2_MG


@pytest.mark.asyncio
@pytest.mark.darwin
async def test_carbon_usage_includes_carbon_intensity_metadata(mocker):
    co2g_per_kwh = 20.0
    country = Country(name="fr", co2g_kwh=co2g_per_kwh)
    mocker.patch.object(
        MacEnergyConsumption,
        "get_energy_usage",
        return_value=EnergyUsage(host_energy_usage=60.0),
    )
    carbon_emission = CarbonEmission(location=country)

    carbon_usage = await carbon_emission.get_co2_usage()

    assert carbon_usage.carbon_intensity_metadata == CarbonIntensityMetadata(
        source=CarbonIntensitySource.FILE,
        co2g_kwh=co2g_per_kwh,
        zone="fr",
    )
