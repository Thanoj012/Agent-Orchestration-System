.PHONY: up down test seed
up:
	docker compose up --build
down:
	docker compose down
seed:
	docker compose exec worker python -m app.cli seed-memory
test:
	pytest -q
