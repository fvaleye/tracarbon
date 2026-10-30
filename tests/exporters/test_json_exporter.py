import asyncio
from datetime import datetime
from datetime import timezone
from threading import Event
from unittest.mock import AsyncMock

import orjson
import pytest

from tracarbon import Country
from tracarbon import MetricGenerator
from tracarbon import TracarbonBuilder
from tracarbon.exporters import JSONExporter
from tracarbon.exporters import Metric
from tracarbon.exporters import Tag


@pytest.mark.parametrize(("suffix", "indent", "pretty"), [("json", 1, False), ("json", 2, True), ("jsonl", 4, False)])
def test_json_exporter_appends_across_restarts(mocker, tmp_path, suffix, indent, pretty):
    fixed_timestamp = datetime(2021, 12, 21, tzinfo=timezone.utc)
    mocker.patch("tracarbon.exporters.json_exporter.datetime").now.return_value = fixed_timestamp
    output = tmp_path / f"metrics.{suffix}"
    metric = Metric(name="sample", value=AsyncMock(return_value=70), tags=[Tag(key="test", value="tags")])
    exporter = JSONExporter(path=str(output), indent=indent, metric_generators=[MetricGenerator(metrics=[metric])])

    for _ in range(2):
        exporter.start(interval_in_seconds=60)
        exporter.stop()
    exporter.flush()

    record = {
        "timestamp": str(fixed_timestamp),
        "metric_name": "sample",
        "metric_value": 70,
        "metric_tags": ["test:tags"],
    }
    contents = output.read_bytes()
    records = [orjson.loads(line) for line in contents.splitlines()] if suffix == "jsonl" else orjson.loads(contents)
    assert records == [record, record]
    assert (b'\n  "' in contents) == pretty
    assert exporter.metric_report["sample"].call_count == 1


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
        generator.metrics.insert(0, Metric(name="failed", value=failing_value))
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


async def test_json_exporter_preserves_records_on_cancellation(mocker, tmp_path):
    output = tmp_path / "metrics.json"
    append_started = Event()
    release_append = Event()
    append_finished = Event()
    append_record = JSONExporter._append_record

    def delayed_append(self, record):
        append_started.set()
        assert release_append.wait(timeout=2)
        append_record(self, record)
        append_finished.set()

    mocker.patch.object(JSONExporter, "_append_record", delayed_append)
    exporter = JSONExporter(
        path=str(output),
        metric_generators=[MetricGenerator(metrics=[Metric(name="sample", value=AsyncMock(return_value=1.0))])],
    )
    collection = asyncio.create_task(exporter._launch_all())
    try:
        assert await asyncio.to_thread(append_started.wait, 2)
        collection.cancel()
        await asyncio.sleep(0.05)
    finally:
        release_append.set()
        with pytest.raises(asyncio.CancelledError):
            await collection
        assert await asyncio.to_thread(append_finished.wait, 2)

    assert [record["metric_name"] for record in orjson.loads(output.read_bytes())] == ["sample"]


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
