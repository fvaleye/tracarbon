import asyncio
import functools
import threading
import time
from types import TracebackType
from typing import Any
from typing import Coroutine
from typing import Dict
from typing import Type

from loguru import logger
from pydantic import BaseModel
from pydantic import Field
from pydantic import PrivateAttr

from tracarbon.exceptions import TracarbonException
from tracarbon.exceptions import WorkloadNotAttributable
from tracarbon.hardwares import EnergyConsumption
from tracarbon.hardwares.energy import EnergyCounter
from tracarbon.hardwares.energy import Power
from tracarbon.hardwares.energy import UsageType
from tracarbon.locations import CarbonIntensityMetadata
from tracarbon.locations import Country
from tracarbon.locations import Location

__all__ = [
    "WorkloadUsage",
    "WorkloadTracker",
    "track",
]


@functools.lru_cache(maxsize=1)
def _the_location_this_machine_runs_in() -> Location:
    """
    Get where this machine runs, once, since finding out reaches the network.

    :return: the location of this machine
    """
    return Country.get_location()


@functools.lru_cache(maxsize=1)
def _the_energy_consumption_of_this_machine() -> EnergyConsumption:
    """
    Get the sensor of this machine, once, since finding it reaches the cloud metadata services.

    :return: the energy consumption sensor of this machine
    """
    return EnergyConsumption.from_platform()


_the_loop_of_this_thread = threading.local()


def _run(measuring: "Coroutine[Any, Any, None]") -> None:
    """
    Run a measurement on a loop that outlives it.

    Running each one on a loop of its own and closing it takes the timers registered on it away,
    and the carbon intensity of a location expires on one of those, so it would be fetched once
    and then held for as long as the process lives.

    :param measuring: the measurement to run
    """
    loop = getattr(_the_loop_of_this_thread, "loop", None)
    if loop is None or loop.is_closed():
        loop = _the_loop_of_this_thread.loop = asyncio.new_event_loop()
    loop.run_until_complete(measuring)


