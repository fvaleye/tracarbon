import pytest

from tracarbon.emissions import CarbonEmission
from tracarbon.exporters import Tag
from tracarbon.general_metrics import (
    CarbonEmissionGenerator,
    EnergyConsumptionGenerator,
    HardwareCPUUsageGenerator,
    HardwareMemoryUsageGenerator,
)
from tracarbon.locations.country import Country


def test_carbon_emission_metric(mocker):
    location_name = "fr"
    mocker.patch.object(Country, "get_current_country", return_value=location_name)
    location = Country(name=location_name, co2g_kwh=51.1)
    carbon_emission_generator = CarbonEmissionGenerator(location=location)
    carbon_emission_metric = next(carbon_emission_generator.generate())

    assert carbon_emission_metric.name == "carbon_emission"
    assert carbon_emission_metric.tags[1] == Tag(key="location", value=location_name)
    assert carbon_emission_metric.tags[2] == Tag(
        key="source", value=location.co2g_kwh_source.value
    )
    assert carbon_emission_metric.tags[3] == Tag(key="units", value="co2g/kwh")


def test_hardware_memory_usage_metric(mocker):
    location_name = "fr"
    mocker.patch.object(Country, "get_current_country", return_value=location_name)
    location = Country(name=location_name, co2g_kwh=51.1)
    hardware_memory_generator = HardwareMemoryUsageGenerator(location=location)
    hardware_memory_metric = next(hardware_memory_generator.generate())

    assert hardware_memory_metric.name == "hardware_memory_used"
    assert hardware_memory_metric.tags[1] == Tag(key="location", value=location_name)
    assert hardware_memory_metric.tags[2] == Tag(key="units", value="%")


def test_hardware_cpu_usage_metric(mocker):
    location_name = "fr"
    mocker.patch.object(Country, "get_current_country", return_value=location_name)
    location = Country(name=location_name, co2g_kwh=51.1)
    hardware_cpu_generator = HardwareCPUUsageGenerator(location=location)
    hardware_cpu_metric = next(hardware_cpu_generator.generate())

    assert hardware_cpu_metric.name == "hardware_cpu_used"
    assert hardware_cpu_metric.tags[1] == Tag(key="location", value=location_name)
    assert hardware_cpu_metric.tags[2] == Tag(key="units", value="%")


def test_energy_consumption_metric(mocker):
    location_name = "fr"
    mocker.patch.object(Country, "get_current_country", return_value=location_name)
    location = Country(name=location_name, co2g_kwh=51.1)
    energy_consumption_generator = EnergyConsumptionGenerator(location=location)
    energy_consumption_metric = next(energy_consumption_generator.generate())

    assert energy_consumption_metric.name == "energy_consumption"
    assert energy_consumption_metric.tags[1] == Tag(key="location", value=location_name)
    assert energy_consumption_metric.tags[2] == Tag(key="units", value="watts")
