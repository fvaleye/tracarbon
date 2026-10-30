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

Measure your machine's energy and carbon while a command runs:

.. code-block:: console

   tracarbon exec -- python generate.py

When the command exits, Tracarbon prints the totals per component to stderr and exits with the
command's status. Add ``--output report.json`` to save the report.

To measure a local LLM, see `Measure a local LLM`_.

Python API
==========

Wrap your workload in a tracker:

.. code-block:: python

   import time

   from tracarbon import TracarbonBuilder

   with TracarbonBuilder().build() as tracker:
       time.sleep(2)  # Replace with your workload.

   print(tracker.report.total_co2g)

The block starts and stops tracking. ``total_co2g`` is the total CO2 in grams,
or ``None`` if unavailable. For manual control, use ``tracker.start()`` and
``tracker.stop()``.

Configuration
=============

In Python, pass a :class:`.TracarbonConfiguration` to the builder:

.. code-block:: python

   from tracarbon import TracarbonBuilder, TracarbonConfiguration

   configuration = TracarbonConfiguration(interval_in_seconds=1)
   tracker = TracarbonBuilder(configuration=configuration).build()

Creating ``TracarbonConfiguration`` loads the nearest ``.env`` in the working
directory or its parents. Pass ``env_file_path="path/to/.env"`` to load a specific
file. Existing environment variables take precedence over ``.env``; both override
constructor arguments.

``metric_prefix_name`` applies to the default exporter. When supplying your own
exporter, set its prefix and its generators' locations explicitly. The CLI defaults
to collecting both power and carbon emissions; the Python builder collects carbon
emissions.

Carbon intensity
================

Bundled files
-------------

Without an API key, Tracarbon reads yearly lifecycle factors from its packaged
country and cloud-region files. These are static estimates, not live readings.
Choose a country explicitly to avoid the IP geolocation request:

.. code-block:: console

   TRACARBON_CO2SIGNAL_API_KEY= tracarbon run --country-code-alpha-iso-2 fr

The empty environment variable overrides a key in ``.env``. Cloud-provider
detection still runs; a detected cloud region takes precedence over the country.
In Python, select the bundled country directly:

.. code-block:: python

   import time

   from tracarbon import Country, TracarbonBuilder

   location = Country.from_file("fr")
   with TracarbonBuilder().with_location(location).build() as tracker:
       time.sleep(2)

   print(tracker.report.total_co2g)

``Country.from_file`` uses the packaged data even when an API key is configured.
Unsupported countries raise ``CountryIsMissing``. Bundled data only provides
``lifecycle`` factors; choosing ``direct`` without a key logs a warning and uses
the lifecycle value.

Live API
--------

Set ``TRACARBON_CO2SIGNAL_API_KEY`` to an Electricity Maps key. The default
endpoint is ``https://api.electricitymaps.com/v4/carbon-intensity/latest``.
Set ``TRACARBON_EMISSION_FACTOR_TYPE`` to ``lifecycle`` (default) or ``direct``.

.. code-block:: console

   TRACARBON_CO2SIGNAL_API_KEY=API_KEY TRACARBON_EMISSION_FACTOR_TYPE=direct tracarbon run --country-code-alpha-iso-2 fr

Each location caches a successful response for one hour, independently of the
measurement interval. A failed refresh uses the last successful value and marks
``location.carbon_intensity_metadata.fallback_used``. If the first request fails,
the error propagates and the CLI exits with an error. An invalid key does not
automatically select bundled files. On AWS, GCP, and Azure, the default API uses
the detected provider and region; without a key, their packaged region files apply.

Application logging
===================

Python applications configure their own
`Loguru handlers <https://loguru.readthedocs.io/en/stable/resources/recipes.html#configuring-loguru-to-be-used-by-a-library-or-an-application>`_.
Creating ``TracarbonConfiguration`` leaves those handlers unchanged.

The CLI configures its own handler with local variables hidden in tracebacks.
For application handlers, set ``LOGURU_DIAGNOSE=False`` before starting Python
or pass ``diagnose=False`` to ``logger.add()``.

Choose metrics
==============

To collect both energy consumption and carbon emissions:

.. code-block:: python

   import time

   from tracarbon import Country, TracarbonBuilder
   from tracarbon.exporters import StdoutExporter
   from tracarbon.general_metrics import CarbonEmissionGenerator, EnergyConsumptionGenerator

   location = Country.from_file("fr")
   metrics = [EnergyConsumptionGenerator(location=location), CarbonEmissionGenerator(location=location)]
   exporter = StdoutExporter(metric_generators=metrics, metric_prefix_name="tracarbon")
   with TracarbonBuilder(location=location, exporter=exporter).build() as tracker:
       time.sleep(2)

For custom metrics, pass your async measurement function as ``value``:

.. code-block:: python

   import time

   from tracarbon import TracarbonBuilder
   from tracarbon.exporters import Metric, MetricGenerator, StdoutExporter

   async def read_metric():
       return 1.0

   metric = Metric(name="custom_metric", value=read_metric)
   exporter = StdoutExporter(metric_generators=[MetricGenerator(metrics=[metric])])
   with TracarbonBuilder(exporter=exporter).build() as tracker:
       time.sleep(2)

Processes
=========

Measure the CPU energy and carbon emissions of a process and its descendants:

.. code-block:: console

   tracarbon run --pid 1234 --pid 5678

In Python, track the current process with any exporter:

.. code-block:: python

   import time

   from tracarbon import TracarbonBuilder

   with TracarbonBuilder().with_processes().build() as tracker:
       time.sleep(2)

   print(tracker.report.process_co2g)

