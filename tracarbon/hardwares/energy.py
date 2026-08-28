from datetime import datetime
from enum import Enum
from typing import ClassVar
from typing import Dict
from typing import Tuple

from loguru import logger
from pydantic import BaseModel
from pydantic import Field

__all__ = [
    "EnergyUsageUnit",
    "UsageType",
    "EnergyUsage",
    "EnergyZone",
    "EnergyCounter",
    "Power",
]


class EnergyUsageUnit(Enum):
    """
    Energy usage unit.
    """

    WATT = "watts"
    MILLIWATT = "milliwatts"


class UsageType(Enum):
    """
    Usage type.
    """

    HOST = "host"
    CPU = "cpu"
    MEMORY = "memory"
    GPU = "gpu"


class EnergyZone(BaseModel):
    """
    One power zone of the hardware and the energy it has counted since it started.

    A zone rolls over on its own once it reaches the range it exposes, so a reading lower than
    the previous one means that zone wrapped rather than its energy dropping.
    """

    joules: float
    wraps_at_joules: float | None = None
    counts_at_most_watts: float | None = None
    averaged_over_seconds: float = 0.0
    usage_types: Tuple[UsageType, ...] = ()

    @property
    def seconds_before_it_can_wrap_twice(self) -> float | None:
        """
        Get how long this zone can count before it could have rolled over more than once.

        The stretch is the longest one over which the zone could not have drawn a whole range. A
        zone wrapping at a rate nothing bounds affords none of it, which is what the caller reads
        from a zone that says nothing about the power holding it.
        A zone saying nothing about the power it is held to cannot say this either, and is not
        measured at all. Guessing a ceiling instead would refuse a laptop a window it could have
        measured and let a large socket past one it could not.

        :return: the seconds it affords, or None where it never rolls over or does not say how fast
        """
        if not self.wraps_at_joules or not self.counts_at_most_watts:
            return None
        return max(0.0, self.wraps_at_joules / self.counts_at_most_watts - self.averaged_over_seconds)

    def drew_more_than_it_could_have(self, joules: float, seconds: float) -> bool:
        """
        Get whether a zone reports consuming more energy than it could have drawn.

        A counter that was restarted reads lower than it did before, exactly as one that wrapped
        does, and correcting a restart as though it were a wrap credits the zone a whole range it
        never consumed. What constrains it is what says the two apart, and what it constrains is an
        average over a window, so a stretch holds what the average allows across it and a further
        window's worth on top.

        :param joules: the energy the zone is taken to have consumed
        :param seconds: how long the window lasted
        :return: whether that much energy was beyond this zone in that time
        """
        if self.counts_at_most_watts is None:
            return False
        return joules > self.counts_at_most_watts * (seconds + self.averaged_over_seconds)

    def could_have_wrapped_twice_in(self, seconds: float) -> bool:
        """
        Get whether this zone could have rolled over more than once over a window.

        A window exactly as long as one roll lands on the reading it started from, which cannot be
        told from no energy at all, so that window is already too long.

        :param seconds: how long the window lasted
        :return: whether the energy of the window can still be told from two readings
        """
        if self.wraps_at_joules and not self.counts_at_most_watts:
            return True
        affords = self.seconds_before_it_can_wrap_twice
        return affords is not None and seconds >= affords


class EnergyCounter(BaseModel):
    """
    The energy every power zone of the hardware has counted, kept apart until it is measured.

    Zones wrap independently, so summing them before measuring a window would make one zone
    wrapping look like every zone did.
    """

    zones: Dict[str, EnergyZone] = Field(default_factory=dict)

    def joules_since(self, previous: "EnergyCounter", seconds: float) -> Dict[UsageType, float]:
        """
        Get the energy consumed since a previous reading of the same counters.

        A usage type is reported only when every zone counting towards it was measured. A zone the
        earlier reading did not have, one that went backwards with no range to correct it, and one
        that could have rolled over more than once all leave the types they cover unmeasured, so
        that a part of the machine is never handed back as though it were the whole of it.

        :param previous: the earlier reading to measure from
        :param seconds: how long the window lasted, which is what says whether a zone could have
            rolled over more than once, so a caller that does not know it cannot be told the energy
        :return: the energy consumed for each type both readings measured in full
        """
        consumed: Dict[UsageType, float] = dict()
        unmeasured: set[UsageType] = set()
        for name in self.zones.keys() | previous.zones.keys():
            zone = self.zones.get(name)
            previous_zone = previous.zones.get(name)
            if zone is None:
                unmeasured.update(previous.zones[name].usage_types)
                continue
            if previous_zone is None:
                unmeasured.update(zone.usage_types)
                continue
            joules = zone.joules
            if joules < previous_zone.joules:
                if not zone.wraps_at_joules:
                    logger.warning(f"The energy zone {name} went backwards and exposes no range to correct it.")
                    unmeasured.update(zone.usage_types)
                    continue
                joules = joules + zone.wraps_at_joules
            if zone.drew_more_than_it_could_have(joules=joules - previous_zone.joules, seconds=seconds):
                logger.warning(
                    f"The energy zone {name} reports consuming more in {seconds} seconds than what constrains "
                    f"it allows, so it did not simply wrap."
                )
                unmeasured.update(zone.usage_types)
                continue
            if zone.could_have_wrapped_twice_in(seconds=seconds):
                logger.warning(
                    f"The energy zone {name} could have wrapped more than once in {seconds} seconds, and it "
                    f"counts no wraps, so the energy it consumed cannot be told from two readings."
                )
                unmeasured.update(zone.usage_types)
                continue
            for usage_type in zone.usage_types:
                consumed[usage_type] = consumed.get(usage_type, 0.0) + (joules - previous_zone.joules)
        return {usage_type: joules for usage_type, joules in consumed.items() if usage_type not in unmeasured}


