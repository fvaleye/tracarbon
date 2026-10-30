.. _tracarbon-documentation:

Tracarbon
=========

Tracarbon tracks your device's energy consumption and calculates its carbon
emissions. Use the CLI to measure a command or monitor your machine, or the Python
API to track a workload in your application.

This documentation covers version |release|.

Quick start
-----------

Install Tracarbon with Python 3.10 or newer and start tracking:

.. code-block:: console

   pip install tracarbon
   tracarbon run

Press ``Ctrl+C`` to stop and print the report. No API key is required.
See :doc:`installation` for optional exporters.

To measure your machine while a command runs:

.. code-block:: console

   tracarbon exec -- python your_script.py

See :doc:`usage` for Python examples, carbon intensity configuration, process
tracking, and exporting metrics.

Guides and reference
--------------------

.. toctree::
   :maxdepth: 1

   installation
   usage
   api_reference
   development


Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
