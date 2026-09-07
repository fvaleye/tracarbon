*****
Usage
*****

Tracarbon
=========

1. Set the environment variable or directly set the configuration.
2. Choose :class:`.Exporter` with your list of :class:`.Metric`.
3. Launch Tracarbon!

Run the CLI
===========

Print metrics using the CO2 Signal API:

>>> TRACARBON_CO2SIGNAL_API_KEY=API_KEY tracarbon run

Run without an API key:

>>> tracarbon run

Choose a country:

>>> tracarbon run --country-code-alpha-iso-2 fr

Send metrics to Datadog:

>>> TRACARBON_CO2SIGNAL_API_KEY=API_KEY DATADOG_API_KEY=DATADOG_API_KEY DATADOG_APP_KEY=DATADOG_APP_KEY tracarbon run --exporter-name Datadog

Export Kubernetes container metrics to Prometheus on Linux:

>>> tracarbon run --exporter-name Prometheus --containers

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

Run the code
============
>>> from tracarbon import TracarbonBuilder, TracarbonConfiguration
>>>
>>> configuration = TracarbonConfiguration(co2signal_api_key="API_KEY")  # Your configuration
>>> tracarbon = TracarbonBuilder(configuration=configuration).build()
>>> tracarbon.start()
>>> # Your code
>>> total_co2g = tracarbon.stop()
>>>
>>> with tracarbon:
>>>    # Your code
>>>
>>> report = tracarbon.report # Get the report
>>> print(report.total_co2g)

``stop()`` returns total CO2 in grams, or ``None`` if unavailable.

Measure a local LLM on Apple Silicon
====================================

Run `Qwen3.8-27B <https://huggingface.co/Qwen/Qwen3.8-27B>`_ with
`MLX Community's 4-bit weights <https://huggingface.co/mlx-community/Qwen3.8-27B-4bit>`_
(16.1 GB download). From this checkout:

.. code-block:: console

   uv run --frozen --with mlx-lm==0.31.3 --with mlx==0.32.2 python examples/measure_mlx.py \
     --revision 3e6447f082e89cc7f0bc6e5441afd38dfce760ff > measurement.json

``measurement.json`` contains energy, CO2 and per-token averages. See ``--help`` for options.

Country is detected by IP; ``--country fr`` overrides it. Carbon estimates use
bundled static factors for 28 European countries.

Readings cover shared chip activity, including other apps. Loading and warmup
are excluded. Run on a quiet machine.

Run the code with general metrics
=================================
>>> from tracarbon import TracarbonBuilder, TracarbonConfiguration
>>> from tracarbon.exporters import StdoutExporter
>>> from tracarbon.general_metrics import CarbonEmissionGenerator, EnergyConsumptionGenerator
>>>
>>> configuration = TracarbonConfiguration(co2signal_api_key="API_KEY")  # Your configuration
>>> metric_generators = [EnergyConsumptionGenerator(), CarbonEmissionGenerator()]
>>> exporter = StdoutExporter(metric_generators=metric_generators) # Your exporter
>>> tracarbon = TracarbonBuilder(configuration=configuration).with_exporter(exporter=exporter).build()
>>> tracarbon.start()
>>> # Your code
>>> tracarbon.stop()
>>>
>>> with tracarbon:
>>>    # Your code
>>>
>>> report = tracarbon.report # Get the report

Run the code with a custom configuration
=========================================
>>> from tracarbon import TracarbonBuilder, TracarbonConfiguration
>>> from tracarbon.exporters import StdoutExporter, MetricGenerator, Metric, Tag
>>> from tracarbon.emissions import CarbonEmission
>>>
>>> configuration = TracarbonConfiguration(co2signal_api_key="API_KEY")  # Your configuration
>>> metric_generators = [MetricGenerator(metrics=[Metric(name="custom_metric", value=CustomClass().run, tags=[Tag(key="key", value="value")])])]  # Your custom metrics
>>> exporter = StdoutExporter(metric_generators=metric_generators) # Your exporter
>>> tracarbon = TracarbonBuilder(configuration=configuration).with_exporter(exporter=exporter).build()
>>> tracarbon.start()
>>> # Your code
>>> tracarbon.stop()
>>>
>>> with tracarbon:
>>>    # Your code
>>>
>>> report = tracarbon.report # Get the report
