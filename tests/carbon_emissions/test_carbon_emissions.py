import pytest

from tracarbon import (
    CarbonEmission,
    CarbonUsage,
    CarbonUsageUnit,
    EnergyUsage,
    LinuxEnergyConsumption,
    MacEnergyConsumption,
    UsageType,
)
from tracarbon.locations import Country


@pytest.mark.asyncio
@pytest.mark.darwin
async def test_carbon_emission_should_run_to_convert_watt_hours_to_co2g_on_mac(mocker):
    co2g_per_kwh = 20.0
    carbon_usage = 0.0003333333333333334
    co2_expected = CarbonUsage(
        host_carbon_usage=carbon_usage,
        cpu_carbon_usage=carbon_usage,
        memory_carbon_usage=carbon_usage,
        gpu_carbon_usage=carbon_usage,
    )
    energy_usage = 60.0
    energy_usage = EnergyUsage(
        host_energy_usage=energy_usage,
        cpu_energy_usage=energy_usage,
        memory_energy_usage=energy_usage,
        gpu_energy_usage=energy_usage,
    )
    name_alpha_iso_2 = "fr"
    mocker.patch.object(Country, "get_latest_co2g_kwh", return_value=co2g_per_kwh)
    mocker.patch.object(
        MacEnergyConsumption, "get_energy_usage", return_value=energy_usage
    )
    carbon_emission = CarbonEmission(
        location=Country(name=name_alpha_iso_2, co2g_kwh=co2g_per_kwh),
    )

    co2g = await carbon_emission.get_co2_usage()

    assert co2g == co2_expected


@pytest.mark.asyncio
@pytest.mark.linux
async def test_carbon_emission_should_run_to_convert_watt_hours_to_co2g_on_linux(
    mocker,
):
    co2g_per_kwh = 20.0
    co2_expected = CarbonUsage(
        host_carbon_usage=0.0003333333333333334,
    )
    name_alpha_iso_2 = "fr"
    energy_usage = EnergyUsage(host_energy_usage=60.0)
    mocker.patch.object(Country, "get_latest_co2g_kwh", return_value=co2g_per_kwh)
    mocker.patch.object(
        LinuxEnergyConsumption, "get_energy_usage", return_value=energy_usage
    )
    carbon_emission = CarbonEmission(
        location=Country(name=name_alpha_iso_2, co2g_kwh=co2g_per_kwh),
    )

    co2g = await carbon_emission.get_co2_usage()

    assert co2g == co2_expected


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
    assert (
        carbon_usage.get_carbon_usage_on_type(UsageType.MEMORY) == memory_carbon_usage
    )
    assert carbon_usage.get_carbon_usage_on_type(UsageType.GPU) == gpu_carbon_usage
    assert carbon_usage.unit == CarbonUsageUnit.CO2_G

    carbon_usage.convert_unit(CarbonUsageUnit.CO2_MG)

    assert (
        carbon_usage.get_carbon_usage_on_type(UsageType.HOST)
        == host_carbon_usage * 1000
    )
    assert (
        carbon_usage.get_carbon_usage_on_type(UsageType.CPU) == cpu_carbon_usage * 1000
    )
    assert (
        carbon_usage.get_carbon_usage_on_type(UsageType.MEMORY)
        == memory_carbon_usage * 1000
    )
    assert (
        carbon_usage.get_carbon_usage_on_type(UsageType.GPU) == gpu_carbon_usage * 1000
    )
    assert carbon_usage.unit == CarbonUsageUnit.CO2_MG
