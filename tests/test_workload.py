import asyncio
import time

import pytest
from pydantic import ValidationError

from tracarbon import EnergyConsumption
from tracarbon import EnergyUsage
from tracarbon import GPUInfo
from tracarbon import LinuxEnergyConsumption
from tracarbon import UsageType
from tracarbon import WorkloadTracker
from tracarbon import track
from tracarbon.exceptions import HardwareNoGPUDetectedException
from tracarbon.exceptions import WorkloadNotAttributable
from tracarbon.hardwares.energy import EnergyCounter
from tracarbon.hardwares.energy import MeasurementMethod
from tracarbon.locations.country import Country

FRANCE = Country(name="fr", co2g_kwh=74.0)


class ConstantEnergyConsumption(EnergyConsumption):
    """A sensor that only reports power, like powermetrics on a Mac."""

    host_watts: float = 10.0
    gpu_watts: float | None = None

    async def get_energy_usage(self) -> EnergyUsage:
        return EnergyUsage(host_energy_usage=self.host_watts, gpu_energy_usage=self.gpu_watts)


class CountingEnergyConsumption(EnergyConsumption):
    """A sensor that exposes a cumulative energy counter, like Intel RAPL."""

    joules_per_read: float = 5.0
    first_reading_joules: float = 100.0
    wraps_at_joules: float = 1_000_000.0
    reads: int = 0

    def measurement_method(self) -> MeasurementMethod:
        return MeasurementMethod.COUNTER

    async def get_energy_usage(self) -> EnergyUsage:
        return EnergyUsage(host_energy_usage=0.0)

    async def get_energy_counter(self) -> EnergyCounter:
        joules = (self.first_reading_joules + self.reads * self.joules_per_read) % self.wraps_at_joules
        self.reads += 1
        return EnergyCounter(
            joules={UsageType.HOST: joules, UsageType.GPU: joules / 2},
            wraps_at_joules={UsageType.HOST: self.wraps_at_joules, UsageType.GPU: self.wraps_at_joules},
        )


class NotAttributableEnergyConsumption(EnergyConsumption):
    """A sensor whose reading does not follow what the machine computes, like ioreg AdapterPower."""

    def measurement_method(self) -> MeasurementMethod:
        return MeasurementMethod.NOT_ATTRIBUTABLE

    async def get_energy_usage(self) -> EnergyUsage:
        return EnergyUsage(host_energy_usage=43.96)


class FailingEnergyConsumption(EnergyConsumption):
    async def get_energy_usage(self) -> EnergyUsage:
        raise HardwareNoGPUDetectedException("powermetrics failed to run.")


def track_a_workload(duration_in_seconds: float = 0.2, **data) -> WorkloadTracker:
    data.setdefault("energy_consumption", ConstantEnergyConsumption())
    data.setdefault("location", FRANCE)
    data.setdefault("interval_in_seconds", 0.05)
    with track(name="llm.generate", **data) as tracker:
        time.sleep(duration_in_seconds)
    return tracker


def test_a_counter_measures_the_block_exactly_without_sampling_it():
    tracker = track_a_workload(energy_consumption=CountingEnergyConsumption(joules_per_read=5.0))

    usage = tracker.usage
    assert usage.measurement_method == MeasurementMethod.COUNTER
    assert usage.sample_count == 0
    assert usage.joules == 5.0
    assert usage.joules_on(usage_type=UsageType.GPU) == 2.5


def test_a_counter_that_wrapped_during_the_block_still_measures_it():
    tracker = track_a_workload(
        energy_consumption=CountingEnergyConsumption(
            first_reading_joules=990.0, joules_per_read=20.0, wraps_at_joules=1000.0
        )
    )

    assert tracker.usage.joules == 20.0


def test_the_energy_of_a_sampled_block_is_its_power_over_the_time_it_ran():
    tracker = track_a_workload(duration_in_seconds=0.2)

    usage = tracker.usage
    assert usage.measurement_method == MeasurementMethod.SAMPLED
    assert usage.sample_count > 1
    assert usage.duration_in_seconds == pytest.approx(0.2, abs=0.1)
    assert usage.average_watts == pytest.approx(10.0, rel=0.1)
    assert usage.joules == pytest.approx(10.0 * usage.duration_in_seconds, rel=0.1)


def test_a_sensor_that_does_not_follow_the_compute_refuses_to_measure_a_workload():
    with pytest.raises(WorkloadNotAttributable) as exception:
        track_a_workload(energy_consumption=NotAttributableEnergyConsumption())

    assert "llm.generate" in exception.value.args[0]


