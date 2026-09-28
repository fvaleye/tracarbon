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

With uv
===========

.. code-block:: bash

    # Setup Python
    make init

    # List everything
    make help
