from datetime import datetime
from typing import Optional

from loguru import logger

from tracarbon.hardwares.sensors import EnergyConsumption, Sensor
from tracarbon.locations import Location


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
        logger.debug(f"Energy consumption run: {watt_hours}W/h")
        co2g_per_kwh = await self.location.get_co2g_kwh()
        logger.debug(f"co2g_per_kwh of the location: {co2g_per_kwh}g CO2 eq/kWh")
        return self.co2g_from_watt_hours(
            watt_hours=watt_hours, co2g_per_kwh=co2g_per_kwh
        )
