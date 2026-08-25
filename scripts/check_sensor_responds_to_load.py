"""
Check that the energy sensor of this machine follows what the machine computes.

A sensor that reports the same energy whether the machine is idle or busy measures something
other than the compute, and no reading taken from it can be attributed to what ran.
"""

import asyncio
import hashlib
import statistics
import sys
import threading

from tracarbon import EnergyConsumption
from tracarbon.exceptions import TracarbonException
from tracarbon.hardwares.energy import EnergyUsageUnit

READS_PER_WINDOW = 6
BURNING_THREADS = 4
SEPARATION_A_RESPONSIVE_SENSOR_REACHES = 1.05


def burn_until(stop: threading.Event) -> None:
    digest = b"seed"
    while not stop.is_set():
        digest = hashlib.sha256(digest).digest()


async def read_watts(energy_consumption: EnergyConsumption) -> float | None:
    try:
        energy_usage = await energy_consumption.get_energy_usage()
    except TracarbonException as exception:
        print(f"  the sensor failed: {exception}")
        return None
    energy_usage.convert_unit(unit=EnergyUsageUnit.WATT)
    return energy_usage.host_energy_usage


async def mean_watts_while(energy_consumption: EnergyConsumption, busy: bool) -> float | None:
    stop = threading.Event()
    workers = [threading.Thread(target=burn_until, args=(stop,), daemon=True) for _ in range(BURNING_THREADS * busy)]
    for worker in workers:
        worker.start()
    readings = [await read_watts(energy_consumption) for _ in range(READS_PER_WINDOW)]
    stop.set()
    measured = [watts for watts in readings if watts is not None]
    return statistics.fmean(measured) if measured else None


async def check() -> int:
    energy_consumption = EnergyConsumption.from_platform()
    print(f"Sensor       {type(energy_consumption).__name__}")

    idle = await mean_watts_while(energy_consumption, busy=False)
    busy = await mean_watts_while(energy_consumption, busy=True)
    if idle is None or busy is None or not idle:
        print("\nFAIL: the sensor reported nothing to compare.")
        return 1

    print(f"  idle       {idle:6.2f} W")
    print(f"  busy       {busy:6.2f} W")
    print(f"Separation   {busy / idle:.2f}x")
    if busy / idle < SEPARATION_A_RESPONSIVE_SENSOR_REACHES:
        print("\nFAIL: the reading does not follow the compute, so nothing read from it measures a workload.")
        return 1
    print("\nPASS: the reading follows the compute.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(check()))
