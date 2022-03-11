import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from loguru import logger
from pydantic import BaseModel

from tracarbon.hardwares.hardware import HardwareInfo
from tracarbon.locations.location import Location


class Sensor(ABC, BaseModel):
    """
    The Sensor contract.
    """

    async def run(self) -> float:
        """
        Run the sensor.

        :return: the metric sent by the sensor.
        """
        pass


class EnergyConsumption(Sensor):
    """
    A sensor to calculate the energy consumption in watts.
    """

    shell_command: str
    init: bool = False

    async def run(self) -> float:
        """
        Run the sensor.

        :return: the sensor metric.
        """
        proc = await asyncio.create_subprocess_shell(
            self.shell_command, stdout=asyncio.subprocess.PIPE
        )
        result, _ = await proc.communicate()
        return float(result)

    @classmethod
    def from_platform(
        cls,
        platform: str = HardwareInfo.get_platform(),
    ) -> "EnergyConsumption":
        """
        Get the energy consumption from the local platform.

        :return: EnergyConsumption
        """
        if platform in ["Darwin"]:
            return MacEnergyConsumption()
        raise ValueError(f"This platform {platform} is not yet implemented.")


class MacEnergyConsumption(EnergyConsumption):
    """
    Energy Consumption of the Mac working only if it's plugged into electrical outlet in watts.
    """

    shell_command: str = """/usr/sbin/ioreg -rw0 -c AppleSmartBattery | grep BatteryData | grep -o '"AdapterPower"=[0-9]*' | cut -c 16- | xargs -I %  lldb --batch -o "print/f %" | grep -o '$0 = [0-9.]*' | cut -c 6-"""


class CarbonEmission(Sensor):
    """
    Carbon Metric sensor from watts per second to calculate the co2g/kwh emitted.
    """

    location: Location
    energy_consumption: EnergyConsumption
    previous_energy_consumption_time: Optional[datetime] = None
    WH_TO_KWH_FACTOR: int = 1000
    SECONDS_TO_HOURS_FACTOR: int = 3600

    def wattage_to_watt_hours(self, wattage: float) -> float:
        """
        Convert wattage W to watt-hours W/h.

        :param wattage: the wattage in W
        :return: watt-hours W/h
        """
        now = datetime.now()
        if self.previous_energy_consumption_time:
            time_difference_in_seconds = (
                now - self.previous_energy_consumption_time
            ).total_seconds()
        else:
            time_difference_in_seconds = 1
        logger.debug(
            f"Time difference with the previous energy consumption run: {time_difference_in_seconds}s"
        )
        self.previous_energy_consumption_time = now
        return wattage * (time_difference_in_seconds / self.SECONDS_TO_HOURS_FACTOR)

    def co2g_from_watt_hours(self, watt_hours: float, co2g_per_kwh: float) -> float:
        """
        Calculate the co2g emitted using watt hours and the co2g/kwh.

        :param watt_hours: the current wattage
        :param co2g_per_kwh: the co2g emitted during one kwh
        :return: the co2g emitted by the energy consumption
        """
        return (watt_hours / self.WH_TO_KWH_FACTOR) * co2g_per_kwh

    async def run(self) -> float:
        """
        Run the Carbon Emission sensor.

        :return: the co2g/kwh.
        """
        wattage = await self.energy_consumption.run()
        logger.debug(f"Energy consumption run: {wattage}W")
        watt_hours = self.wattage_to_watt_hours(wattage=wattage)
        co2g_per_kwh = await self.location.get_co2g_kwh()
        return self.co2g_from_watt_hours(
            watt_hours=watt_hours, co2g_per_kwh=co2g_per_kwh
        )
