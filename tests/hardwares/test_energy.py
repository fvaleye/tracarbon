import datetime

import pytest

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


A_WINDOW_THE_ZONES_BELOW_COULD_HAVE_DRAWN_THEIR_ENERGY_IN = 0.2
A_ZONE_HELD_TO_FOUR_HUNDRED_WATTS = 400.0
A_ZONE_HELD_TO_FIFTEEN_WATTS = 15.0
A_ROLL_OF_SIXTY_FIVE_KILOJOULES = 65532.6


def a_counter(**zones: tuple) -> EnergyCounter:
    return EnergyCounter(
        zones={
            name: EnergyZone(
                joules=zone[0],
                wraps_at_joules=zone[1],
                counts_at_most_watts=zone[2] if len(zone) > 2 else A_ZONE_HELD_TO_FOUR_HUNDRED_WATTS,
                usage_types=(UsageType.HOST,),
            )
            for name, zone in zones.items()
        }
    )


def test_a_counter_reports_the_energy_consumed_since_a_previous_reading():
    previous = a_counter(package=(100.0, 1000.0), dram=(40.0, 1000.0))
    current = a_counter(package=(130.0, 1000.0), dram=(55.0, 1000.0))

    assert current.joules_since(
        previous=previous, seconds=A_WINDOW_THE_ZONES_BELOW_COULD_HAVE_DRAWN_THEIR_ENERGY_IN
    ) == {UsageType.HOST: 45.0}


def test_one_zone_wrapping_does_not_correct_the_zones_that_did_not():
    previous = a_counter(package=(90.0, 100.0), dram=(90.0, 100.0))
    current = a_counter(package=(10.0, 100.0), dram=(95.0, 100.0))

    assert current.joules_since(
        previous=previous, seconds=A_WINDOW_THE_ZONES_BELOW_COULD_HAVE_DRAWN_THEIR_ENERGY_IN
    ) == {UsageType.HOST: 25.0}


def test_a_zone_going_backwards_without_a_range_is_left_out():
    previous = EnergyCounter(zones={"socket": EnergyZone(joules=90.0, usage_types=(UsageType.HOST,))})
    current = EnergyCounter(zones={"socket": EnergyZone(joules=10.0, usage_types=(UsageType.HOST,))})

    assert (
        current.joules_since(previous=previous, seconds=A_WINDOW_THE_ZONES_BELOW_COULD_HAVE_DRAWN_THEIR_ENERGY_IN) == {}
    )


def test_a_usage_type_a_zone_was_not_measured_for_is_reported_by_none_of_its_zones():
    previous = a_counter(package=(100.0, 1000.0))
    current = a_counter(package=(130.0, 1000.0), dram=(12.0, 1000.0))

    assert (
        current.joules_since(previous=previous, seconds=A_WINDOW_THE_ZONES_BELOW_COULD_HAVE_DRAWN_THEIR_ENERGY_IN) == {}
    )


def test_a_zone_that_could_have_rolled_over_twice_takes_its_siblings_with_it():
    previous = a_counter(package=(900.0, 1000.0, 400.0), dram=(10.0, None))
    current = a_counter(package=(1000.0, 1000.0, 400.0), dram=(20.0, None))
    seconds_that_zone_affords = 1000.0 / 400.0

    assert current.joules_since(previous=previous, seconds=seconds_that_zone_affords / 2) == {UsageType.HOST: 110.0}
    assert current.joules_since(previous=previous, seconds=seconds_that_zone_affords * 2) == {}


def test_a_window_as_long_as_one_roll_ends_on_the_reading_it_started_from():
    zone = EnergyZone(joules=0.0, wraps_at_joules=1000.0, counts_at_most_watts=400.0)
    exactly_one_roll = 1000.0 / 400.0

    assert zone.could_have_wrapped_twice_in(seconds=exactly_one_roll) is True
    assert zone.could_have_wrapped_twice_in(seconds=exactly_one_roll * 0.99) is False


def test_a_zone_that_rolls_over_without_a_power_it_is_held_to_is_not_measured():
    an_hour = 3600.0
    previous = a_counter(package=(90.0, 100.0, None))
    one_roll_that_could_have_been_several = a_counter(package=(10.0, 100.0, None))
    several_rolls_landing_where_it_nearly_started = a_counter(package=(95.0, 100.0, None))

    assert one_roll_that_could_have_been_several.joules_since(previous=previous, seconds=an_hour) == {}
    assert several_rolls_landing_where_it_nearly_started.joules_since(previous=previous, seconds=an_hour) == {}


