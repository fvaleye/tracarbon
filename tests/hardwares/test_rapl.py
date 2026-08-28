import datetime
import pathlib

import pytest

from tracarbon import RAPL
from tracarbon.hardwares import EnergyUsageUnit
from tracarbon.hardwares import RAPLResult
from tracarbon.hardwares import UsageType
from tracarbon.hardwares.energy import EnergyZone


@pytest.mark.linux
@pytest.mark.darwin
def test_is_rapl_compatible(tmpdir):
    assert RAPL().is_rapl_compatible() is False

    path = tmpdir.mkdir("intel-rapl")

    assert RAPL(path=str(path)).is_rapl_compatible() is True


@pytest.mark.asyncio
async def test_get_rapl_power_usage():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/intel-rapl"
    rapl_separator_for_windows = "T"

    rapl_results = await RAPL(path=path, rapl_separator=rapl_separator_for_windows).get_rapl_power_usage()

    def by_energy_uj(rapl_result: RAPLResult) -> str:
        return rapl_result.energy_uj

    rapl_results.sort(key=by_energy_uj)
    assert rapl_results[0].name == "T1T0-core"
    assert rapl_results[0].energy_uj == 3.0
    assert rapl_results[1].name == "T1T1-dram"
    assert rapl_results[1].energy_uj == 2433.0
    assert rapl_results[2].name == "T1-package-1"
    assert rapl_results[2].energy_uj == 20232.0
    assert rapl_results[3].name == "T0T1-dram"
    assert rapl_results[3].energy_uj == 2592370025.0
    assert rapl_results[4].name == "T0-package-0"
    assert rapl_results[4].energy_uj == 24346753748.0
    assert rapl_results[5].name == "T0T0-core"
    assert rapl_results[5].energy_uj == 43725162336.0


@pytest.mark.asyncio
@pytest.mark.linux
@pytest.mark.darwin
async def test_get_rapl_power_wrap_around_when_0():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/intel-rapl2"
    two_seconds_ago = datetime.datetime.now() - datetime.timedelta(seconds=2)
    rapl_separator_for_windows = "T"
    rapl_results = dict()
    rapl_results["T0-package-0"] = RAPLResult(
        name="T0-package-0", energy_uj=2, max_energy_uj=70000, timestamp=two_seconds_ago
    )
    rapl_results["T0T0-core"] = RAPLResult(
        name="T0T0-core", energy_uj=1, max_energy_uj=70000, timestamp=two_seconds_ago
    )
    rapl = RAPL(path=path, rapl_separator=rapl_separator_for_windows, rapl_results=rapl_results)
    host_energy_usage_expected = 35
    cpu_energy_usage_expected = 35

    energy_report = await rapl.get_energy_report()
    energy_report.convert_unit(EnergyUsageUnit.MILLIWATT)
    assert round(energy_report.host_energy_usage, 0) == host_energy_usage_expected
    assert round(energy_report.cpu_energy_usage, 0) == cpu_energy_usage_expected
    assert energy_report.memory_energy_usage is None


@pytest.mark.asyncio
@pytest.mark.linux
@pytest.mark.darwin
async def test_get_total_uj_one_call():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/intel-rapl2"
    rapl_separator_for_windows = "T"
    one_minute_ago = datetime.datetime.now() - datetime.timedelta(seconds=60)
    rapl_results = dict()
    rapl_results["T0-package-0"] = RAPLResult(
        name="T0-package-0", energy_uj=50000, max_energy_uj=70000, timestamp=one_minute_ago
    )
    rapl_results["T0T0-core"] = RAPLResult(
        name="T0T0-core", energy_uj=40000, max_energy_uj=70000, timestamp=one_minute_ago
    )
    rapl = RAPL(path=path, rapl_separator=rapl_separator_for_windows, rapl_results=rapl_results)
    host_energy_usage_expected = 0.33
    cpu_energy_usage_expected = 0.5

    energy_report = await rapl.get_energy_report()
    energy_report.convert_unit(EnergyUsageUnit.MILLIWATT)
    assert round(energy_report.host_energy_usage, 2) == host_energy_usage_expected
    assert round(energy_report.cpu_energy_usage, 2) == cpu_energy_usage_expected
    assert energy_report.memory_energy_usage is None


def test_classify_domain():
    rapl = RAPL()

    assert rapl._classify_domain("T0-package-0") == "package"
    assert rapl._classify_domain("T0T1-dram") == "memory"
    assert rapl._classify_domain("T0T0-core") == "cpu"
    assert rapl._classify_domain("T0T2-uncore") == "gpu"
    assert rapl._classify_domain("unknown") == "unknown"


