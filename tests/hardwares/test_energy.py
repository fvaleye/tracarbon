import datetime

import pytest

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


def test_energy_should_convert_watts_from_microjoules():
    microjoules = 43043430
    watts_expected = 43.043

    watts = Power.watts_from_microjoules(microjoules=microjoules)

    assert round(watts, 3) == watts_expected
