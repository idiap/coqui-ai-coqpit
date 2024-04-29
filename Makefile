.DEFAULT_GOAL := help
.PHONY: lint install help

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

test:	## run tests.
	coverage run -m pytest && coverage report --show-missing

lint:	## run ruff format and lint
	pre-commit run --all-files

install:	## install 👩‍✈️ Coqpit for development.
	pip install -e .
	pre-commit install

testlint: test lint
