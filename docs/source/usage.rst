*****
Usage
*****

Tracarbon
=========

1. Set the environment variable or set the configuration
2. Choose :class:`.Exporter` with your :class:`.Metric`
3. Run it!

Run the CLI
===========

Run the tracarbon cli with Stdout exporter and the API key:

>>> TRACARBON_CO2SIGNAL_API_KEY=API_KEY tracarbon run

Run the tracarbon cli with Stdout exporter with the static file:

>>> tracarbon run

Run the tracarbon cli with Datadog exporter:

>>> TRACARBON_CO2SIGNAL_API_KEY=API_KEY DATADOG_API_KEY=DATADOG_API_KEY DATADOG_APP_KEY=DATADOG_APP_KEY tracarbon run --exporter-name Datadog

Run the code
============
>>> from tracarbon import TracarbonBuilder, TracarbonConfiguration
>>>
>>> configuration = TracarbonConfiguration()  # Your configuration
>>> tracarbon = TracarbonBuilder(configuration=configuration).build()
>>> tracarbon.start()
>>> # Your code
>>> tracarbon.stop()
>>>
>>> with tracarbon:
>>>    # Your code

Run the code with a customs configuration
=========================================
>>> from tracarbon import TracarbonBuilder, TracarbonConfiguration
>>> from tracarbon.exporters import StdoutExporter, Metric
>>> from tracarbon.emissions import CarbonEmission
>>> from tracarbon.locations import Country
>>>
>>> configuration = TracarbonConfiguration(co2signal_api_key="API_KEY")  # Your configuration
>>> location = Country.get_location()
>>> metrics = [Metric(name="co2_emission", value=CarbonEmission().run, tags=[])]
>>> exporter = StdoutExporter(metrics=metrics)
>>> tracarbon = TracarbonBuilder(configuration=configuration).build(exporter=exporter, location=location)
>>> tracarbon.start()
>>> # Your code
>>> tracarbon.stop()
>>>
>>> with tracarbon:
>>>    # Your code

