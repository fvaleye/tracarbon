import asyncio
import os

import pytest

from tracarbon import CarbonEmission
from tracarbon import Country
from tracarbon import EnergyConsumption
from tracarbon import EnergyUsage
from tracarbon import EnergyUsageUnit
from tracarbon import TracarbonBuilder
from tracarbon import TracarbonConfiguration
from tracarbon._sampling import collection_samples
from tracarbon._sampling import sample_energy
from tracarbon.cli import build_tracarbon
from tracarbon.exporters import StdoutExporter
from tracarbon.general_metrics import CarbonEmissionGenerator
from tracarbon.general_metrics import EnergyConsumptionGenerator
from tracarbon.hardwares import UsageType
from tracarbon.hardwares.processes import Processes
from tracarbon.hardwares.processes import ProcessUsage


class CountingSensor(EnergyConsumption):
    reads: int = 0
    watts: float = 10.0

    async def get_energy_usage(self) -> EnergyUsage:
        self.reads += 1
        await asyncio.sleep(0)
        return EnergyUsage(
            host_energy_usage=self.watts,
            cpu_energy_usage=self.watts,
            interval_joules={UsageType.HOST: self.watts * 2, UsageType.CPU: self.watts * 2},
        )


def paired_exporter(sensor):
    location = Country(name="fr", co2g_kwh=100)
    return StdoutExporter(
        metric_generators=[
            EnergyConsumptionGenerator(location=location, energy_consumption=sensor),
            CarbonEmissionGenerator(
                location=location, carbon_emission=CarbonEmission(location=location, energy_consumption=sensor)
            ),
        ]
    )


async def test_shared_sensor_is_read_once_per_cycle_without_losing_counter_energy():
    sensor = CountingSensor()
    exporter = paired_exporter(sensor)

    for _ in range(3):
        await exporter._launch_all()

    assert sensor.reads == 3
    assert exporter.metric_report["energy_consumption_host"].total == pytest.approx(60 / 3600)
    assert exporter.metric_report["carbon_emission_host"].total == pytest.approx(60 / 3600 / 1000 * 100)

    for _ in range(2):
        assert [metric async for metric in exporter.metric_generators[0].generate()]
    assert sensor.reads == 5


async def test_mutating_one_sample_does_not_change_later_samples():
    sensor = CountingSensor()

    with collection_samples():
        reading = await sample_energy(sensor)
        reading.convert_unit(EnergyUsageUnit.MILLIWATT)
        reading.interval_joules.clear()
        other_reading = await sample_energy(sensor)

    assert sensor.reads == 1
    assert other_reading.unit == EnergyUsageUnit.WATT
    assert other_reading.host_energy_usage == 10
    assert other_reading.interval_joules == {UsageType.HOST: 20, UsageType.CPU: 20}


@pytest.mark.parametrize("use_cli", [True, False])
async def test_default_builders_share_hardware_and_process_reads(mocker, use_cli):
    sensors = []

    def create_sensor():
        sensor = CountingSensor()
        sensors.append(sensor)
        return sensor

    mocker.patch.object(EnergyConsumption, "from_platform", side_effect=create_sensor)
    mocker.patch.object(Country, "get_location", return_value=Country(name="fr", co2g_kwh=100))
    process_reads = mocker.patch.object(
        Processes, "get_processes_usage", return_value=[ProcessUsage(pid=os.getpid(), name="worker", cpu_usage=0.25)]
    )
    if use_cli:
        tracker = build_tracarbon("Stdout", TracarbonConfiguration(), country_code_alpha_iso_2="fr", pids=[os.getpid()])
    else:
        tracker = TracarbonBuilder(location=Country(name="fr", co2g_kwh=100)).with_processes().build()

    await tracker.exporter._launch_all()
    await tracker.exporter._launch_all()

    assert sum(sensor.reads for sensor in sensors) == 2
    assert process_reads.call_count == 2
    assert tracker.exporter.metric_report["energy_consumption_process_cpu"].total == pytest.approx(40 / 3600 * 0.25)
    assert tracker.exporter.metric_report["carbon_emission_process_cpu"].total == pytest.approx(
        40 / 3600 * 0.25 / 1000 * 100
    )


async def test_supplied_exporter_keeps_its_sensors_when_process_tracking_is_added(mocker):
    custom = CountingSensor(watts=50)
    default = CountingSensor()
    mocker.patch.object(EnergyConsumption, "from_platform", return_value=default)
    mocker.patch.object(Processes, "get_processes_usage", return_value=[])
    exporter = paired_exporter(custom)
    tracker = (
        TracarbonBuilder(location=Country(name="fr", co2g_kwh=100)).with_exporter(exporter).with_processes().build()
    )

    await tracker.exporter._launch_all()

    assert custom.reads == default.reads == 1
    assert tracker.exporter.metric_report["energy_consumption_host"].average == 50