def test_a_counter_that_rolled_over_inside_its_budget_is_still_measured():
    a_hundred_seconds = 100.0
    before_the_roll = a_counter(package=(65500.0, A_ROLL_OF_SIXTY_FIVE_KILOJOULES, A_ZONE_HELD_TO_FOUR_HUNDRED_WATTS))
    after_the_roll = a_counter(package=(100.0, A_ROLL_OF_SIXTY_FIVE_KILOJOULES, A_ZONE_HELD_TO_FOUR_HUNDRED_WATTS))

    assert after_the_roll.joules_since(previous=before_the_roll, seconds=a_hundred_seconds) == {
        UsageType.HOST: pytest.approx(132.6)
    }


def test_a_burst_shorter_than_the_window_a_limit_averages_over_is_not_read_as_a_restart():
    a_tenth_of_a_second = 0.1
    a_limit_averaged_over_a_minute = EnergyZone(
        joules=0.0,
        wraps_at_joules=A_ROLL_OF_SIXTY_FIVE_KILOJOULES,
        counts_at_most_watts=A_ZONE_HELD_TO_FIFTEEN_WATTS,
        averaged_over_seconds=60.0,
    )
    joules_a_burst_may_reach_before_the_average_pulls_it_back = 100.0

    assert (
        a_limit_averaged_over_a_minute.drew_more_than_it_could_have(
            joules=joules_a_burst_may_reach_before_the_average_pulls_it_back, seconds=a_tenth_of_a_second
        )
        is False
    )


def test_a_roll_within_the_window_allowance_is_not_read_as_a_restart():
    six_seconds = 6.0
    a_limit_averaged_over_five_seconds = EnergyZone(
        joules=0.0,
        wraps_at_joules=1000.0,
        counts_at_most_watts=10.0,
        averaged_over_seconds=5.0,
    )
    joules_the_roll_credits = 70.0

    assert (
        a_limit_averaged_over_five_seconds.drew_more_than_it_could_have(
            joules=joules_the_roll_credits, seconds=six_seconds
        )
        is False
    )


def test_a_counter_that_was_restarted_is_not_read_as_one_that_rolled_over():
    a_minute = 60.0
    before_the_restart = a_counter(package=(60000.0, A_ROLL_OF_SIXTY_FIVE_KILOJOULES, A_ZONE_HELD_TO_FIFTEEN_WATTS))
    after_the_restart = a_counter(package=(0.5, A_ROLL_OF_SIXTY_FIVE_KILOJOULES, A_ZONE_HELD_TO_FIFTEEN_WATTS))
    joules_reading_it_as_a_roll_would_credit = 5533.1
    joules_fifteen_watts_could_draw_in_a_minute = A_ZONE_HELD_TO_FIFTEEN_WATTS * a_minute

    assert joules_reading_it_as_a_roll_would_credit > joules_fifteen_watts_could_draw_in_a_minute
    assert after_the_restart.joules_since(previous=before_the_restart, seconds=a_minute) == {}


def test_a_zone_is_measured_against_the_power_it_is_held_to_when_it_publishes_one():
    over_an_hour = 4368.84
    a_laptop_package_held_to_fifteen_watts = EnergyZone(
        joules=0.0, wraps_at_joules=A_ROLL_OF_SIXTY_FIVE_KILOJOULES, counts_at_most_watts=A_ZONE_HELD_TO_FIFTEEN_WATTS
    )
    a_zone_publishing_no_constraint = EnergyZone(joules=0.0, wraps_at_joules=A_ROLL_OF_SIXTY_FIVE_KILOJOULES)

    assert a_laptop_package_held_to_fifteen_watts.seconds_before_it_can_wrap_twice == pytest.approx(
        over_an_hour, abs=0.01
    )
    assert a_zone_publishing_no_constraint.seconds_before_it_can_wrap_twice is None


def test_a_zone_the_later_reading_lost_takes_its_siblings_with_it():
    previous = a_counter(package=(100.0, 1000.0), dram=(40.0, 1000.0))
    current = a_counter(package=(130.0, 1000.0))

    assert (
        current.joules_since(previous=previous, seconds=A_WINDOW_THE_ZONES_BELOW_COULD_HAVE_DRAWN_THEIR_ENERGY_IN) == {}
    )


def test_a_zone_going_backwards_with_a_range_of_zero_takes_its_siblings_with_it():
    previous = a_counter(package=(90.0, 0.0), dram=(10.0, None))
    current = a_counter(package=(10.0, 0.0), dram=(20.0, None))

    assert (
        current.joules_since(previous=previous, seconds=A_WINDOW_THE_ZONES_BELOW_COULD_HAVE_DRAWN_THEIR_ENERGY_IN) == {}
    )
