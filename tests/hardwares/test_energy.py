import datetime

from tracarbon import EnergyCounter
from tracarbon import EnergyUsage
from tracarbon import EnergyUsageUnit
from tracarbon import UsageType
from tracarbon.hardwares import Power
from tracarbon.hardwares.energy import EnergyZone


def test_power_should_convert_watt_hours_to_co2g():
    co2g_per_kwh = 20.3
    watts_hour = 10.1
    co2g_expected = 0.20503

    co2g = Power.co2g_from_watts_hour(watts_hour=watts_hour, co2g_per_kwh=co2g_per_kwh)

    assert co2g == co2g_expected


def test_energy_should_convert_watt_hours_to_co2g():
    watts = 45
    watt_hours_expected = 0.75
    one_minute_ago = datetime.datetime.now() - datetime.timedelta(seconds=60)
    previous_energy_measurement_time = one_minute_ago

    watt_hours = Power.watts_to_watt_hours(
        watts=watts, previous_energy_measurement_time=previous_energy_measurement_time
    )

    assert round(watt_hours, 3) == watt_hours_expected


def test_energy_should_convert_watts_from_microjoules():
    uj = 4304343000
    watts_expected = 4304.343

    watts = Power.watts_from_microjoules(
        uj=uj,
    )

    assert round(watts, 3) == watts_expected


def test_energy_usage_with_type_and_conversion():
    host_energy_usage = 2.4
    cpu_energy_usage = 0.4
    memory_energy_usage = 2
    gpu_energy_usage = 1

    energy_usage = EnergyUsage(
        host_energy_usage=host_energy_usage,
        cpu_energy_usage=cpu_energy_usage,
        memory_energy_usage=memory_energy_usage,
        gpu_energy_usage=gpu_energy_usage,
    )

    assert energy_usage.get_energy_usage_on_type(UsageType.HOST) == host_energy_usage
    assert energy_usage.get_energy_usage_on_type(UsageType.CPU) == cpu_energy_usage
    assert energy_usage.get_energy_usage_on_type(UsageType.MEMORY) == memory_energy_usage
    assert energy_usage.get_energy_usage_on_type(UsageType.GPU) == gpu_energy_usage
    assert energy_usage.unit == EnergyUsageUnit.WATT

    energy_usage.convert_unit(EnergyUsageUnit.MILLIWATT)

    assert energy_usage.get_energy_usage_on_type(UsageType.HOST) == host_energy_usage * 1000
    assert energy_usage.get_energy_usage_on_type(UsageType.CPU) == cpu_energy_usage * 1000
    assert energy_usage.get_energy_usage_on_type(UsageType.MEMORY) == memory_energy_usage * 1000
    assert energy_usage.get_energy_usage_on_type(UsageType.GPU) == gpu_energy_usage * 1000
    assert energy_usage.unit == EnergyUsageUnit.MILLIWATT


def test_power_should_convert_microjoules_to_joules():
    uj = 4304343000
    joules_expected = 4304.343

    joules = Power.joules_from_microjoules(uj=uj)

    assert round(joules, 3) == joules_expected


def a_counter(**zones: tuple) -> EnergyCounter:
    return EnergyCounter(
        zones={
            name: EnergyZone(joules=joules, wraps_at_joules=wraps_at_joules, usage_types=(UsageType.HOST,))
            for name, (joules, wraps_at_joules) in zones.items()
        }
    )


def test_a_counter_reports_the_energy_consumed_since_a_previous_reading():
    previous = a_counter(package=(100.0, 1000.0), dram=(40.0, 1000.0))
    current = a_counter(package=(130.0, 1000.0), dram=(55.0, 1000.0))

    assert current.joules_since(previous=previous) == {UsageType.HOST: 45.0}


def test_one_zone_wrapping_does_not_correct_the_zones_that_did_not():
    previous = a_counter(package=(90.0, 100.0), dram=(90.0, 100.0))
    current = a_counter(package=(10.0, 100.0), dram=(95.0, 100.0))

    assert current.joules_since(previous=previous) == {UsageType.HOST: 25.0}


def test_a_zone_going_backwards_without_a_range_is_left_out():
    previous = EnergyCounter(zones={"socket": EnergyZone(joules=90.0, usage_types=(UsageType.HOST,))})
    current = EnergyCounter(zones={"socket": EnergyZone(joules=10.0, usage_types=(UsageType.HOST,))})

    assert current.joules_since(previous=previous) == {}


def test_a_counter_reports_nothing_for_a_zone_the_previous_reading_did_not_have():
    previous = a_counter(package=(100.0, 1000.0))
    current = a_counter(package=(130.0, 1000.0), dram=(12.0, 1000.0))

    assert current.joules_since(previous=previous) == {UsageType.HOST: 30.0}
