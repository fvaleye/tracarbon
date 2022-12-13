import pytest

from tracarbon.builder import TracarbonBuilder, TracarbonConfiguration
from tracarbon.emissions import CarbonEmission
from tracarbon.exporters import Metric, StdoutExporter, Tag
from tracarbon.general_metrics import CarbonEmissionMetric
from tracarbon.hardwares import HardwareInfo
from tracarbon.locations import Country


@pytest.mark.darwin
def test_builder_without_configuration(mocker):
    location = "fr"
    mocker.patch.object(Country, "get_current_country", return_value=location)
    builder = TracarbonBuilder()
    expected_exporter = StdoutExporter(
        metrics=[CarbonEmissionMetric(location=Country(name=location, co2g_kwh=51.1))]
    )

    tracarbon = builder.build()

    assert tracarbon.configuration == TracarbonConfiguration()
    assert type(tracarbon.exporter) == type(expected_exporter)
    assert type(tracarbon.exporter.metrics[0]) == type(expected_exporter.metrics[0])
    assert tracarbon.location == Country(name=location, co2g_kwh=51.1)


@pytest.mark.darwin
def test_builder_with_configuration():
    configuration = TracarbonConfiguration(co2signal_api_key="API_KEY")
    expected_location = Country(name="fr", co2g_kwh=51.1)
    expected_exporter = StdoutExporter(
        metrics=[CarbonEmissionMetric(location=expected_location)]
    )
    builder = TracarbonBuilder(configuration=configuration)

    tracarbon = builder.build(exporter=expected_exporter, location=expected_location)

    assert tracarbon.configuration == configuration
    assert tracarbon.location == expected_location
    assert tracarbon.exporter == expected_exporter
