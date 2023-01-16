from datetime import datetime
from enum import Enum
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel

from tracarbon.hardwares import EnergyConsumption, Power, Sensor
from tracarbon.hardwares.energy import EnergyUsage, EnergyUsageUnit, UsageType
from tracarbon.locations import Country, Location


class CarbonUsageUnit(Enum):
    """
    Carbon usage unit.
    """

    CO2_G_KWH = "co2g/kwh"
    CO2_MG_KWH = "co2mg/kwh"


class CarbonUsage(BaseModel):
    """
    Carbon Usage of the different types.
    """

    host_carbon_usage: float = 0.0
    cpu_carbon_usage: Optional[float] = None
    memory_carbon_usage: Optional[float] = None
    gpu_carbon_usage: Optional[float] = None
    unit: CarbonUsageUnit = CarbonUsageUnit.CO2_G_KWH

    def get_carbon_usage_on_type(self, usage_type: UsageType) -> Optional[float]:
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
            if (
                unit == CarbonUsageUnit.CO2_G_KWH
                and self.unit == CarbonUsageUnit.CO2_MG_KWH
            ):
                self.host_carbon_usage = self.host_carbon_usage / 1000
                self.cpu_carbon_usage = (
                    self.cpu_carbon_usage / 1000 if self.cpu_carbon_usage else None
                )
                self.memory_carbon_usage = (
                    self.memory_carbon_usage / 1000
                    if self.memory_carbon_usage
                    else None
                )
                self.gpu_carbon_usage = (
                    self.gpu_carbon_usage / 1000 if self.gpu_carbon_usage else None
                )
                self.unit = CarbonUsageUnit.CO2_G_KWH
            elif (
                unit == CarbonUsageUnit.CO2_MG_KWH
                and self.unit == CarbonUsageUnit.CO2_G_KWH
            ):
                self.host_carbon_usage = self.host_carbon_usage * 1000
                self.cpu_carbon_usage = (
                    self.cpu_carbon_usage * 1000 if self.cpu_carbon_usage else None
                )
                self.memory_carbon_usage = (
                    self.memory_carbon_usage * 1000
                    if self.memory_carbon_usage
                    else None
                )
                self.gpu_carbon_usage = (
                    self.gpu_carbon_usage * 1000 if self.gpu_carbon_usage else None
                )
                self.unit = CarbonUsageUnit.CO2_MG_KWH


class CarbonEmission(Sensor):
    """
    Carbon Metric sensor in watts per second to calculate the CO2g/kwh emitted.
    """

    location: Location
    energy_consumption: EnergyConsumption
    previous_energy_consumption_time: Optional[datetime] = None

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
        logger.debug(f"Energy consumption run: {energy_usage}")

        co2g_per_kwh = await self.location.get_latest_co2g_kwh()
        logger.debug(f"Carbon Emission of the location: {co2g_per_kwh}g CO2 eq/kWh")
        energy_usage.convert_unit(unit=EnergyUsageUnit.WATT)
        host_carbon_usage = Power.co2g_from_watts_hour(
            Power.watts_to_watt_hours(
                watts=energy_usage.host_energy_usage,
                previous_energy_measurement_time=self.previous_energy_consumption_time,
            ),
            co2g_per_kwh=co2g_per_kwh,
        )
        cpu_carbon_usage = 0.0
        memory_carbon_usage = 0.0
        gpu_carbon_usage = 0.0
        if energy_usage.cpu_energy_usage:
            cpu_carbon_usage = Power.co2g_from_watts_hour(
                Power.watts_to_watt_hours(
                    watts=energy_usage.cpu_energy_usage,
                    previous_energy_measurement_time=self.previous_energy_consumption_time,
                ),
                co2g_per_kwh=co2g_per_kwh,
            )
        if energy_usage.memory_energy_usage:
            memory_carbon_usage = Power.co2g_from_watts_hour(
                Power.watts_to_watt_hours(
                    watts=energy_usage.memory_energy_usage,
                    previous_energy_measurement_time=self.previous_energy_consumption_time,
                ),
                co2g_per_kwh=co2g_per_kwh,
            )
        if energy_usage.gpu_energy_usage:
            gpu_carbon_usage = Power.co2g_from_watts_hour(
                Power.watts_to_watt_hours(
                    watts=energy_usage.gpu_energy_usage,
                    previous_energy_measurement_time=self.previous_energy_consumption_time,
                ),
                co2g_per_kwh=co2g_per_kwh,
            )
        self.previous_energy_consumption_time = datetime.now()
        return CarbonUsage(
            host_carbon_usage=host_carbon_usage,
            cpu_carbon_usage=cpu_carbon_usage if cpu_carbon_usage > 0 else None,
            memory_carbon_usage=memory_carbon_usage
            if memory_carbon_usage > 0
            else None,
            gpu_carbon_usage=gpu_carbon_usage if gpu_carbon_usage > 0 else None,
        )
