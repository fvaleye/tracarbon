import asyncio

import pytest

from tracarbon import AMDRAPL
from tracarbon import RAPL
from tracarbon import EnergyConsumption
from tracarbon import EnergyCounter
from tracarbon import EnergyUsage
from tracarbon import GPUInfo
from tracarbon import LinuxEnergyConsumption
from tracarbon import TracarbonException
from tracarbon import UsageType
from tracarbon import WorkloadNotAttributable
from tracarbon import WorkloadTracker
from tracarbon import track
from tracarbon.exceptions import HardwareRAPLException
from tracarbon.hardwares import sensors
from tracarbon.hardwares.energy import EnergyZone
from tracarbon.locations.country import Country

FRANCE = Country(name="fr", co2g_kwh=74.0)
WATTS_HIGH_ENOUGH_THAT_A_MICROSECOND_READING_IS_NOT_TAKEN_FOR_A_RESTART = 100_000_000.0


class CountingEnergyConsumption(EnergyConsumption):
    """A sensor exposing cumulative counters, like Intel RAPL."""

    joules_per_read: float = 5.0
    first_reading_joules: float = 100.0
    wraps_at_joules: float = 1_000_000_000_000.0
    counts_at_most_watts: float | None = WATTS_HIGH_ENOUGH_THAT_A_MICROSECOND_READING_IS_NOT_TAKEN_FOR_A_RESTART
    reads: int = 0
    fails_after_reads: int | None = None

    async def can_measure_a_workload(self) -> bool:
        return True

    async def get_energy_usage(self) -> EnergyUsage:
        return EnergyUsage(host_energy_usage=0.0)

    async def get_energy_counter(self) -> EnergyCounter:
        if self.fails_after_reads is not None and self.reads >= self.fails_after_reads:
            raise HardwareRAPLException("The RAPL read encountered an issue.")
        joules = (self.first_reading_joules + self.reads * self.joules_per_read) % self.wraps_at_joules
        self.reads += 1
        return EnergyCounter(
            zones={
                "package": EnergyZone(
                    joules=joules,
                    wraps_at_joules=self.wraps_at_joules,
                    counts_at_most_watts=self.counts_at_most_watts,
                    usage_types=(UsageType.HOST,),
                ),
                "uncore": EnergyZone(
                    joules=joules / 2,
                    wraps_at_joules=self.wraps_at_joules,
                    counts_at_most_watts=self.counts_at_most_watts,
                    usage_types=(UsageType.GPU,),
                ),
            }
        )


class PowerOnlyEnergyConsumption(EnergyConsumption):
    """A sensor reporting power and no counter, like powermetrics or a cloud instance."""

    async def get_energy_usage(self) -> EnergyUsage:
        return EnergyUsage(host_energy_usage=43.96)


def track_a_workload(**data) -> "track":
    data.setdefault("energy_consumption", CountingEnergyConsumption())
    data.setdefault("location", FRANCE)
    with track(name="llm.generate", **data) as tracker:
        pass
    return tracker


def test_the_energy_of_a_block_is_the_difference_between_two_counter_readings():
    tracker = track_a_workload(energy_consumption=CountingEnergyConsumption(joules_per_read=5.0))

    usage = tracker.usage
    assert usage.joules == 5.0
    assert usage.joules_on(usage_type=UsageType.GPU) == 2.5
    assert usage.duration_in_seconds > 0


def test_a_counter_that_wrapped_during_the_block_still_measures_it():
    tracker = track_a_workload(
        energy_consumption=CountingEnergyConsumption(
            first_reading_joules=999_999_990.0,
            joules_per_read=20.0,
            wraps_at_joules=1_000_000_000.0,
        )
    )

    assert tracker.usage.joules == 20.0


def test_hardware_exposing_no_counter_refuses_to_measure_a_workload():
    with pytest.raises(WorkloadNotAttributable) as exception:
        track_a_workload(energy_consumption=PowerOnlyEnergyConsumption())

    assert "llm.generate" in exception.value.args[0]


@pytest.mark.asyncio
async def test_a_discrete_gpu_stops_linux_from_measuring_a_workload(mocker):
    mocker.patch.object(RAPL, "is_rapl_compatible", return_value=True)
    mocker.patch.object(sensors.shutil, "which", return_value="/usr/bin/nvidia-smi")

    assert await LinuxEnergyConsumption().can_measure_a_workload() is False


