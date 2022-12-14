import pytest

from tracarbon.emissions import CarbonEmission
from tracarbon.exporters import Tag
from tracarbon.general_metrics import (
    CarbonEmissionMetric,
    EnergyConsumptionMetric,
    HardwareCPUUsageMetric,
    HardwareMemoryUsageMetric,
)
from tracarbon.locations.country import Country


def test_carbon_emission_metric(mocker):
    location_name = "fr"
    mocker.patch.object(Country, "get_current_country", return_value=location_name)
    location = Country(name=location_name, co2g_kwh=51.1)
    carbon_emission_metric = CarbonEmissionMetric(location=location)

    assert carbon_emission_metric.platform is not None
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
    carbon_emission_metric = HardwareMemoryUsageMetric(location=location)

    assert carbon_emission_metric.platform is not None
    assert carbon_emission_metric.name == "hardware_memory_used"
    assert carbon_emission_metric.tags[1] == Tag(key="location", value=location_name)
    assert carbon_emission_metric.tags[2] == Tag(key="units", value="%")


def test_hardware_cpu_usage_metric(mocker):
    location_name = "fr"
    mocker.patch.object(Country, "get_current_country", return_value=location_name)
    location = Country(name=location_name, co2g_kwh=51.1)
    carbon_emission_metric = HardwareCPUUsageMetric(location=location)

    assert carbon_emission_metric.platform is not None
    assert carbon_emission_metric.name == "hardware_cpu_used"
    assert carbon_emission_metric.tags[1] == Tag(key="location", value=location_name)
    assert carbon_emission_metric.tags[2] == Tag(key="units", value="%")


def test_energy_consumption_metric(mocker):
    location_name = "fr"
    mocker.patch.object(Country, "get_current_country", return_value=location_name)
    location = Country(name=location_name, co2g_kwh=51.1)
    carbon_emission_metric = EnergyConsumptionMetric(location=location)

    assert carbon_emission_metric.platform is not None
    assert carbon_emission_metric.name == "energy_consumption"
    assert carbon_emission_metric.tags[1] == Tag(key="location", value=location_name)
    assert carbon_emission_metric.tags[2] == Tag(key="units", value="watts")
