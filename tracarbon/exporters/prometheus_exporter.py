import math
import os
from threading import Lock
from typing import Any
from typing import Dict
from typing import List
from typing import cast
from weakref import WeakValueDictionary

from loguru import logger
from pydantic import Field
from pydantic import PrivateAttr

from tracarbon.conf import PROMETHEUS_INSTALLED
from tracarbon.emissions import CarbonUsageUnit
from tracarbon.exporters.exporter import Exporter
from tracarbon.exporters.exporter import MetricGenerator
from tracarbon.exporters.exporter import Tag

_GRAMS_PER_CARBON_UNIT = {CarbonUsageUnit.CO2_G.value: 1.0, CarbonUsageUnit.CO2_MG.value: 0.001}

if PROMETHEUS_INSTALLED:
    from prometheus_client import Counter
    from prometheus_client import Gauge
    from prometheus_client import start_http_server

    _shared_metrics: Dict[str, Gauge | Counter] = {}
    _exporters: WeakValueDictionary[int, "PrometheusExporter"] = WeakValueDictionary()
    _metrics_lock = Lock()

    class PrometheusExporter(Exporter):
        """
        Expose metrics through an HTTP server for Prometheus to scrape.

        Exporters share collectors created in the default registry.
        """

        prometheus_metrics: Dict[str, Gauge] = Field(default_factory=dict)
        address: str | None = None
        port: int | None = None
        _container_series: set[tuple[Gauge | Counter, tuple[str, ...]]] = PrivateAttr(default_factory=set)
        _current_generator_series: set[tuple[Gauge | Counter, tuple[str, ...]]] = PrivateAttr(default_factory=set)
        _series_by_generator: Dict[int, tuple[MetricGenerator, set[tuple[Gauge | Counter, tuple[str, ...]]]]] = (
            PrivateAttr(default_factory=dict)
        )

        def __init__(self, **data: Any) -> None:
            super().__init__(**data)
            addr = self.address if self.address else os.environ.get("PROMETHEUS_ADDRESS", "::")
            port = self.port if self.port else int(os.environ.get("PROMETHEUS_PORT", 8081))
            start_http_server(
                addr=addr,
                port=port,
            )
            with _metrics_lock:
                _exporters[id(self)] = self

        async def _launch_all(self) -> None:
            try:
                await super()._launch_all()
            finally:
                with _metrics_lock:
                    active_generator_ids = {id(generator) for generator in self.metric_generators}
                    self._series_by_generator = {
                        key: value for key, value in self._series_by_generator.items() if key in active_generator_ids
                    }
                    previous_series = self._container_series
                    self._container_series = {
                        series
                        for _, generator_series in self._series_by_generator.values()
                        for series in generator_series
                    }
                    for metric, labels in previous_series - self._container_series:
                        if not any(
                            (metric, labels) in exporter._container_series
                            for exporter in _exporters.values()
                            if exporter is not self
                            and (
                                not exporter.stopped
                                or exporter._collection_thread is not None
                                or exporter._final_collection_pending
                            )
                        ):
                            metric.remove(*labels)

        def _export(
            self, metric_type: type[Gauge] | type[Counter], name: str, tags: List[Tag], value: float | None
        ) -> None:
            """
            Update a gauge or add a finite, nonnegative counter increment.

            A None value claims a pod series without updating its sample, keeping other exporters from
            removing it while collection is in progress.
            """
            with _metrics_lock:
                metric: Gauge | Counter | None = self.prometheus_metrics.get(name) if metric_type is Gauge else None
                if metric is None:
                    if name not in _shared_metrics:
                        _shared_metrics[name] = metric_type(name, f"Tracarbon metric {name}", [tag.key for tag in tags])
                    metric = _shared_metrics[name]
                if metric_type is Gauge:
                    self.prometheus_metrics[name] = cast(Gauge, metric)
                labels = tuple(tag.value for tag in tags)
                if any(tag.key == "pod_name" for tag in tags):
                    self._container_series.add((metric, labels))
                    self._current_generator_series.add((metric, labels))
                if value is None:
                    return
                series = metric.labels(*labels) if labels else metric
                if metric_type is Gauge:
                    cast(Gauge, series).set(value)
                elif math.isfinite(value) and value >= 0:
                    series.inc(value)
                else:
                    logger.warning(f"Skipping metric[{name}]: a counter cannot add [{value}].")

        async def launch(self, metric_generator: MetricGenerator) -> None:
            """
            Launch the Prometheus exporter with the metrics.
            Each metric is a gauge holding its latest value. Carbon also accumulates in a counter of grams
            named with ``_grams_total`` and labelled without ``units``.

            :param metric_generator: the metric generator
            """
            _, retained_series = self._series_by_generator.setdefault(id(metric_generator), (metric_generator, set()))
            self._current_generator_series = set()
            first_failure: Exception | None = None
            try:
                async for metric in metric_generator.generate():
                    metric_name = metric.format_name(metric_prefix_name=self.metric_prefix_name, separator="_")
                    grams_per_unit = _GRAMS_PER_CARBON_UNIT.get(metric.unit())
                    counter_name = f"{metric_name.removesuffix('_total')}_grams_total"
                    counter_tags = [tag for tag in metric.tags if tag.key != "units"]
                    if any(tag.key == "pod_name" for tag in metric.tags):
                        self._export(Gauge, metric_name, metric.tags, None)
                        if grams_per_unit is not None:
                            self._export(Counter, counter_name, counter_tags, None)
                    try:
                        metric_value = await metric.value()
                    except Exception as failure:
                        logger.error(f"Error reading metric '{metric.name}': {failure}")
                        if first_failure is None:
                            first_failure = failure
                        continue
                    if metric_value is not None:
                        await self.add_metric_to_report(metric=metric, value=metric_value)
                        logger.info(
                            f"Sending metric[{metric_name}] with value [{metric_value}] "
                            f"and labels{metric.format_tags()} to Prometheus."
                        )
                    self._export(Gauge, metric_name, metric.tags, metric_value)
                    if grams_per_unit is not None:
                        self._export(
                            Counter,
                            counter_name,
                            counter_tags,
                            None if metric_value is None else metric_value * grams_per_unit,
                        )
                if first_failure is not None:
                    raise first_failure
                retained_series.clear()
            finally:
                retained_series.update(self._current_generator_series)

        @classmethod
        def get_name(cls) -> str:
            """
            Get the name of the exporter.

            :return: the Exporter's name
            """
            return "Prometheus"
