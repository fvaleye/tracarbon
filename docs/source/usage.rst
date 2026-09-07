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

``total_co2g`` is ``None`` when no host carbon emission metric was collected.
``stop()`` collects a final sample so short workloads are measured too. Repeated
calls do not collect again. From a metric callback, it finishes the current sample.

Measure a local LLM on Apple Silicon
====================================

Measure energy and carbon per output token with Alibaba's
`Qwen3.8-27B <https://huggingface.co/Qwen/Qwen3.8-27B>`_ (Apache 2.0), using
`MLX Community's 4-bit conversion <https://huggingface.co/mlx-community/Qwen3.8-27B-4bit>`_.
Requires Apple Silicon, readable IOReport counters and a 16.1 GB model download.

Run from the repository checkout. MLX is installed only for this example:

.. code-block:: console

   uv run --frozen --with mlx-lm==0.31.3 --with mlx==0.32.2 python examples/measure_mlx.py \
     --revision 3e6447f082e89cc7f0bc6e5441afd38dfce760ff > measurement.json

The command pins the package versions and conversion's revision. Use ``--model``
and ``--revision`` for another MLX-compatible chat model.

The default prompt asks how to use Tracarbon. The script runs 20 sequential
requests, capped at 128 output tokens each, with greedy sampling and thinking
disabled. Adjust ``--prompt``, ``--max-tokens`` and ``--repeats`` to change the workload.

Loading and warmup happen before measurement. Each request uses a fresh prompt
cache and finishes before measurement stops. Prompt processing and measurement
overhead count toward energy use.

``measurement.json`` records the run settings, device, country, last response
and measurements:

* ``energy_wh``: chip energy in watt-hours.
* ``joules_per_output_token``: ``energy_wh * 3600 / output_tokens``.
* ``co2g_per_output_token``: electricity emissions divided by output tokens.

Tracarbon detects your country from your public IP through ipinfo.io. Use
``--country fr`` to override detection or run offline with cached weights.
The example uses Tracarbon's bundled static factors for 28 European countries
(74 g/kWh for France). The JSON records the selected factor and source.
Carbon estimates cover electricity use; training and hardware manufacturing are excluded.

CPU, GPU and memory counters include other applications' activity, plus ANE energy
where reported. They measure shared chip energy, not wall power or one process.
Missing required counters, sampling errors or no positive energy interval stop the run.

Run on a quiet machine. Repeat requests over a longer window to reduce timing
error on short generations. Keep the prompt, revision, quantization, token limits
and hardware fixed when comparing runs. Across models, check answer quality and
tokenizer differences too: MLX counts output tokens, including an end-of-sequence
token when emitted.

For a remote API, local sensors measure the client. Measuring server emissions
requires data from the server or provider.

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