@pytest.mark.asyncio
async def test_a_discrete_gpu_reporting_no_power_still_stops_linux_from_measuring(mocker):
    mocker.patch.object(RAPL, "is_rapl_compatible", return_value=True)
    mocker.patch.object(sensors.shutil, "which", return_value="/usr/bin/nvidia-smi")
    mocker.patch.object(GPUInfo, "get_gpu_power_usage_or_none", return_value=None)

    assert await LinuxEnergyConsumption().can_measure_a_workload() is False


@pytest.mark.asyncio
async def test_an_amd_host_can_measure_a_workload_from_its_hwmon_counters(mocker):
    mocker.patch.object(RAPL, "is_rapl_compatible", return_value=False)
    mocker.patch.object(AMDRAPL, "is_amd_rapl_compatible", return_value=True)
    mocker.patch.object(sensors.shutil, "which", return_value=None)

    assert await LinuxEnergyConsumption().can_measure_a_workload() is True


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


def test_a_workload_the_hardware_could_not_measure_reports_nothing_rather_than_zero():
    tracker = track_a_workload(energy_consumption=CountingEnergyConsumption(fails_after_reads=1))

    usage = tracker.usage
    assert usage.joules is None
    assert usage.co2g is None
    assert "tracarbon.energy.host_joules" not in usage.otel_attributes
    assert "tracarbon.energy.host_co2eq_grams" not in usage.otel_attributes


def test_the_usage_is_exported_as_opentelemetry_span_attributes():
    tracker = track_a_workload(energy_consumption=CountingEnergyConsumption(joules_per_read=500.0), tokens=250)

    attributes = tracker.usage.otel_attributes
    assert attributes["tracarbon.energy.host_joules"] == 500.0
    assert attributes["tracarbon.energy.host_joules_per_token"] == 2.0
    assert attributes["tracarbon.energy.host_co2eq_grams"] == tracker.usage.co2g
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
        with track(name="llm.generate", energy_consumption=CountingEnergyConsumption(), location=unreachable_location):
            raise ValueError("the workload failed")


@pytest.mark.asyncio
async def test_the_sync_context_manager_refuses_a_running_event_loop_before_the_workload_runs():
    the_workload_ran = False

    with pytest.raises(TracarbonException, match="async with"):
        with track(name="llm.generate", energy_consumption=CountingEnergyConsumption(), location=FRANCE):
            the_workload_ran = True

    assert the_workload_ran is False


def test_a_teardown_that_fails_never_replaces_the_workload_exception(mocker):
    mocker.patch.object(WorkloadTracker, "stop", side_effect=RuntimeError("the telemetry failed"))

    with pytest.raises(ValueError, match="the workload failed"):
        with track(name="llm.generate", energy_consumption=CountingEnergyConsumption(), location=FRANCE):
            raise ValueError("the workload failed")


def test_stopping_a_workload_twice_reports_what_it_consumed_once():
    tracker = track(name="w", energy_consumption=CountingEnergyConsumption(), location=FRANCE)
    tracker.start()

    first = tracker.stop().joules
    second = tracker.stop().joules

    assert first == second


@pytest.mark.asyncio
async def test_stopping_from_inside_an_event_loop_says_how_to_stop():
    tracker = track(name="w", energy_consumption=CountingEnergyConsumption(), location=FRANCE)

    with pytest.raises(TracarbonException) as exception:
        tracker.stop()

    assert "astop" in exception.value.args[0]


def test_a_misspelled_argument_is_refused_rather_than_detected_around():
    with pytest.raises(TypeError):
        track(name="w", locaton=FRANCE)  # type: ignore[call-arg]


def test_where_this_machine_runs_is_found_once_however_many_workloads_are_tracked(mocker):
    get_location = mocker.patch.object(Country, "get_location", return_value=FRANCE)

    for _ in range(20):
        track(name="llm.generate", energy_consumption=CountingEnergyConsumption())

    assert get_location.call_count == 1


def test_a_workload_long_enough_for_a_counter_to_roll_twice_is_not_measured():
    a_zone_that_rolls_quickly = CountingEnergyConsumption(joules_per_read=1.0, wraps_at_joules=1.0)
    tracker = track(name="llm.generate", energy_consumption=a_zone_that_rolls_quickly, location=FRANCE)

    tracker.start()
    tracker._started_at -= 3600
    usage = tracker.stop()

    assert usage.joules is None


def test_a_misspelled_argument_is_refused_by_the_tracker_as_well():
    with pytest.raises(TypeError):
        WorkloadTracker(name="w", locaton=FRANCE)  # type: ignore[call-arg]
