.PHONY: setup check format lint type test

setup:
	uv sync --group dev

format:
	uv run ruff format .

lint:
	uv run ruff check .

type:
	uv run ty check .

test:
	uv run pytest --cov=SocketMock --cov-report=term-missing

check: format lint type test
