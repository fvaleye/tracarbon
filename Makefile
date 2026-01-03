.DEFAULT_GOAL := help

.PHONY: init
init: ## Init the requirements
	$(info --- 🖥 Init dependencies ---)
	@uv venv
	@uv pip install -e '.[all,dev]'

.PHONY: format
format: ## Format the code
	$(info --- 🐍 Check Python format ---)
	pre-commit run -a

.PHONY: typecheck
typecheck: ## Run type checking with ty
	$(info --- 🐍 Type checking Python ---)
	@uv run ty check tracarbon/

.PHONY: security
security: ## Run security checks
	$(info --- 🐍 Security Python ---)
	@uv run bandit -c pyproject.toml -r .

.PHONY: complexity
complexity: ## Run complexity checks
	$(info --- 🐍 Complexity Python ---)
	@uv run radon cc -a tracarbon/

.PHONY: test-unit
test-unit: ## Run unit test
	$(info --- 🐍 Run Python test-unit ---)
	@uv run python -m pytest

.PHONY: check-data
check-data: ## Check data of Tracarbon
	$(info --- 📍 Checking data ---)
	@uv run python scripts/check_data.py
	@echo "👍"

.PHONY: build-documentation
build-documentation: ## Build documentation with Sphinx
	$(info --- 📚 Run build of the Sphinx documentation ---)
	@uv run sphinx-build -Wn -b html -d ./docs/build/doctrees ./docs/source ./docs/build/html

.PHONY: help
help: ## List the rules
	grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
