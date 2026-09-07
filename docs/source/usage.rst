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

Run Tracarbon CLI with the default Stdout exporter and the C02 Signal API:

>>> TRACARBON_CO2SIGNAL_API_KEY=API_KEY tracarbon run

Run Tracarbon CLI with the default Stdout exporter without the CO2 Signal API:

>>> tracarbon run

Run Tracarbon CLI with the default Stdout exporter with a specified location:

>>> tracarbon run --country-code-alpha-iso-2 fr

Run Tracarbon CLI with the Datadog exporter:

>>> TRACARBON_CO2SIGNAL_API_KEY=API_KEY DATADOG_API_KEY=DATADOG_API_KEY DATADOG_APP_KEY=DATADOG_APP_KEY tracarbon run --exporter-name Datadog

Run Tracarbon CLI on Linux hardware with Kubernetes and send the metrics to Prometheus:

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
``stop()`` collects a closing sample, including when the workload finishes before
the next scheduled sample. Repeated calls do not collect again. Stopping from a
metric callback lets that collection finish without starting another one.

Measure a local LLM on Apple Silicon
====================================

Run ``examples/measure_mlx.py`` from this repository checkout to measure local
generation with `MLX LM <https://github.com/ml-explore/mlx-lm#python-api>`_. The
example uses Tracarbon's IOReport sensor and reports energy and operational carbon
per generated token as JSON. It requires Apple Silicon and readable IOReport
counters. MLX is installed only for the example:

.. code-block:: console

   uv run --frozen --with mlx-lm==0.31.3 --with mlx==0.32.2 python examples/measure_mlx.py \
     --country fr \
     --revision 12fd25f77366fa6b3b4b768ec3050bf629380bac > measurement.json

The default model is `SmolLM2-135M-Instruct
<https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct>`_, a small model for
trying the measurement. The command pins its model revision. ``--model`` accepts
other MLX-compatible chat models; choose their revision with ``--revision``.
``--prompt``, ``--max-tokens`` and ``--repeats`` control the workload. The defaults
are 128 maximum output tokens and 20 sequential requests with greedy sampling.

The model is downloaded, loaded and warmed up before measurement. Each measured
request starts with a fresh prompt cache. The generation stream is fully consumed
and MLX is synchronized before stopping. The measured window includes prompt
processing, decoding, Python orchestration and sampling overhead. Report timestamps
can lag hardware counter readings. Use repeated requests over a longer window to
reduce timing error and the relative overhead on very short generations.

The JSON includes the model configuration, requested revision, package versions,
device, prompt, generated text and these measurements:

* ``energy_wh`` is the integrated chip energy in watt-hours.
* ``joules_per_output_token`` is ``energy_wh * 3600 / output_tokens``.
* ``co2g`` is ``energy_wh / 1000 * carbon_intensity.co2g_kwh``.
* ``co2g_per_output_token`` divides that carbon estimate by ``output_tokens``.
* ``generation_seconds`` times the requests; ``measurement_seconds`` spans report
  timestamps, including bookkeeping around the requests.

Token counts come from MLX, including its end-of-sequence token when generated.
The energy numerator includes prompt processing even though the denominator is
output tokens. Compare runs with the same prompt, model revision, token limits,
sampling settings and hardware. For different models, inspect the generated text
for task quality and account for different tokenizers before comparing efficiency.

``--country fr`` explicitly selects the bundled static France factor, currently
74 g/kWh. It does not fetch a live intensity or detect your location. Choose the
country where the machine runs. The JSON records the factor and its source;
missing date and factor-type metadata remain null. The result covers emissions
associated with electricity use, without allocating model training or device
manufacturing emissions.

The example requires CPU, GPU and memory counters, with ANE energy included where
reported. These counters cover shared activity, including other running applications.
They do not measure wall power or isolate the LLM process. The example fails if a
required counter is unavailable, sampling fails or no positive energy interval is
collected. A reported zero is valid; a missing counter is not. Run it on a quiet
machine and repeat measurements to see the variation. For a remote LLM API, local
sensors only measure the client; server emissions require measurements from the
server or its provider.

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
