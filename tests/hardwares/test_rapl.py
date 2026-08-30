import datetime
import pathlib

import pytest

from tracarbon import RAPL
from tracarbon.hardwares import EnergyUsageUnit
from tracarbon.hardwares import Power
from tracarbon.hardwares import RAPLResult


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
@pytest.mark.linux
@pytest.mark.darwin
async def test_a_zone_that_was_restarted_is_not_credited_a_whole_range():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/intel-rapl"
    two_seconds_ago = datetime.datetime.now() - datetime.timedelta(seconds=2)
    rapl_separator_for_windows = "T"
    a_reading_the_zone_restarted_from = 60000000000.0
    rapl_results = {
        "T0-package-0": RAPLResult(
            name="T0-package-0",
            energy_uj=a_reading_the_zone_restarted_from,
            max_energy_uj=65532610987,
            timestamp=two_seconds_ago,
        )
    }
    rapl = RAPL(path=path, rapl_separator=rapl_separator_for_windows, rapl_results=rapl_results)

    energy_report = await rapl.get_energy_report()

    assert energy_report.host_energy_usage == 0.0
    assert rapl.rapl_results["T0-package-0"].energy_uj < a_reading_the_zone_restarted_from


@pytest.mark.asyncio
@pytest.mark.linux
@pytest.mark.darwin
async def test_a_zone_that_wrapped_within_what_it_could_draw_is_still_corrected():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/intel-rapl2"
    two_seconds_ago = datetime.datetime.now() - datetime.timedelta(seconds=2)
    rapl_separator_for_windows = "T"
    a_reading_just_below_the_range_the_zone_wraps_at = 69990.0
    rapl_results = {
        "T0-package-0": RAPLResult(
            name="T0-package-0",
            energy_uj=a_reading_just_below_the_range_the_zone_wraps_at,
            max_energy_uj=70000,
            timestamp=two_seconds_ago,
        )
    }
    rapl = RAPL(path=path, rapl_separator=rapl_separator_for_windows, rapl_results=rapl_results)

    energy_report = await rapl.get_energy_report()

    the_ten_microjoules_the_roll_accounts_for = 10.002 / 2 / Power.MICROJOULES_TO_WATT_FACTOR
    assert energy_report.host_energy_usage == pytest.approx(the_ten_microjoules_the_roll_accounts_for)


@pytest.mark.asyncio
async def test_a_wrap_uses_the_full_elapsed_time_to_check_its_power(mocker):
    now = datetime.datetime.now()
    elapsed_seconds = 2.49
    previous_energy_uj = 65500000000.0
    max_energy_uj = 65532610987.0
    wrapped_energy_joules = 84.0
    current_result = RAPLResult(
        name="T0-package-0",
        energy_uj=previous_energy_uj + wrapped_energy_joules * Power.MICROJOULES_TO_WATT_FACTOR - max_energy_uj,
        max_energy_uj=max_energy_uj,
        timestamp=now,
    )
    rapl = RAPL(
        rapl_results={
            current_result.name: RAPLResult(
                name=current_result.name,
                energy_uj=previous_energy_uj,
                max_energy_uj=max_energy_uj,
                timestamp=now - datetime.timedelta(seconds=elapsed_seconds),
            )
        },
        max_power_watts={current_result.name: 35.0},
    )
    mocker.patch.object(RAPL, "get_rapl_power_usage", return_value=[current_result])

    energy_report = await rapl.get_energy_report()

    assert energy_report.host_energy_usage > 0.0


@pytest.mark.asyncio
@pytest.mark.linux
@pytest.mark.darwin
async def test_a_zone_nothing_around_it_bounds_is_corrected_as_it_was_before():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/intel-rapl"
    two_seconds_ago = datetime.datetime.now() - datetime.timedelta(seconds=2)
    rapl_separator_for_windows = "T"
    a_reading_the_zone_restarted_from = 60000000000.0
    rapl_results = {
        "T1T0-core": RAPLResult(
            name="T1T0-core",
            energy_uj=a_reading_the_zone_restarted_from,
            max_energy_uj=65532610987,
            timestamp=two_seconds_ago,
        )
    }
    rapl = RAPL(path=path, rapl_separator=rapl_separator_for_windows, rapl_results=rapl_results)

    energy_report = await rapl.get_energy_report()

    assert energy_report.cpu_energy_usage > 0.0


