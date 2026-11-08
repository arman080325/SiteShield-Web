.PHONY: dev test lint fmt backend-test frontend-test

dev:
	docker compose up --build

test: backend-test frontend-test

backend-test:
	cd backend && pytest -v

frontend-test:
	cd frontend && npm run build

lint:
	cd backend && ruff check .
	cd frontend && npm run lint

fmt:
	cd backend && ruff format .
