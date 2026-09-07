*****
Usage
*****

After :doc:`installation`, use the CLI to monitor your device or the Python API
to measure a workload.

CLI
===

Start tracking:

.. code-block:: console

   tracarbon run

Press ``Ctrl+C`` to stop. No API key is required.

Keep Tracarbon running while you use your local LLM. See the
`local LLM example <https://github.com/fvaleye/tracarbon/tree/main/examples>`_.

Python API
==========

Wrap your workload in a tracker:

.. code-block:: python

   from tracarbon import TracarbonBuilder

   with TracarbonBuilder().build() as tracker:
       run_workload()

   print(tracker.report.total_co2g)

The block starts and stops tracking. ``total_co2g`` is the total CO2 in grams,
or ``None`` if unavailable. For manual control, use ``tracker.start()`` and
``tracker.stop()``.

Configuration
=============

Choose a country:

.. code-block:: console

   tracarbon run --country-code-alpha-iso-2 fr

Set an API key for live carbon intensity:

.. code-block:: console

   TRACARBON_CO2SIGNAL_API_KEY=API_KEY tracarbon run

In Python, pass a :class:`.TracarbonConfiguration` to the builder:

.. code-block:: python

   from tracarbon import TracarbonBuilder, TracarbonConfiguration

   configuration = TracarbonConfiguration(interval_in_seconds=1)
   tracker = TracarbonBuilder(configuration=configuration).build()

Choose metrics
==============

To collect both energy consumption and carbon emissions:

.. code-block:: python

   from tracarbon import TracarbonBuilder
   from tracarbon.exporters import StdoutExporter
   from tracarbon.general_metrics import CarbonEmissionGenerator, EnergyConsumptionGenerator

   metrics = [EnergyConsumptionGenerator(), CarbonEmissionGenerator()]
   exporter = StdoutExporter(metric_generators=metrics)
   with TracarbonBuilder(exporter=exporter).build() as tracker:
       run_workload()

For custom metrics, pass your async measurement function as ``value``:

.. code-block:: python

   from tracarbon import TracarbonBuilder
   from tracarbon.exporters import Metric, MetricGenerator, StdoutExporter

   metric = Metric(name="custom_metric", value=read_metric)
   exporter = StdoutExporter(metric_generators=[MetricGenerator(metrics=[metric])])
   with TracarbonBuilder(exporter=exporter).build() as tracker:
       run_workload()

Export metrics
==============

Send metrics to Datadog:

.. code-block:: console

   DATADOG_API_KEY=API_KEY DATADOG_APP_KEY=APP_KEY tracarbon run --exporter-name Datadog

Export Kubernetes container metrics to Prometheus on Linux:

.. code-block:: console

   tracarbon run --exporter-name Prometheus --containers

With the default metric prefix, container metrics are exposed with these Prometheus names:

===============================================  ====================================================================
Metric                                           Labels
===============================================  ====================================================================
tracarbon_energy_consumption_kubernetes_total    pod_name, pod_namespace, container_name, platform, containers, location, units
tracarbon_energy_consumption_kubernetes_cpu      pod_name, pod_namespace, container_name, platform, containers, location, units
tracarbon_energy_consumption_kubernetes_memory   pod_name, pod_namespace, container_name, platform, containers, location, units
tracarbon_carbon_emission_kubernetes_total       pod_name, pod_namespace, container_name, platform, containers, location, source, units
tracarbon_carbon_emission_kubernetes_cpu         pod_name, pod_namespace, container_name, platform, containers, location, source, units
tracarbon_carbon_emission_kubernetes_memory      pod_name, pod_namespace, container_name, platform, containers, location, source, units
===============================================  ====================================================================

Zero values are exported. If Kubernetes returns no pod metrics, the CLI logs
``No Kubernetes container metrics were collected.`` Host metrics are still exported.
