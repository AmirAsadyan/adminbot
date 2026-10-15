.PHONY: help install migrate test run clean superuser

help:
	@echo "AdminBot - Development Commands"
	@echo ""
	@echo "  make install      Install dependencies"
	@echo "  make migrate      Run database migrations"
	@echo "  make superuser    Create a Django superuser"
	@echo "  make test         Run tests"
	@echo "  make run          Start development server"
	@echo "  make clean        Remove generated files"

install:
	pip install -r requirements.txt

migrate:
	python manage.py migrate

superuser:
	python manage.py createsuperuser

test:
	python manage.py test

run:
	python manage.py runserver

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -f db.sqlite3