def _an_event_loop_is_already_running() -> bool:
    """
    Get whether the caller runs inside an event loop, where a loop of our own cannot be started.

    :return: whether an event loop is already running
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


class WorkloadUsage(BaseModel):
    """
    The energy the host consumed while a workload ran, and the carbon that energy emitted.

    The counters measure the machine, not the process, so this is what the whole host consumed
    during the window rather than a share the workload is responsible for. Two workloads measured
    over the same window each report the machine, so the numbers do not add up.
    """

    name: str
    duration_in_seconds: float = 0.0
    joules_by_usage_type: Dict[UsageType, float] = Field(default_factory=dict)
    co2g: float | None = None
    tokens: int | None = None
    carbon_intensity_metadata: CarbonIntensityMetadata = Field(default_factory=CarbonIntensityMetadata)

    @property
    def joules(self) -> float | None:
        """
        Get the energy the host consumed while the workload ran.

        :return: the energy in joules, or None if the hardware reported none
        """
        return self.joules_by_usage_type.get(UsageType.HOST)

    def joules_on(self, usage_type: UsageType) -> float | None:
        """
        Get the energy consumed on one part of the hardware.

        :param usage_type: the type of hardware the energy was consumed on
        :return: the energy in joules, or None if the hardware does not report this type
        """
        return self.joules_by_usage_type.get(usage_type)

    @property
    def average_watts(self) -> float | None:
        """
        Get the average power the host drew while the workload ran.

        :return: the average power in watts, or None if nothing was measured
        """
        if not self.duration_in_seconds or self.joules is None:
            return None
        return self.joules / self.duration_in_seconds

    @property
    def joules_per_token(self) -> float | None:
        """
        Get the energy the host consumed for each token the workload generated.

        :return: the energy in joules per token, or None if no token count was given
        """
        if not self.tokens or self.joules is None:
            return None
        return self.joules / self.tokens

    @property
    def otel_attributes(self) -> Dict[str, Any]:
        """
        Get the usage as OpenTelemetry span attributes, to report it next to the gen_ai token counts.

        What the hardware did not report is left out rather than sent as a zero.

        :return: the attributes to set on the span that ran the workload
        """
        attributes: Dict[str, Any] = {
            "tracarbon.energy.carbon_intensity_source": self.carbon_intensity_metadata.source.value,
        }
        measured = {
            "tracarbon.energy.host_joules": self.joules,
            "tracarbon.energy.host_co2eq_grams": self.co2g,
            "tracarbon.energy.host_joules_per_token": self.joules_per_token,
            "tracarbon.energy.carbon_intensity_g_kwh": self.carbon_intensity_metadata.co2g_kwh,
        }
        attributes.update({key: value for key, value in measured.items() if value is not None})
        return attributes


class WorkloadTracker(BaseModel):
    """
    Measure what the host consumed while a block of code ran, instead of while the exporter runs.

    The cumulative energy counters of the hardware are read once before the block and once after,
    so the energy is a subtraction rather than an estimate. Hardware exposing no counter refuses
    to measure a workload at all.
    """

    energy_consumption: EnergyConsumption
    location: Location
    usage: WorkloadUsage

    _started_at: float | None = PrivateAttr(default=None)
    _measured: bool = PrivateAttr(default=False)
    _start_counter: EnergyCounter | None = PrivateAttr(default=None)

    def __init__(
        self,
        name: str,
        *,
        tokens: int | None = None,
        energy_consumption: EnergyConsumption | None = None,
        location: Location | None = None,
    ) -> None:
        super().__init__(
            usage=WorkloadUsage(name=name, tokens=tokens),
            energy_consumption=(
                energy_consumption if energy_consumption is not None else _the_energy_consumption_of_this_machine()
            ),
            location=location if location is not None else _the_location_this_machine_runs_in(),
        )

    def __enter__(self) -> "WorkloadTracker":
        self.start()
        return self

    def __exit__(
        self,
        exception_type: Type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            self.stop()
        except Exception as reporting_failure:
            logger.opt(exception=reporting_failure).warning(f"Could not report the usage of [{self.usage.name}]")

    async def __aenter__(self) -> "WorkloadTracker":
        await self._start_measurement()
        return self

    async def __aexit__(
        self,
        exception_type: Type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self._stop_without_masking_the_workload_exception()

    def start(self) -> None:
        """
        Start measuring the workload, from code that runs no event loop.

        :raises TracarbonException: if an event loop is already running, where `async with` is the way in
        :raises WorkloadNotAttributable: if the hardware exposes no energy counter to measure it with
        """
        if _an_event_loop_is_already_running():
            raise TracarbonException(
                f"An event loop is already running, so [{self.usage.name}] has to be measured with `async with`."
            )
        _run(self._start_measurement())

    def stop(self, tokens: int | None = None) -> WorkloadUsage:
        """
        Stop measuring the workload, from code that runs no event loop, and report what it consumed.

        :param tokens: the number of tokens the workload generated, which is only known once it ran
        :raises TracarbonException: if an event loop is already running, where `astop` is the way out
        :return: the energy and the carbon emissions of the workload
        """
        if _an_event_loop_is_already_running():
            raise TracarbonException(
                f"An event loop is already running, so [{self.usage.name}] has to be stopped with `astop`."
            )
        _run(self._stop_without_masking_the_workload_exception(tokens=tokens))
        return self.usage

    async def astop(self, tokens: int | None = None) -> WorkloadUsage:
        """
        Stop measuring the workload from inside an event loop and report what it consumed.

        :param tokens: the number of tokens the workload generated, which is only known once it ran
        :return: the energy and the carbon emissions of the workload
        """
        await self._stop_without_masking_the_workload_exception(tokens=tokens)
        return self.usage

    async def _start_measurement(self) -> None:
        if not await self.energy_consumption.can_measure_a_workload():
            raise WorkloadNotAttributable(
                f"{type(self.energy_consumption).__name__} exposes no energy counter a workload can be measured "
                f"from, so [{self.usage.name}] was not measured."
            )
        self._start_counter = await self.energy_consumption.get_energy_counter()
        self._started_at = time.monotonic()
        self._measured = False

    async def _stop_without_masking_the_workload_exception(self, tokens: int | None = None) -> None:
        """
        A workload that raised must keep its own exception, so reporting its usage never raises on top of it.
        """
        try:
            await self._stop_measurement(tokens=tokens)
        except Exception as exception:
            logger.opt(exception=exception).warning(f"Could not report the usage of [{self.usage.name}]")

    async def _stop_measurement(self, tokens: int | None = None) -> None:
        if tokens is not None:
            self.usage.tokens = tokens
        if self._start_counter is None or self._started_at is None:
            if self._measured:
                logger.debug(f"[{self.usage.name}] was already measured, so it is reported as it was.")
            else:
                logger.warning(f"[{self.usage.name}] was never started, so there is nothing to report.")
            return
        try:
            end_counter = await self.energy_consumption.get_energy_counter()
            seconds = time.monotonic() - self._started_at
            self.usage.joules_by_usage_type = end_counter.joules_since(previous=self._start_counter, seconds=seconds)
            self.usage.duration_in_seconds = seconds
        finally:
            self._measured = True
            self._start_counter = None
            self._started_at = None
        await self._report_the_carbon_emissions()

    async def _report_the_carbon_emissions(self) -> None:
        if self.usage.joules is None:
            return
        co2g_per_kwh = await self.location.get_latest_co2g_kwh()
        self.usage.co2g = Power.co2g_from_watts_hour(
            watts_hour=Power.watt_hours_from_joules(joules=self.usage.joules),
            co2g_per_kwh=co2g_per_kwh,
        )
        self.usage.carbon_intensity_metadata = self.location.carbon_intensity_metadata.model_copy()


def track(
    name: str,
    *,
    tokens: int | None = None,
    energy_consumption: EnergyConsumption | None = None,
    location: Location | None = None,
) -> WorkloadTracker:
    """
    Measure what the host consumed while a block of code ran.

    :param name: the name of the workload
    :param tokens: the number of tokens the workload generated, to report the energy per token
    :param energy_consumption: the sensor to measure with, defaulting to the one of this machine
    :param location: where this machine runs, defaulting to the one it is detected to run in
    :return: the workload tracker to use as a context manager
    """
    return WorkloadTracker(name=name, tokens=tokens, energy_consumption=energy_consumption, location=location)
