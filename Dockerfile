FROM python:3.11-buster

# Environmnet variables
ENV POETRY_VENV=/opt/poetry-venv
ENV POETRY_CACHE_DIR=/opt/.cache

# Prerequisites
RUN rm -rf /var/lib/apt/lists/* & apt-get -y update && apt-get -y --no-install-recommends install python3 python3-pip

# Python
RUN pip install --upgrade pip

# Install poetry separated from system interpreter and add it to PATH
RUN python3 -m venv $POETRY_VENV \
    && $POETRY_VENV/bin/pip install -U pip setuptools \
    && $POETRY_VENV/bin/pip install poetry==1.8.0
ENV PATH="${PATH}:${POETRY_VENV}/bin"

COPY . ./carbon-tracker
WORKDIR ./carbon-tracker

# Install tracarbon
RUN poetry install --all-extras

# Run tracarbon
ENTRYPOINT ["poetry", "run", "tracarbon", "run"]