@pytest.mark.asyncio
async def test_a_zone_publishing_no_ceiling_reads_as_none_at_all(tmpdir):
    zone = tmpdir.mkdir("zone")

    assert await RAPL._read_max_power_watts(file_path=str(zone)) == 0.0


@pytest.mark.asyncio
async def test_the_peak_power_limit_is_read_when_the_zone_publishes_one(tmpdir):
    zone = tmpdir.mkdir("zone")
    zone.join("constraint_0_max_power_uw").write("28000000")
    zone.join("constraint_1_max_power_uw").write("35000000")
    zone.join("constraint_2_max_power_uw").write("70000000")

    assert await RAPL._read_max_power_watts(file_path=str(zone)) == 70.0


@pytest.mark.asyncio
@pytest.mark.linux
@pytest.mark.darwin
async def test_the_ceiling_a_zone_publishes_is_read_once(mocker):
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/intel-rapl2"
    rapl_separator_for_windows = "T"
    rapl = RAPL(path=path, rapl_separator=rapl_separator_for_windows)
    reading_the_ceiling = mocker.spy(RAPL, "_read_max_power_watts")

    await rapl.get_energy_report()
    read_after_the_first_report = reading_the_ceiling.call_count
    await rapl.get_energy_report()
    await rapl.get_energy_report()

    assert read_after_the_first_report == len(rapl.max_power_watts)
    assert reading_the_ceiling.call_count == read_after_the_first_report
    assert rapl.max_power_watts["T0-package-0"] == 28.0


@pytest.mark.asyncio
@pytest.mark.linux
@pytest.mark.darwin
async def test_dram_without_a_published_max_does_not_borrow_the_package_max():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/intel-rapl"
    one_hundred_seconds_ago = datetime.datetime.now() - datetime.timedelta(seconds=100)
    rapl_separator_for_windows = "T"
    current_energy_uj = 2592370025.0
    max_energy_uj = 65532610987.0
    wrapped_energy_uj = 4000000000.0
    rapl_results = {
        "T0T1-dram": RAPLResult(
            name="T0T1-dram",
            energy_uj=current_energy_uj + max_energy_uj - wrapped_energy_uj,
            max_energy_uj=max_energy_uj,
            timestamp=one_hundred_seconds_ago,
        )
    }
    rapl = RAPL(path=path, rapl_separator=rapl_separator_for_windows, rapl_results=rapl_results)

    energy_report = await rapl.get_energy_report()

    assert energy_report.memory_energy_usage == pytest.approx(40.0)


@pytest.mark.asyncio
@pytest.mark.linux
@pytest.mark.darwin
async def test_the_largest_published_max_bounds_the_zone():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/intel-rapl"
    rapl_separator_for_windows = "T"
    published_max_power = 35.0
    thermal_spec_power = 28.0
    rapl = RAPL(path=path, rapl_separator=rapl_separator_for_windows)

    await rapl.get_energy_report()

    assert rapl.max_power_watts["T0-package-0"] == published_max_power
    assert rapl.max_power_watts["T0-package-0"] != thermal_spec_power


@pytest.mark.asyncio
@pytest.mark.linux
@pytest.mark.darwin
async def test_a_restart_of_a_whole_package_leaves_no_zone_of_it_reporting():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/intel-rapl"
    a_minute_ago = datetime.datetime.now() - datetime.timedelta(seconds=60)
    rapl_separator_for_windows = "T"
    a_reading_every_zone_restarted_from = 60000000000.0
    rapl_results = {
        name: RAPLResult(
            name=name,
            energy_uj=a_reading_every_zone_restarted_from,
            max_energy_uj=65532610987,
            timestamp=a_minute_ago,
        )
        for name in ("T0-package-0", "T0T0-core", "T0T1-dram")
    }
    rapl = RAPL(
        path=path,
        rapl_separator=rapl_separator_for_windows,
        rapl_results=rapl_results,
        max_power_watts={"T0T0-core": 0.0, "T0T1-dram": 0.0},
    )

    energy_report = await rapl.get_energy_report()

    assert energy_report.host_energy_usage == 0.0
    assert energy_report.memory_energy_usage is None
    assert energy_report.cpu_energy_usage is None
