import pytest

from tracarbon.builder import TracarbonBuilder
from tracarbon.builder import TracarbonConfiguration
from tracarbon.builder import TracarbonReport
from tracarbon.exporters import StdoutExporter
from tracarbon.general_metrics import CarbonEmissionGenerator
from tracarbon.locations import Country


@pytest.mark.darwin
def test_builder_without_configuration(mocker):
    location = "fr"
    mocker.patch.object(Country, "get_current_country", return_value=location)
    builder = TracarbonBuilder()
    expected_exporter = StdoutExporter(
        metric_generators=[CarbonEmissionGenerator(location=Country(name=location, co2g_kwh=51.1))]
    )

    tracarbon = builder.build()

    assert tracarbon.configuration == TracarbonConfiguration()
    assert type(tracarbon.exporter) == type(expected_exporter)
    assert type(tracarbon.exporter.metric_generators[0]) == type(expected_exporter.metric_generators[0])
    assert tracarbon.location == Country(name=location, co2g_kwh=51.1)


@pytest.mark.darwin
def test_builder_with_configuration():
    configuration = TracarbonConfiguration(co2signal_api_key="API_KEY")
    expected_location = Country(name="fr", co2g_kwh=51.1)
    expected_exporter = StdoutExporter(metric_generators=[CarbonEmissionGenerator(location=expected_location)])
    builder = TracarbonBuilder(configuration=configuration)

    tracarbon = builder.with_exporter(exporter=expected_exporter).with_location(location=expected_location).build()

    assert tracarbon.configuration == configuration
    assert tracarbon.location == expected_location
    assert tracarbon.exporter == expected_exporter
    assert tracarbon.report is not None
