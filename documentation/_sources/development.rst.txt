***********
Development
***********

With Docker
===========

.. code-block:: bash

    # Inside the root folder
    docker build -t tracarbon ./

    # Open a shell in the image
    docker run --rm -it --entrypoint bash tracarbon

The image entrypoint is ``tracarbon run``. Pass its options directly:

.. code-block:: bash

    docker run --rm -e TRACARBON_INTERVAL_IN_SECONDS=1 tracarbon --country-code-alpha-iso-2 fr

The container needs access to the Linux host's supported sensors to measure its
power. A Docker VM on macOS does not expose the Mac's IOReport counters. Without
RAPL or a supported GPU, the Linux collector raises an error and the CLI exits
with status 1. GPU-only readings leave host totals unavailable. Use the native
installation to measure the Mac. ``docker stop`` sends SIGTERM,
which collects the final interval and prints the report before exit.

With uv
===========

.. code-block:: bash

    # Setup Python
    make init

    # List everything
    make help
