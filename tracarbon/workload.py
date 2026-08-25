import asyncio
import datetime
from threading import Event
from threading import Thread
from types import TracebackType
from typing import Any
from typing import Dict
from typing import Type

from asyncer import asyncify
from loguru import logger
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import PrivateAttr
from pydantic import field_validator

from tracarbon.exceptions import TracarbonException
from tracarbon.exceptions import WorkloadNotAttributable
from tracarbon.hardwares import EnergyConsumption
from tracarbon.hardwares.energy import EnergyCounter
from tracarbon.hardwares.energy import EnergyUsageUnit
from tracarbon.hardwares.energy import MeasurementMethod
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


class WorkloadUsage(BaseModel):
    """
    The energy the host consumed while a workload ran, and the carbon that energy emitted.

    The sensors measure the machine, not the workload, so this is what the whole host drew
    during the window rather than a share the workload is responsible for. Two workloads
    measured over the same window each report the machine, so the numbers do not add up.
    """

    name: str
    measurement_method: MeasurementMethod = MeasurementMethod.SAMPLED
    duration_in_seconds: float = 0.0
    joules_by_usage_type: Dict[UsageType, float] = Field(default_factory=dict)
    co2g: float | None = None
    sample_count: int = 0
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
        Get the energy the workload consumed on one part of the hardware.

        :param usage_type: the type of hardware the energy was consumed on
        :return: the energy in joules, or None if the hardware does not report this type
        """
        return self.joules_by_usage_type.get(usage_type)

    @property
    def average_watts(self) -> float | None:
        """
        Get the average power the workload drew while it ran.

        :return: the average power in watts, or None if the workload has not been measured yet
        """
        if not self.duration_in_seconds or self.joules is None:
            return None
        return self.joules / self.duration_in_seconds

    @property
    def joules_per_token(self) -> float | None:
        """
        Get the energy the workload consumed for each token it generated.

        :return: the energy in joules per token, or None if no token count was given
        """
        if not self.tokens or self.joules is None:
            return None
        return self.joules / self.tokens

    @property
    def otel_attributes(self) -> Dict[str, Any]:
        """
        Get the usage as OpenTelemetry span attributes, to report it next to the gen_ai token counts.

        :return: the attributes to set on the span that ran the workload
        """
        attributes: Dict[str, Any] = {
            "tracarbon.energy.measurement_method": self.measurement_method.value,
            "tracarbon.energy.carbon_intensity_source": self.carbon_intensity_metadata.source.value,
        }
        measured = {
            "tracarbon.energy.joules": self.joules,
            "tracarbon.energy.co2eq_grams": self.co2g,
            "tracarbon.energy.joules_per_token": self.joules_per_token,
            "tracarbon.energy.carbon_intensity_g_kwh": self.carbon_intensity_metadata.co2g_kwh,
        }
        attributes.update({key: value for key, value in measured.items() if value is not None})
        return attributes


class WorkloadTracker(BaseModel):
    """
    Measure the energy and the carbon emissions of a block of code, instead of the whole host.

    Hardware that exposes cumulative energy counters is read once before the block and once after,
    which measures the block exactly. Hardware that only reports power is sampled while the block
    runs, which estimates it. Hardware that reports neither refuses to measure a workload at all.
    """

    energy_consumption: EnergyConsumption
    location: Location
    usage: WorkloadUsage
    interval_in_seconds: float = 1.0

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("interval_in_seconds")
    @classmethod
    def an_interval_of_zero_would_read_the_sensor_in_a_tight_loop(cls, interval_in_seconds: float) -> float:
        if interval_in_seconds <= 0:
            raise ValueError("interval_in_seconds must be greater than zero.")
        return interval_in_seconds

    _stop_sampling: Event = PrivateAttr(default_factory=Event)
    _sampling_thread: Thread | None = PrivateAttr(default=None)
    _start_time: datetime.datetime | None = PrivateAttr(default=None)
    _previous_sample_time: datetime.datetime | None = PrivateAttr(default=None)
    _start_counter: EnergyCounter | None = PrivateAttr(default=None)

    def __init__(self, name: str, tokens: int | None = None, **data: Any) -> None:
        if "energy_consumption" not in data:
            data["energy_consumption"] = EnergyConsumption.from_platform()
        if "location" not in data:
            data["location"] = Country.get_location()
        super().__init__(usage=WorkloadUsage(name=name, tokens=tokens), **data)

    def __enter__(self) -> "WorkloadTracker":
        self.start()
        return self

    def __exit__(
        self,
        exception_type: Type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.stop()

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

        :raises WorkloadNotAttributable: if the hardware reports an energy that no workload can be attributed to
        """
        asyncio.run(self._start_measurement())

    def stop(self, tokens: int | None = None) -> WorkloadUsage:
        """
        Stop measuring the workload, from code that runs no event loop, and report what it consumed.

        :param tokens: the number of tokens the workload generated, which is only known once it ran
        :return: the energy and the carbon emissions of the workload
        """
        asyncio.run(self._stop_without_masking_the_workload_exception(tokens=tokens))
        return self.usage

    async def astop(self, tokens: int | None = None) -> WorkloadUsage:
        """
        Stop measuring the workload from inside an event loop and report what it consumed.

        :param tokens: the number of tokens the workload generated, which is only known once it ran
        :return: the energy and the carbon emissions of the workload
        """
        await self._stop_without_masking_the_workload_exception(tokens=tokens)
        return self.usage

    async def _stop_without_masking_the_workload_exception(self, tokens: int | None = None) -> None:
        """
        A workload that raised must keep its own exception, so reporting its usage never raises on top of it.
        """
        try:
            await self._stop_measurement(tokens=tokens)
        except Exception as exception:
            logger.opt(exception=exception).warning(f"Could not report the usage of [{self.usage.name}]")

    async def _start_measurement(self) -> None:
        await self._read_the_sensor_once_so_it_reports_how_it_measures()
        self.usage.measurement_method = self.energy_consumption.measurement_method()
        if self.usage.measurement_method == MeasurementMethod.NOT_ATTRIBUTABLE:
            raise WorkloadNotAttributable(
                f"{type(self.energy_consumption).__name__} does not report an energy that a workload can be measured "
                f"from, so [{self.usage.name}] was not measured."
            )
        self._start_time = datetime.datetime.now()
        if self.usage.measurement_method == MeasurementMethod.COUNTER:
            self._start_counter = await self.energy_consumption.get_energy_counter()
            return
        self._previous_sample_time = self._start_time
        self._stop_sampling.clear()
        self._sampling_thread = Thread(target=self._sample_until_stopped, daemon=True)
        self._sampling_thread.start()

    async def _read_the_sensor_once_so_it_reports_how_it_measures(self) -> None:
        """
        Sensors that fall back between hardware interfaces only know which one they use once they ran.
        """
        try:
            await self.energy_consumption.get_energy_usage()
        except TracarbonException as exception:
            logger.opt(exception=exception).warning(f"The sensor of [{self.usage.name}] failed its first read")

    async def _stop_measurement(self, tokens: int | None = None) -> None:
        if tokens is not None:
            self.usage.tokens = tokens
        if self.usage.measurement_method == MeasurementMethod.COUNTER:
            await self._read_the_counters()
        else:
            await self._stop_sampling_the_power()
        if self._start_time:
            self.usage.duration_in_seconds = (datetime.datetime.now() - self._start_time).total_seconds()
        await self._report_the_carbon_emissions()

    async def _read_the_counters(self) -> None:
        end_counter = await self.energy_consumption.get_energy_counter()
        if self._start_counter:
            self.usage.joules_by_usage_type = end_counter.joules_since(previous=self._start_counter)

    async def _stop_sampling_the_power(self) -> None:
        self._stop_sampling.set()
        if self._sampling_thread:
            await asyncify(self._sampling_thread.join)()
            self._sampling_thread = None
        await self._sample()

    async def _report_the_carbon_emissions(self) -> None:
        if self.usage.joules is None:
            return
        co2g_per_kwh = await self.location.get_latest_co2g_kwh()
        self.usage.co2g = Power.co2g_from_watts_hour(
            watts_hour=Power.watt_hours_from_joules(joules=self.usage.joules),
            co2g_per_kwh=co2g_per_kwh,
        )
        self.usage.carbon_intensity_metadata = self.location.carbon_intensity_metadata.model_copy()

    def _sample_until_stopped(self) -> None:
        while not self._stop_sampling.wait(self.interval_in_seconds):
            asyncio.run(self._sample())

    async def _sample(self) -> None:
        """
        Add the energy the hardware consumed since the previous sample to the workload.
        """
        try:
            energy_usage = await self.energy_consumption.get_energy_usage()
        except TracarbonException as exception:
            logger.opt(exception=exception).warning(f"Skipped an energy sample of [{self.usage.name}]")
            return
        energy_usage.convert_unit(unit=EnergyUsageUnit.WATT)
        for usage_type in UsageType:
            watts = energy_usage.get_energy_usage_on_type(usage_type=usage_type)
            if watts is None:
                continue
            joules = Power.joules_from_watt_hours(
                watt_hours=Power.watts_to_watt_hours(
                    watts=watts,
                    previous_energy_measurement_time=self._previous_sample_time,
                )
            )
            self.usage.joules_by_usage_type[usage_type] = self.usage.joules_by_usage_type.get(usage_type, 0.0) + joules
        self._previous_sample_time = datetime.datetime.now()
        self.usage.sample_count += 1


def track(name: str, tokens: int | None = None, **data: Any) -> WorkloadTracker:
    """
    Measure the energy and the carbon emissions of a block of code.

    :param name: the name of the workload
    :param tokens: the number of tokens the workload generated, to report the energy per token
    :return: the workload tracker to use as a context manager
    """
    return WorkloadTracker(name=name, tokens=tokens, **data)
