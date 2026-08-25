import datetime

from tracarbon import EnergyCounter
from tracarbon import EnergyUsage
from tracarbon import EnergyUsageUnit
from tracarbon import UsageType
from tracarbon.hardwares import Power


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


def test_power_should_convert_watt_hours_to_joules():
    watt_hours = 0.75
    joules_expected = 2700.0

    joules = Power.joules_from_watt_hours(watt_hours=watt_hours)

    assert joules == joules_expected


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


def test_a_counter_reports_the_energy_consumed_since_a_previous_reading():
    previous = EnergyCounter(joules={UsageType.HOST: 100.0, UsageType.CPU: 40.0})
    current = EnergyCounter(joules={UsageType.HOST: 130.0, UsageType.CPU: 55.0})

    consumed = current.joules_since(previous=previous)

    assert consumed == {UsageType.HOST: 30.0, UsageType.CPU: 15.0}


def test_a_counter_that_wrapped_reports_the_energy_across_the_wrap():
    previous = EnergyCounter(joules={UsageType.HOST: 990.0})
    current = EnergyCounter(joules={UsageType.HOST: 10.0}, wraps_at_joules={UsageType.HOST: 1000.0})

    consumed = current.joules_since(previous=previous)

    assert consumed == {UsageType.HOST: 20.0}


def test_a_counter_reports_nothing_for_a_type_the_previous_reading_did_not_have():
    previous = EnergyCounter(joules={UsageType.HOST: 100.0})
    current = EnergyCounter(joules={UsageType.HOST: 130.0, UsageType.GPU: 12.0})

    consumed = current.joules_since(previous=previous)

    assert consumed == {UsageType.HOST: 30.0}
