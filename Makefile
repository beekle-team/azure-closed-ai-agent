.PHONY: bootstrap up up-emulators down logs agent-test seed

bootstrap:
	test -f .env || cp .env.example .env
	bash scripts/bootstrap-admin.sh
	test -f admin/src/.env || cp admin/src/.env.example admin/src/.env
	docker compose build
	docker compose up -d postgres redis
	docker compose run --rm admin-app composer install --no-interaction
	docker compose run --rm admin-app php artisan key:generate --force
	docker compose run --rm admin-app php artisan migrate --force
	docker compose run --rm admin-app php artisan db:seed --force
	docker compose run --rm agent python -m closed_agent.graph.seed

up:
	docker compose up -d --build

up-emulators:
	docker compose --profile emulators up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

agent-test:
	docker compose run --rm agent pytest

seed:
	docker compose run --rm agent python -m closed_agent.graph.seed
