import pytest

from tracarbon.builder import Tracarbon
from tracarbon.builder import TracarbonBuilder
from tracarbon.builder import TracarbonConfiguration
from tracarbon.builder import TracarbonReport
from tracarbon.exporters import Metric
from tracarbon.exporters import MetricReport
from tracarbon.exporters import StdoutExporter
from tracarbon.general_metrics import CarbonEmissionGenerator
from tracarbon.locations import Country


def build_metric_report(metric_name: str, total: float) -> MetricReport:
    async def metric_value() -> float:
        return total

    return MetricReport(
        exporter_name="Stdout",
        metric=Metric(name=metric_name, value=metric_value),
        total=total,
    )


@pytest.mark.darwin
def test_builder_without_configuration(mocker):
    location = "fr"
    mocker.patch.object(Country, "get_current_country", return_value=location)
    builder = TracarbonBuilder()
    expected_exporter = StdoutExporter(
        metric_generators=[CarbonEmissionGenerator(location=Country(name=location, co2g_kwh=74.0))]
    )

    tracarbon = builder.build()

    assert tracarbon.configuration == TracarbonConfiguration()
    assert type(tracarbon.exporter) is type(expected_exporter)
    assert type(tracarbon.exporter.metric_generators[0]) is type(expected_exporter.metric_generators[0])
    assert tracarbon.location == Country(name=location, co2g_kwh=74.0)


@pytest.mark.darwin
def test_builder_with_configuration():
    configuration = TracarbonConfiguration(co2signal_api_key="API_KEY")
    expected_location = Country(name="fr", co2g_kwh=74.0)
    expected_exporter = StdoutExporter(metric_generators=[CarbonEmissionGenerator(location=expected_location)])
    builder = TracarbonBuilder(configuration=configuration)

    tracarbon = builder.with_exporter(exporter=expected_exporter).with_location(location=expected_location).build()

    assert tracarbon.configuration == configuration
    assert tracarbon.location == expected_location
    assert tracarbon.exporter == expected_exporter
    assert tracarbon.report is not None


def test_report_total_co2g_reads_the_host_carbon_emission():
    report = TracarbonReport(metric_report={"carbon_emission_host": build_metric_report("carbon_emission_host", 12.5)})

    assert report.total_co2g == 12.5


def test_report_total_co2g_without_a_host_carbon_emission():
    report = TracarbonReport(
        metric_report={"energy_consumption_host": build_metric_report("energy_consumption_host", 30.0)}
    )

    assert report.total_co2g is None


def test_stop_returns_the_total_co2g_emitted():
    exporter = StdoutExporter(metric_generators=[])
    exporter.metric_report = {"carbon_emission_host": build_metric_report("carbon_emission_host", 4.2)}
    tracarbon = Tracarbon(
        configuration=TracarbonConfiguration(),
        exporter=exporter,
        location=Country(name="fr", co2g_kwh=74.0),
    )

    total_co2g = tracarbon.stop()

    assert total_co2g == 4.2
