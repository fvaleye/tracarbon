from tracarbon.conf import DATADOG_INSTALLED
from tracarbon.conf import PROMETHEUS_INSTALLED
from tracarbon.exporters.exporter import Exporter
from tracarbon.exporters.exporter import Metric
from tracarbon.exporters.exporter import MetricGenerator
from tracarbon.exporters.exporter import MetricReport
from tracarbon.exporters.exporter import Tag
from tracarbon.exporters.json_exporter import JSONExporter
from tracarbon.exporters.stdout import StdoutExporter

__all__ = [
    "Exporter",
    "JSONExporter",
    "Metric",
    "MetricGenerator",
    "MetricReport",
    "StdoutExporter",
    "Tag",
]

if DATADOG_INSTALLED:
    from tracarbon.exporters.datadog_exporter import DatadogExporter as DatadogExporter

    __all__.append("DatadogExporter")

if PROMETHEUS_INSTALLED:
    from tracarbon.exporters.prometheus_exporter import PrometheusExporter as PrometheusExporter

    __all__.append("PrometheusExporter")