class EnergyUsage(BaseModel):
    """
    Energy report in watts.
    """

    host_energy_usage: float = 0.0
    cpu_energy_usage: float | None = None
    memory_energy_usage: float | None = None
    gpu_energy_usage: float | None = None
    unit: EnergyUsageUnit = EnergyUsageUnit.WATT

    def get_energy_usage_on_type(self, usage_type: UsageType) -> float | None:
        """
        Get the energy usage based on the type.

        :param: usage_type: the type of energy to return
        :return: the energy of the type
        """
        if usage_type == UsageType.CPU:
            return self.cpu_energy_usage
        elif usage_type == UsageType.GPU:
            return self.gpu_energy_usage
        elif usage_type == UsageType.HOST:
            return self.host_energy_usage
        elif usage_type == UsageType.MEMORY:
            return self.memory_energy_usage
        return None

    def convert_unit(self, unit: EnergyUsageUnit) -> None:
        """
        Convert the EnergyUsage values to the requested unit.

        :param unit: the target energy usage unit for the conversion
        """
        if self.unit == unit:
            return
        # Convert from milliwatts to watts
        if self.unit == EnergyUsageUnit.MILLIWATT and unit == EnergyUsageUnit.WATT:
            self.host_energy_usage = self.host_energy_usage / 1000
            self.cpu_energy_usage = self.cpu_energy_usage / 1000 if self.cpu_energy_usage is not None else None
            self.memory_energy_usage = self.memory_energy_usage / 1000 if self.memory_energy_usage is not None else None
            self.gpu_energy_usage = self.gpu_energy_usage / 1000 if self.gpu_energy_usage is not None else None
            self.unit = EnergyUsageUnit.WATT
        # Convert from watts to milliwatts
        elif self.unit == EnergyUsageUnit.WATT and unit == EnergyUsageUnit.MILLIWATT:
            self.host_energy_usage = self.host_energy_usage * 1000
            self.cpu_energy_usage = self.cpu_energy_usage * 1000 if self.cpu_energy_usage is not None else None
            self.memory_energy_usage = self.memory_energy_usage * 1000 if self.memory_energy_usage is not None else None
            self.gpu_energy_usage = self.gpu_energy_usage * 1000 if self.gpu_energy_usage is not None else None
            self.unit = EnergyUsageUnit.MILLIWATT


class Power(BaseModel):
    """Power utility"""

    MICROJOULES_TO_WATT_FACTOR: ClassVar[int] = 1000000
    WH_TO_KWH_FACTOR: ClassVar[int] = 1000
    SECONDS_TO_HOURS_FACTOR: ClassVar[int] = 3600

    @staticmethod
    def watts_to_watt_hours(watts: float, previous_energy_measurement_time: datetime | None = None) -> float:
        """
        Convert current watts to watt-hours W/h using the previous energy measurement.

        :param watts: the wattage in W
        :param previous_energy_measurement_time: the previous measurement time
        :return: watt-hours W/h
        """
        now = datetime.now()
        if previous_energy_measurement_time:
            time_difference_in_seconds = (now - previous_energy_measurement_time).total_seconds()
        else:
            time_difference_in_seconds = 1
        return watts * (time_difference_in_seconds / Power.SECONDS_TO_HOURS_FACTOR)

    @staticmethod
    def co2g_from_watts_hour(watts_hour: float, co2g_per_kwh: float) -> float:
        """
        Calculate the CO2g generated using watt-hours and the CO2g/kwh.

        :return: the CO2g generated by the energy consumption
        """
        return (watts_hour / Power.WH_TO_KWH_FACTOR) * co2g_per_kwh

    @staticmethod
    def joules_from_microjoules(uj: float) -> float:
        """
        Get joules from microjoules.

        :param uj: energy in microjoules
        :return: joules
        """
        return uj / Power.MICROJOULES_TO_WATT_FACTOR

    @staticmethod
    def watt_hours_from_joules(joules: float) -> float:
        """
        Get watt-hours from joules.

        :param joules: the energy in joules
        :return: watt-hours W/h
        """
        return joules / Power.SECONDS_TO_HOURS_FACTOR

    @staticmethod
    def watts_from_microwatts(uw: float) -> float:
        """
        Get watts from microwatts.

        :param uw: the power in microwatts
        :return: watts
        """
        return uw / Power.MICROJOULES_TO_WATT_FACTOR

    @staticmethod
    def watts_from_microjoules(
        uj: float,
    ) -> float:
        """
        Get watts from microjoules.

        :param: uj: energy in microjoules
        :return: watts
        """
        return uj / Power.MICROJOULES_TO_WATT_FACTOR
