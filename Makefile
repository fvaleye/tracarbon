.DEFAULT_GOAL := help

.PHONY: init
init: ## Init the requirements
	$(info --- 🖥 Init dependencies ---)
	@poetry install

.PHONY: format
format: ## Format the code
	$(info --- 🐍 Check Python format ---)
	@poetry run black .
	@poetry run isort .

.PHONY: style
style: ## Run style
	$(info --- 🐍 Style Python ---)
	@poetry run isort --diff --check-only .
	@poetry run black --check .
	@poetry run mypy

.PHONY: security
security: ## Run security checks
	$(info --- 🐍 Security Python ---)
	@poetry run bandit -c pyproject.toml -r .

.PHONY: complexity
complexity: ## Run complexity checks
	$(info --- 🐍 Complexity Python ---)
	@poetry run radon cc -a tracarbon/

.PHONY: test-unit
test-unit: ## Run unit test
	$(info --- 🐍 Run Python test-unit ---)
	@poetry run python -m pytest

.PHONY: check-data
check-data: ## Check data of Tracarbon
	$(info --- 📍 Checking data ---)
	@poetry run python scripts/check_data.py
	@echo "👍"

.PHONY: build-documentation
build-documentation: ## Build documentation with Sphinx
	$(info --- 📚 Run build of the Sphinx documentation ---)
	@poetry run sphinx-build -Wn -b html -d ./docs/build/doctrees ./docs/source ./docs/build/html

.PHONY: publish
publish: ## Publish to Pypi
	$(info --- 📄 Run Publish to Pypi ---)
	@poetry publish --build --username "${PYPI_USERNAME}" --password "${PYPI_PASSWORD}"

.PHONY: help
help: ## List the rules
	grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'