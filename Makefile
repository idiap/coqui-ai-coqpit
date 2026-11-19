.DEFAULT_GOAL := help
.PHONY: lint install help

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

test:	## run tests.
	uv run coverage run && uv run coverage report

lint:	## run ruff format and lint
	uv run prek run --all-files

install:	## install 👩‍✈️ Coqpit for development.
	uv sync --all-extras
	uv run prek install

testlint: test lint
