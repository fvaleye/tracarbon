from datetime import datetime

import psutil
import ujson

from tracarbon import Country, HardwareInfo, MetricGenerator
from tracarbon.exporters import JSONExporter, Metric, Tag


def test_json_exporter_should_write_well_formatted_metrics_in_json_file(mocker, tmpdir):
    mock = mocker.patch("tracarbon.exporters.json_exporter.datetime")
    fixed_timestamp = datetime(2021, 12, 21)
    mock.utcnow.return_value = fixed_timestamp
    test_json_file = tmpdir.mkdir("data").join("test.json")
    interval_in_seconds = 1
    memory_value = "70"
    mock_memory_value = ["0", "0", memory_value]
    mocker.patch.object(psutil, "virtual_memory", return_value=mock_memory_value)

    async def get_memory_usage() -> float:
        return psutil.virtual_memory()[2]

    expected = [
        {
            "timestamp": str(fixed_timestamp),
            "metric_name": "test_metric_1",
            "metric_value": "70",
            "metric_tags": ["test:tags"],
        },
        {
            "timestamp": str(fixed_timestamp),
            "metric_name": "test_metric_1",
            "metric_value": "70",
            "metric_tags": ["test:tags"],
        },
    ]

    mocker.patch.object(
        Country,
        "get_location",
        return_value=Country(name="fr", co2g_kwh=50.0),
    )
    memory_metric = Metric(
        name="test_metric_1",
        value=get_memory_usage,
        tags=[Tag(key="test", value="tags")],
    )

    metric_generators = [MetricGenerator(metrics=[memory_metric])]
    exporter = JSONExporter(
        quit=True, metric_generators=metric_generators, path=str(test_json_file)
    )
    exporter.start(interval_in_seconds=interval_in_seconds)
    exporter.stop()

    exporter.start(interval_in_seconds=interval_in_seconds)
    exporter.stop()
    exporter.flush()

    with open(test_json_file, "r") as file:
        assert ujson.load(file) == expected
