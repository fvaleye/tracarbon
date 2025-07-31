FROM python:3.12-slim-bookworm

# Install uv
RUN pip install uv

COPY . /app
WORKDIR /app

# Install dependencies.
# The --system flag installs packages into the system’s Python environment.
# The -e flag installs the project in "editable" mode.
# '.[all]' will install datadog, prometheus and kubernetes optional dependencies.
RUN uv pip install -e '.[all]' --system

# Run tracarbon
ENTRYPOINT ["tracarbon", "run"]
