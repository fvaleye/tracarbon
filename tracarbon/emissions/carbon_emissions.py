import time
from datetime import datetime
from enum import Enum
from typing import Any

from loguru import logger
from pydantic import BaseModel
from pydantic import Field
from pydantic import PrivateAttr

from tracarbon.hardwares import EnergyConsumption
from tracarbon.hardwares import Power
from tracarbon.hardwares import Sensor
from tracarbon.hardwares.energy import EnergyUsage
from tracarbon.hardwares.energy import EnergyUsageUnit
from tracarbon.hardwares.energy import UsageType
from tracarbon.locations import CarbonIntensityMetadata
from tracarbon.locations import Country
from tracarbon.locations import Location


class CarbonUsageUnit(Enum):
    """
    Carbon usage unit.
    """

    CO2_G = "co2g"
    CO2_MG = "co2mg"


class CarbonUsage(BaseModel):
    """
    Carbon Usage of the different types.
    """

    host_carbon_usage: float = 0.0
    cpu_carbon_usage: float | None = None
    memory_carbon_usage: float | None = None
    gpu_carbon_usage: float | None = None
    unit: CarbonUsageUnit = CarbonUsageUnit.CO2_G
    carbon_intensity_metadata: CarbonIntensityMetadata = Field(default_factory=CarbonIntensityMetadata)

    def get_carbon_usage_on_type(self, usage_type: UsageType) -> float | None:
        """
        Get the carbon usage based on the type.

        :param: usage_type: the type of energy to return
        :return: the carbon of the type
        """
        if usage_type == UsageType.CPU:
            return self.cpu_carbon_usage
        elif usage_type == UsageType.GPU:
            return self.gpu_carbon_usage
        elif usage_type == UsageType.HOST:
            return self.host_carbon_usage
        elif usage_type == UsageType.MEMORY:
            return self.memory_carbon_usage
        return None

    def convert_unit(self, unit: CarbonUsageUnit) -> None:
        """
        Convert the carbon usage with the right carbon usage type.

        :param: unit: the carbon usage unit for the conversion
        """
        if self.unit != unit:
            if unit == CarbonUsageUnit.CO2_G and self.unit == CarbonUsageUnit.CO2_MG:
                self.host_carbon_usage = self.host_carbon_usage / 1000
                self.cpu_carbon_usage = self.cpu_carbon_usage / 1000 if self.cpu_carbon_usage else None
                self.memory_carbon_usage = self.memory_carbon_usage / 1000 if self.memory_carbon_usage else None
                self.gpu_carbon_usage = self.gpu_carbon_usage / 1000 if self.gpu_carbon_usage else None
                self.unit = CarbonUsageUnit.CO2_G
            elif unit == CarbonUsageUnit.CO2_MG and self.unit == CarbonUsageUnit.CO2_G:
                self.host_carbon_usage = self.host_carbon_usage * 1000
                self.cpu_carbon_usage = self.cpu_carbon_usage * 1000 if self.cpu_carbon_usage else None
                self.memory_carbon_usage = self.memory_carbon_usage * 1000 if self.memory_carbon_usage else None
                self.gpu_carbon_usage = self.gpu_carbon_usage * 1000 if self.gpu_carbon_usage else None
                self.unit = CarbonUsageUnit.CO2_MG


class CarbonEmission(Sensor):
    """
    Carbon Metric sensor in watts per second to calculate the CO2g/kwh emitted.
    """

    location: Location
    energy_consumption: EnergyConsumption
    previous_energy_consumption_time: datetime | None = None

    _measured_at: float | None = PrivateAttr(default=None)

    def _seconds_since_the_previous_measurement(self, measured_at: float) -> float:
        """
        Get how long the window closing at this measurement lasted, zero when it opens the first.

        :param measured_at: when the hardware was read, on a clock that only moves forward
        :return: the duration in seconds
        """
        if self._measured_at is not None:
            return measured_at - self._measured_at
        if self.previous_energy_consumption_time is not None:
            return (datetime.now() - self.previous_energy_consumption_time).total_seconds()
        return 0.0

    def __init__(self, **data: Any) -> None:
        if "location" not in data:
            data["location"] = Country.get_location()

        if "energy_consumption" not in data:
            data["energy_consumption"] = EnergyConsumption.from_platform()

        super().__init__(**data)

    async def get_energy_usage(self) -> EnergyUsage:
        """
        Generate energy usage.

        :return: the generated energy usage.
        """
        return await self.energy_consumption.get_energy_usage()

    async def get_co2_usage(self) -> CarbonUsage:
        """
        Run the Carbon Emission sensor and get the carbon emission generated.

        :return: the carbon usage.
        """
        energy_usage = await self.get_energy_usage()
        measured_at = time.monotonic()
        energy_usage.convert_unit(unit=EnergyUsageUnit.WATT)
        logger.debug(f"Energy consumption run: {energy_usage}W")

        seconds = self._seconds_since_the_previous_measurement(measured_at=measured_at)
        co2g_per_kwh = await self.location.get_latest_co2g_kwh()
        logger.debug(f"Carbon Emission of the location: {co2g_per_kwh}g CO2 eq/kWh")

        def co2g_from(watts: float | None) -> float | None:
            watt_hours = Power.watt_hours_from_watts_over(watts=watts or 0.0, seconds=seconds)
            return Power.co2g_from_watts_hour(watt_hours, co2g_per_kwh=co2g_per_kwh) or None

        self.previous_energy_consumption_time = datetime.now()
        self._measured_at = measured_at
        return CarbonUsage(
            host_carbon_usage=co2g_from(energy_usage.host_energy_usage) or 0.0,
            cpu_carbon_usage=co2g_from(energy_usage.cpu_energy_usage),
            memory_carbon_usage=co2g_from(energy_usage.memory_energy_usage),
            gpu_carbon_usage=co2g_from(energy_usage.gpu_energy_usage),
            unit=CarbonUsageUnit.CO2_G,
            carbon_intensity_metadata=self.location.carbon_intensity_metadata.model_copy(),
        )