Pass ``with_processes([1234, 5678])`` to select other processes. Attribution uses each process tree's
share of total CPU capacity: one busy core of four gets a quarter of host CPU power.
``energy_consumption_process_cpu`` reports watts and ``carbon_emission_process_cpu`` reports grams
of CO2 eq, labelled with ``pid`` and ``process_name``.

Measure a local LLM
===================

Run the model on the machine Tracarbon measures and load it before you start. Then measure at least
5 seconds of requests in one session, because `shorter GPU readings are unstable
<https://ml.energy/blog/energy/measurement/thermally-stable-profiling-for-accurate-gpu-energy-measurement/>`_:

.. code-block:: console

   ollama run qwen2.5:0.5b "Say hello."
   tracarbon exec --output session.json -- sh -ec \
     'for request in 1 2 3 4 5; do ollama run --verbose qwen2.5:0.5b "Explain how a database executes a join."; done'

To compare sessions:

- Run on a quiet machine: readings include all activity on the hardware.
- Repeat each session and compare medians.
- Record the token counts, model, quantization, runtime version and settings with each report.
- Watch the prompt cache: cached prompt tokens skip evaluation.
- Host already includes the components, so do not add them to it, except an AMD GPU on Linux.

Export metrics
==============

Use ``tracarbon list-exporters`` to list the exporters available in your installation.
``Stdout`` and ``JSON`` are included in the base package. ``Stdout`` logs to stderr
in the CLI.

JSON and JSON Lines
-------------------

.. code-block:: console

   tracarbon run --exporter-name JSON --country-code-alpha-iso-2 fr

The CLI writes a JSON array to ``tracarbon_export_DD_MM_YYYY.json`` in the working
directory. It appends to an existing file and closes the array after each collection
cycle and at shutdown. For a custom path or JSON Lines, configure the exporter in Python:

.. code-block:: python

   import time

   from tracarbon import Country, TracarbonBuilder
   from tracarbon.exporters import JSONExporter
   from tracarbon.general_metrics import CarbonEmissionGenerator, EnergyConsumptionGenerator

   location = Country.from_file("fr")
   exporter = JSONExporter(
       path="metrics.jsonl",
       metric_prefix_name="tracarbon",
       metric_generators=[
           EnergyConsumptionGenerator(location=location),
           CarbonEmissionGenerator(location=location),
       ],
   )
   with TracarbonBuilder(location=location, exporter=exporter).build() as tracker:
       time.sleep(2)

   print(tracker.report.total_co2g)

Each record contains ``timestamp``, ``metric_name``, ``metric_value``, and
``metric_tags``. The CLI has no output-path option; ``.jsonl`` paths are selected
through the Python API.

Datadog
-------

Send metrics to Datadog:

.. code-block:: console

   pip install 'tracarbon[datadog]'
   DATADOG_API_KEY=API_KEY DATADOG_APP_KEY=APP_KEY tracarbon run --exporter-name Datadog

The Python ``DatadogExporter`` accepts ``datadog_flush_interval`` (default: 10
seconds). Measurements are buffered by the Datadog client, which also flushes at
process exit. Stopping a tracker does not immediately flush that buffer; use
``exporter.stats.flush(float("inf"))`` when delivery is needed before process exit.

Prometheus
----------

Expose host metrics on a local HTTP endpoint:

.. code-block:: console

   pip install 'tracarbon[prometheus]'
   PROMETHEUS_ADDRESS=127.0.0.1 PROMETHEUS_PORT=8081 tracarbon run --exporter-name Prometheus --country-code-alpha-iso-2 fr

In another terminal, run ``curl http://127.0.0.1:8081/metrics``. Prometheus scrapes
this endpoint. By default it listens on ``::`` at port ``8081``.

Export Kubernetes container metrics to Prometheus on Linux:

.. code-block:: console

   pip install 'tracarbon[prometheus,kubernetes]'
   tracarbon run --exporter-name Prometheus --containers

With the default metric prefix, container metrics are exposed with these Prometheus names:

=======================================================  ====================================================================
Metric                                                   Labels
=======================================================  ====================================================================
tracarbon_energy_consumption_kubernetes_total            pod_name, pod_namespace, container_name, platform, containers, location, units
tracarbon_energy_consumption_kubernetes_cpu              pod_name, pod_namespace, container_name, platform, containers, location, units
tracarbon_energy_consumption_kubernetes_memory           pod_name, pod_namespace, container_name, platform, containers, location, units
tracarbon_carbon_emission_kubernetes_total               pod_name, pod_namespace, container_name, platform, containers, location, source, units
tracarbon_carbon_emission_kubernetes_cpu                 pod_name, pod_namespace, container_name, platform, containers, location, source, units
tracarbon_carbon_emission_kubernetes_memory              pod_name, pod_namespace, container_name, platform, containers, location, source, units
tracarbon_carbon_emission_kubernetes_grams_total         pod_name, pod_namespace, container_name, platform, containers, location, source
tracarbon_carbon_emission_kubernetes_cpu_grams_total     pod_name, pod_namespace, container_name, platform, containers, location, source
tracarbon_carbon_emission_kubernetes_memory_grams_total  pod_name, pod_namespace, container_name, platform, containers, location, source
=======================================================  ====================================================================

Energy gauges report power; carbon gauges report emissions over the latest collection interval.
Host, container and process carbon counters ending in ``_grams_total`` accumulate grams of CO2 eq
without a ``units`` label.

A gauge reads ``0`` for a measured zero and ``NaN`` when no reading is available; its carbon counter
then pauses. If Kubernetes returns no pod metrics, the CLI logs
``No Kubernetes container metrics were collected.`` Host metrics are still exported.
