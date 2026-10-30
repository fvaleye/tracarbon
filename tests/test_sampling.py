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


async def test_independently_supplied_sensors_keep_their_own_measurements():
    sensor = CountingSensor()
    other_sensor = CountingSensor(watts=30)
    exporter = paired_exporter(sensor)
    exporter.metric_generators[1].carbon_emission.energy_consumption = other_sensor

    await exporter._launch_all()

    assert sensor.reads == other_sensor.reads == 1
    assert exporter.metric_report["energy_consumption_host"].total == pytest.approx(20 / 3600)
    assert exporter.metric_report["carbon_emission_host"].total == pytest.approx(60 / 3600 / 1000 * 100)


async def test_collectors_do_not_share_a_cycle_even_when_the_sensor_is_shared():
    sensor = CountingSensor()
    first = paired_exporter(sensor)
    second = paired_exporter(sensor)

    await asyncio.gather(first._launch_all(), second._launch_all())

    assert sensor.reads == 2


async def test_unit_conversion_in_one_generator_does_not_change_the_shared_reading():
    class MilliwattGenerator(EnergyConsumptionGenerator):
        async def generate(self):
            async for metric in super().generate():
                if metric.name == "energy_consumption_host":
                    metric.name = "first_generator"
                    yield metric
                    return

    class MilliwattSensor(CountingSensor):
        async def get_energy_usage(self):
            reading = await super().get_energy_usage()
            reading.convert_unit(EnergyUsageUnit.MILLIWATT)
            return reading

    sensor = MilliwattSensor()
    exporter = paired_exporter(sensor)
    exporter.metric_generators.reverse()
    exporter.metric_generators.append(MilliwattGenerator(location=Country(name="fr"), energy_consumption=sensor))

    await exporter._launch_all()

    assert sensor.reads == 1
    assert exporter.metric_report["first_generator"].average == 10_000
    assert exporter.metric_report["first_generator"].total == pytest.approx(20 / 3600)
    assert exporter.metric_report["carbon_emission_host"].total == pytest.approx(20 / 3600 / 1000 * 100)


async def test_generator_called_outside_collection_gets_a_new_reading():
    sensor = CountingSensor()
    exporter = paired_exporter(sensor)
    await exporter._launch_all()

    for _ in range(2):
        assert [metric async for metric in exporter.metric_generators[0].generate()]

    assert sensor.reads == 3


@pytest.mark.parametrize("failure", [RuntimeError("export failed"), asyncio.CancelledError()])
async def test_failed_or_cancelled_collection_does_not_leave_a_cached_reading(failure):
    class FailingExporter(StdoutExporter):
        async def launch(self, metric_generator):
            await super().launch(metric_generator)
            raise failure

    sensor = CountingSensor()
    exporter = FailingExporter(metric_generators=paired_exporter(sensor).metric_generators[:1])
    with pytest.raises(type(failure)):
        await exporter._launch_all()

    assert [metric async for metric in exporter.metric_generators[0].generate()]
    assert sensor.reads == 2


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


def test_shared_sensor_opens_a_fresh_window_when_tracker_restarts(mocker):
    class WindowSensor(CountingSensor):
        opened: bool = False

        def reset(self):
            self.opened = False

        async def get_energy_usage(self):
            reading = await super().get_energy_usage()
            if not self.opened:
                reading.host_energy_usage = None
                reading.cpu_energy_usage = None
                reading.interval_joules = {}
                self.opened = True
            return reading

    sensor = WindowSensor()
    mocker.patch.object(EnergyConsumption, "from_platform", return_value=sensor)
    mocker.patch.object(Country, "get_location", return_value=Country(name="fr", co2g_kwh=100))
    tracker = build_tracarbon("Stdout", TracarbonConfiguration(interval_in_seconds=3600), "fr")

    for _ in range(2):
        with tracker:
            assert not tracker.exporter.metric_report
        assert tracker.report.metric_report["energy_consumption_host"].total == pytest.approx(20 / 3600)
        assert tracker.report.total_co2g == pytest.approx(20 / 3600 / 1000 * 100)
    assert sensor.reads == 4


async def test_nested_collection_restores_the_outer_snapshot():
    sensor = CountingSensor()
    nested = paired_exporter(sensor)

    class NestedExporter(StdoutExporter):
        async def launch(self, metric_generator):
            await super().launch(metric_generator)
            if isinstance(metric_generator, EnergyConsumptionGenerator):
                await nested._launch_all()

    outer = NestedExporter(metric_generators=paired_exporter(sensor).metric_generators)

    await outer._launch_all()

    assert sensor.reads == 2
    assert outer.metric_report["energy_consumption_host"].total == nested.metric_report["energy_consumption_host"].total


async def test_supplied_exporter_keeps_its_sensors_when_process_tracking_is_added(mocker):
    custom = CountingSensor(watts=50)
    default = CountingSensor()
    mocker.patch.object(EnergyConsumption, "from_platform", return_value=default)
    exporter = paired_exporter(custom)
    tracker = (
        TracarbonBuilder(location=Country(name="fr", co2g_kwh=100)).with_exporter(exporter).with_processes().build()
    )

    await tracker.exporter._launch_all()

    assert custom.reads == default.reads == 1
    assert tracker.exporter.metric_report["energy_consumption_host"].average == 50
