from datetime import datetime
from typing import Any, Optional

from loguru import logger

from tracarbon.hardwares import EnergyConsumption, Power, Sensor
from tracarbon.locations import Country, Location


class CarbonEmission(Sensor):
    """
    Carbon Metric sensor in watts per second to calculate the CO2g/kwh emitted.
    """

    location: Location
    energy_consumption: EnergyConsumption
    previous_energy_consumption_time: Optional[datetime] = None

    def __init__(self, **data: Any) -> None:
        if not "location" in data:
            data["location"] = Country.get_location()

        if not "energy_consumption" in data:
            data["energy_consumption"] = EnergyConsumption.from_platform()

        super().__init__(**data)

    async def run(self) -> float:
        """
        Run the Carbon Emission sensor.

        :return: the CO2g/kwh generated.
        """
        watts = await self.energy_consumption.run()
        logger.debug(f"Energy consumption run: {watts}W")
        watts_hour = Power.watts_to_watt_hours(
            watts=watts,
            previous_energy_measurement_time=self.previous_energy_consumption_time,
        )
        self.previous_energy_consumption_time = datetime.now()
        logger.debug(f"Energy consumption run: {watts_hour}W/h")
        co2g_per_kwh = await self.location.get_latest_co2g_kwh()
        logger.debug(f"co2g_per_kwh of the location: {co2g_per_kwh}g CO2 eq/kWh")
        return Power.co2g_from_watts_hour(
            watts_hour=watts_hour, co2g_per_kwh=co2g_per_kwh
        )