@pytest.mark.asyncio
@pytest.mark.linux
@pytest.mark.darwin
async def test_results_with_two_packages_are_correctly_computed():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/intel-rapl"
    rapl_separator_for_windows = "T"

    one_milliwatt = 60000

    one_minute_ago = datetime.datetime.now() - datetime.timedelta(seconds=60)
    rapl_results = dict()
    rapl_results["T0-package-0"] = RAPLResult(
        name="T0-package-0", energy_uj=24346753748 - one_milliwatt, max_energy_uj=65532610987, timestamp=one_minute_ago
    )
    rapl_results["T0T0-core"] = RAPLResult(
        name="T0T0-core", energy_uj=43725162336 - one_milliwatt, max_energy_uj=65532610987, timestamp=one_minute_ago
    )
    rapl_results["T0T1-dram"] = RAPLResult(
        name="T0T1-dram", energy_uj=2592370025 - one_milliwatt, max_energy_uj=65532610987, timestamp=one_minute_ago
    )

    rapl_results["T1-package-1"] = RAPLResult(
        name="T1-package-1", energy_uj=20232 - one_milliwatt, max_energy_uj=65532610987, timestamp=one_minute_ago
    )
    rapl_results["T1T0-core"] = RAPLResult(
        name="T1T0-core", energy_uj=65532610987 - one_milliwatt + 3, max_energy_uj=65532610987, timestamp=one_minute_ago
    )
    rapl_results["T1T1-dram"] = RAPLResult(
        name="T1T1-dram", energy_uj=2433 - one_milliwatt, max_energy_uj=65532610987, timestamp=one_minute_ago
    )

    rapl = RAPL(path=path, rapl_separator=rapl_separator_for_windows, rapl_results=rapl_results)

    host_energy_usage_expected = 4
    cpu_energy_usage_expected = 2
    memory_energy_usage_expected = 2

    energy_report = await rapl.get_energy_report()
    energy_report.convert_unit(EnergyUsageUnit.MILLIWATT)
    assert round(energy_report.host_energy_usage, 2) == host_energy_usage_expected
    assert round(energy_report.cpu_energy_usage, 2) == cpu_energy_usage_expected
    assert round(energy_report.memory_energy_usage, 2) == memory_energy_usage_expected
    assert energy_report.gpu_energy_usage is None


@pytest.mark.asyncio
async def test_get_energy_counter_keeps_every_zone_apart():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/intel-rapl"
    rapl_separator_for_windows = "T"

    counter = await RAPL(path=path, rapl_separator=rapl_separator_for_windows).get_energy_counter()

    assert counter.zones["T0-package-0"].joules == pytest.approx(24346.753748)
    assert counter.zones["T0-package-0"].usage_types == (UsageType.HOST,)
    assert counter.zones["T0T1-dram"].usage_types == (UsageType.HOST, UsageType.MEMORY)
    assert counter.zones["T0T0-core"].usage_types == (UsageType.CPU,)
    assert counter.zones["T0-package-0"].wraps_at_joules == pytest.approx(65532.610987)


@pytest.mark.asyncio
@pytest.mark.linux
@pytest.mark.darwin
async def test_a_zone_is_read_against_the_highest_power_it_is_constrained_to():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/intel-rapl"
    rapl_separator_for_windows = "T"
    the_higher_of_the_two_constraints_in_watts = 35.0

    counter = await RAPL(path=path, rapl_separator=rapl_separator_for_windows).get_energy_counter()

    assert counter.zones["T0-package-0"].counts_at_most_watts == the_higher_of_the_two_constraints_in_watts
    assert counter.zones["T0-package-0"].averaged_over_seconds == pytest.approx(0.00244)
    assert counter.zones["T0-package-0"].seconds_before_it_can_wrap_twice == pytest.approx(1872.36, abs=0.01)


@pytest.mark.asyncio
@pytest.mark.linux
@pytest.mark.darwin
@pytest.mark.asyncio
async def test_a_zone_whose_budget_covers_a_whole_roll_affords_no_window():
    a_limit_whose_budget_is_a_whole_roll = EnergyZone(
        joules=0.0, wraps_at_joules=100.0, counts_at_most_watts=10.0, averaged_over_seconds=10.0
    )
    a_limit_whose_budget_is_half_a_roll = EnergyZone(
        joules=0.0, wraps_at_joules=100.0, counts_at_most_watts=10.0, averaged_over_seconds=5.0
    )
    a_limit_averaged_over_almost_nothing = EnergyZone(
        joules=0.0, wraps_at_joules=100.0, counts_at_most_watts=10.0, averaged_over_seconds=0.1
    )

    assert a_limit_whose_budget_is_a_whole_roll.seconds_before_it_can_wrap_twice == 0.0
    assert a_limit_whose_budget_is_half_a_roll.seconds_before_it_can_wrap_twice == 5.0
    assert a_limit_averaged_over_almost_nothing.seconds_before_it_can_wrap_twice == pytest.approx(9.9)


@pytest.mark.asyncio
async def test_a_constraint_whose_window_cannot_be_told_leaves_the_zone_uncapped(tmpdir, mocker):
    zone = tmpdir.mkdir("zone")
    zone.join("constraint_0_max_power_uw").write("28000000")

    capped_at = await RAPL._read_the_power_the_zone_is_capped_at(file_path=str(zone))

    assert capped_at is None


@pytest.mark.asyncio
async def test_a_constraint_naming_itself_a_peak_bounds_every_stretch(tmpdir):
    zone = tmpdir.mkdir("zone")
    zone.join("constraint_0_max_power_uw").write("28000000")
    zone.join("constraint_0_name").write("peak_power")

    capped_at = await RAPL._read_the_power_the_zone_is_capped_at(file_path=str(zone))

    assert capped_at == (28.0, 0.0)


async def test_the_zones_of_a_machine_measure_a_window_end_to_end():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/intel-rapl"
    rapl_separator_for_windows = "T"
    rapl = RAPL(path=path, rapl_separator=rapl_separator_for_windows)
    a_second = 1.0

    counter = await rapl.get_energy_counter()

    assert counter.joules_since(previous=counter, seconds=a_second) == {
        UsageType.HOST: 0.0,
        UsageType.CPU: 0.0,
        UsageType.MEMORY: 0.0,
    }


async def test_a_zone_inside_another_is_held_to_what_encloses_it():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/intel-rapl"
    rapl_separator_for_windows = "T"
    the_constraint_the_package_publishes = 35.0

    counter = await RAPL(path=path, rapl_separator=rapl_separator_for_windows).get_energy_counter()

    assert counter.zones["T0T0-core"].counts_at_most_watts == the_constraint_the_package_publishes
