"""
Check that the energy sensor of this machine follows what the machine computes.

A sensor that reports the same energy whether the machine is idle or busy cannot be
attributed to a workload, and any per workload number read from it is meaningless.
"""

import hashlib
import sys
import time

from tracarbon import EnergyConsumption
from tracarbon import WorkloadNotAttributable
from tracarbon import track
from tracarbon.locations.country import Country

MEASURED_SECONDS = 3.0
ROUNDS = 3
SEPARATION_A_RESPONSIVE_SENSOR_REACHES = 1.05
A_LOCATION_THAT_NEEDS_NO_API_KEY = Country(name="fr", co2g_kwh=74.0)


def stay_idle() -> None:
    time.sleep(MEASURED_SECONDS)


def burn_the_cpu() -> None:
    deadline = time.monotonic() + MEASURED_SECONDS
    digest = b"seed"
    while time.monotonic() < deadline:
        digest = hashlib.sha256(digest).digest()


def measure(name: str, work) -> float:
    with track(name=name, location=A_LOCATION_THAT_NEEDS_NO_API_KEY, interval_in_seconds=0.5) as tracker:
        work()
    usage = tracker.usage
    print(f"  {name:<6} {usage.joules:8.2f} J over {usage.duration_in_seconds:5.2f} s ({usage.average_watts:6.2f} W)")
    return usage.average_watts or 0.0


def main() -> int:
    energy_consumption = EnergyConsumption.from_platform()
    print(f"Sensor       {type(energy_consumption).__name__}")

    separations = []
    for round_number in range(1, ROUNDS + 1):
        print(f"Round {round_number}")
        try:
            idle_watts = measure("idle", stay_idle)
            busy_watts = measure("busy", burn_the_cpu)
        except WorkloadNotAttributable as exception:
            print(f"\nFAIL: {exception}")
            return 1
        separations.append(busy_watts / idle_watts if idle_watts else 0.0)

    separation = sum(separations) / len(separations)
    print(f"\nSeparation   {separation:.2f}x busy over idle")
    if separation < SEPARATION_A_RESPONSIVE_SENSOR_REACHES:
        print("FAIL: the reading does not follow the compute, so it cannot be attributed to a workload.")
        return 1
    print("PASS: the reading follows the compute.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
