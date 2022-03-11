.DEFAULT_GOAL := help

.PHONY: setup
setup: ## Setup the requirements
	$(info --- Setup dependencies ---)
	poetry update

.PHONY: format
format: ## Format the code
	poetry run black .
	poetry run isort .

.PHONY: check
check: ## Run check
	$(info Check Python)
	poetry run isort --diff --check-only .
	poetry run black --check .
	poetry run mypy

.PHONY: unit-test
unit-test: ## Run unit test
	$(info --- Run Python unit-test ---)
	poetry run python -m pytest

.PHONY: build-documentation
build-documentation: ## Build documentation with Sphinx
	$(info --- Run build of the Sphinx documentation ---)
	poetry run sphinx-build -Wn -b html -d ./docs/build/doctrees ./docs/source ./docs/build/html

.PHONY: publish
publish: ## Publish to Pypi
	$(info --- Run Publish to Pypi ---)
	poetry publish --build --username "${PYPI_USERNAME}" --password "${PYPI_PASSWORD}"

.PHONY: help
help: ## List the rules
	grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'