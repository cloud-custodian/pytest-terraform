

lint:
	ruff check pytest_terraform tests

coverage:
	coverage run --source pytest_terraform -m pytest tests
	coverage report ${COVERAGE_REPORT_FLAGS}