def test_the_carbon_emissions_of_a_block_use_the_carbon_intensity_of_the_location():
    tracker = track_a_workload(energy_consumption=CountingEnergyConsumption(joules_per_read=3600.0))

    usage = tracker.usage
    assert usage.co2g == pytest.approx(1.0 / 1000 * 74.0)
    assert usage.carbon_intensity_metadata.co2g_kwh == 74.0


def test_a_block_generating_tokens_reports_the_energy_it_spent_on_each():
    tracker = track_a_workload(energy_consumption=CountingEnergyConsumption(joules_per_read=500.0), tokens=250)

    assert tracker.usage.joules_per_token == 2.0


def test_a_block_without_tokens_has_no_energy_per_token():
    tracker = track_a_workload()

    assert tracker.usage.joules_per_token is None


def test_a_block_shorter_than_the_sampling_interval_is_still_measured():
    tracker = track_a_workload(duration_in_seconds=0.05, interval_in_seconds=60.0)

    usage = tracker.usage
    assert usage.sample_count == 1
    assert usage.joules > 0
    assert usage.average_watts == pytest.approx(10.0, rel=0.1)


def test_the_hardware_reporting_a_gpu_gets_its_own_energy():
    tracker = track_a_workload(energy_consumption=ConstantEnergyConsumption(host_watts=10.0, gpu_watts=4.0))

    usage = tracker.usage
    assert usage.joules_on(usage_type=UsageType.GPU) == pytest.approx(usage.joules * 4.0 / 10.0, rel=0.1)
    assert usage.joules_on(usage_type=UsageType.CPU) is None


def test_a_workload_the_sensor_could_not_measure_reports_nothing_rather_than_zero():
    tracker = track_a_workload(energy_consumption=FailingEnergyConsumption())

    usage = tracker.usage
    assert usage.sample_count == 0
    assert usage.joules is None
    assert usage.co2g is None
    assert usage.duration_in_seconds > 0
    assert "tracarbon.energy.joules" not in usage.otel_attributes
    assert "tracarbon.energy.co2eq_grams" not in usage.otel_attributes


def test_the_usage_is_exported_as_opentelemetry_span_attributes():
    tracker = track_a_workload(energy_consumption=CountingEnergyConsumption(joules_per_read=500.0), tokens=250)

    attributes = tracker.usage.otel_attributes
    assert attributes["tracarbon.energy.joules"] == 500.0
    assert attributes["tracarbon.energy.joules_per_token"] == 2.0
    assert attributes["tracarbon.energy.measurement_method"] == "counter"
    assert attributes["tracarbon.energy.co2eq_grams"] == tracker.usage.co2g
    assert attributes["tracarbon.energy.carbon_intensity_g_kwh"] == 74.0
    assert attributes["tracarbon.energy.carbon_intensity_source"] == "file"


@pytest.mark.asyncio
async def test_a_workload_is_measured_from_inside_a_running_event_loop():
    async with track(
        name="llm.generate", energy_consumption=CountingEnergyConsumption(joules_per_read=42.0), location=FRANCE
    ) as tracker:
        await asyncio.sleep(0.01)

    assert tracker.usage.joules == 42.0


@pytest.mark.asyncio
async def test_the_token_count_can_be_given_once_the_workload_produced_it():
    tracker = track(
        name="llm.generate", energy_consumption=CountingEnergyConsumption(joules_per_read=500.0), location=FRANCE
    )
    await tracker.__aenter__()

    usage = await tracker.astop(tokens=250)

    assert usage.joules_per_token == 2.0


def test_a_workload_that_raised_keeps_its_own_exception():
    unreachable_location = Country(name="fr", co2g_kwh=None)

    with pytest.raises(ValueError, match="the workload failed"):
        with track(name="llm.generate", energy_consumption=ConstantEnergyConsumption(), location=unreachable_location):
            raise ValueError("the workload failed")


def test_a_discrete_gpu_stops_linux_from_totalling_a_workload(mocker):
    mocker.patch.object(GPUInfo, "get_gpu_power_usage_or_none", return_value=120.0)

    assert LinuxEnergyConsumption().measurement_method() == MeasurementMethod.NOT_ATTRIBUTABLE


def test_an_interval_of_zero_is_refused():
    with pytest.raises(ValidationError):
        track(
            name="llm.generate", energy_consumption=ConstantEnergyConsumption(), location=FRANCE, interval_in_seconds=0
        )
