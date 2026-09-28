import sys
from datetime import datetime
from datetime import timezone
from unittest.mock import AsyncMock

import orjson
import psutil
import pytest

from tracarbon import Country
from tracarbon import MetricGenerator
from tracarbon import TracarbonBuilder
from tracarbon.exporters import JSONExporter
from tracarbon.exporters import Metric
from tracarbon.exporters import Tag


def test_json_exporter_should_write_well_formatted_metrics_in_json_file(mocker, tmpdir):
    mock = mocker.patch("tracarbon.exporters.json_exporter.datetime")
    fixed_timestamp = datetime(2021, 12, 21, tzinfo=timezone.utc)
    mock.now.return_value = fixed_timestamp
    test_json_file = tmpdir.mkdir("data").join("test.json")
    interval_in_seconds = 1
    memory_value = 70
    mock_memory_value = ["0", "0", memory_value]
    mocker.patch.object(psutil, "virtual_memory", return_value=mock_memory_value)

    async def get_memory_usage() -> float:
        return psutil.virtual_memory()[2]

    expected = [
        {
            "timestamp": str(fixed_timestamp),
            "metric_name": "test_metric_1",
            "metric_value": 70,
            "metric_tags": ["test:tags"],
        },
        {
            "timestamp": str(fixed_timestamp),
            "metric_name": "test_metric_1",
            "metric_value": 70,
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
    exporter = JSONExporter(quit=True, metric_generators=metric_generators, path=str(test_json_file))
    exporter.start(interval_in_seconds=interval_in_seconds)
    exporter.stop()

    exporter.start(interval_in_seconds=interval_in_seconds)
    exporter.stop()

    with open(test_json_file, "rb") as file:
        assert orjson.loads(file.read()) == expected

    assert exporter.metric_report["test_metric_1"].exporter_name == JSONExporter.get_name()
    assert exporter.metric_report["test_metric_1"].metric == memory_metric
    assert exporter.metric_report["test_metric_1"].total > 0
    assert exporter.metric_report["test_metric_1"].average > 0
    assert exporter.metric_report["test_metric_1"].minimum < sys.float_info.max
    assert exporter.metric_report["test_metric_1"].maximum > 0
    assert exporter.metric_report["test_metric_1"].call_count == 1


@pytest.mark.parametrize("initial_content", ["", "[\n  ]\n"])
def test_json_exporter_can_append_to_an_empty_array_and_stop_from_a_callback(tmp_path, initial_content):
    output = tmp_path / "metrics.json"
    output.write_text(initial_content)

    async def value() -> float:
        exporter.stop()
        return 0.0

    exporter = JSONExporter(
        path=str(output), metric_generators=[MetricGenerator(metrics=[Metric(name="zero", value=value)])]
    )
    try:
        exporter.start(interval_in_seconds=60)
        records = orjson.loads(output.read_bytes())
        assert len(records) == 1
        assert records[0]["metric_value"] == 0.0
    finally:
        exporter.stop()


def test_json_exporter_preserves_report_and_records_when_final_collection_fails(tmp_path):
    async def value() -> float:
        return 1.0

    async def failing_value() -> float:
        raise ValueError("A sensor failed")

    output = tmp_path / "metrics.json"
    generator = MetricGenerator(metrics=[Metric(name="carbon_emission_host", value=value)])
    exporter = JSONExporter(path=str(output), metric_generators=[generator])
    tracarbon = TracarbonBuilder(exporter=exporter, location=Country(name="fr", co2g_kwh=400.0)).build()
    try:
        tracarbon.start()
        generator.metrics.append(Metric(name="failed", value=failing_value))
        with pytest.raises(ValueError, match="A sensor failed"):
            tracarbon.stop()

        assert tracarbon.report.total_co2g == 2.0
        assert tracarbon.report.end_time is not None
        records = orjson.loads(output.read_bytes())
        assert [record["metric_name"] for record in records] == ["carbon_emission_host", "carbon_emission_host"]
    finally:
        exporter.stop()


def test_json_exporter_defaults_to_a_json_array(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    metric = Metric(name="default", value=AsyncMock(return_value=1.0))
    exporter = JSONExporter(metric_generators=[MetricGenerator(metrics=[metric])])

    exporter.start(interval_in_seconds=60)
    exporter.stop()

    records = orjson.loads((tmp_path / exporter.path).read_bytes())
    assert [record["metric_value"] for record in records] == [1.0]


def test_jsonl_appends_across_restarts(mocker, tmp_path):
    fixed_timestamp = datetime(2021, 12, 21, tzinfo=timezone.utc)
    mocker.patch("tracarbon.exporters.json_exporter.datetime").now.return_value = fixed_timestamp
    output = tmp_path / "metrics.jsonl"
    metric = Metric(name="test_metric_1", value=AsyncMock(return_value=70), tags=[Tag(key="test", value="tags")])
    exporter = JSONExporter(path=str(output), metric_generators=[MetricGenerator(metrics=[metric])])

    for _ in range(2):
        exporter.start(interval_in_seconds=60)
        exporter.stop()
    exporter.flush()

    record = {
        "timestamp": str(fixed_timestamp),
        "metric_name": "test_metric_1",
        "metric_value": 70,
        "metric_tags": ["test:tags"],
    }
    assert [orjson.loads(line) for line in output.read_bytes().splitlines()] == [record, record]


def test_jsonl_records_are_readable_during_collection(tmp_path):
    output = tmp_path / "metrics.jsonl"
    records_read_mid_cycle = []

    async def read_records_during_collection() -> float:
        records_read_mid_cycle.extend(orjson.loads(line) for line in output.read_bytes().splitlines())
        return 2.0

    exporter = JSONExporter(
        path=str(output),
        metric_generators=[
            MetricGenerator(
                metrics=[
                    Metric(name="first", value=AsyncMock(return_value=1.0)),
                    Metric(name="second", value=read_records_during_collection),
                ]
            )
        ],
    )
    exporter.start(interval_in_seconds=60)
    exporter.stop()

    assert [record["metric_name"] for record in records_read_mid_cycle] == ["first"]


def test_jsonl_separates_a_torn_record_from_the_next(tmp_path):
    output = tmp_path / "metrics.jsonl"
    output.write_bytes(b'{"metric_name": "complete"}\n{"metric_na')
    exporter = JSONExporter(
        path=str(output),
        metric_generators=[MetricGenerator(metrics=[Metric(name="after", value=AsyncMock(return_value=1.0))])],
    )

    exporter.start(interval_in_seconds=60)
    exporter.stop()

    complete, torn, after = output.read_bytes().splitlines()
    assert torn == b'{"metric_na'
    assert [orjson.loads(line)["metric_name"] for line in (complete, after)] == ["complete", "after"]
