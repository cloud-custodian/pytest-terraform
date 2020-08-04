

lint:
	pre-commit run --all-files

coverage:
	coverage run --source pytest_terraform -m pytest tests
	coverage report ${COVERAGE_REPORT_FLAGS}
