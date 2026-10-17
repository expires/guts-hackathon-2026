# Lifeline. BOSS-owned. Run `make help`.
SHELL := /bin/bash
API := services/api
IOS := apps/ios
UV := uv run --project $(API) --directory $(API)
SIM ?= iPhone 18 Pro Max
COMPOSE := docker compose
# CLI iOS builds never share Xcode GUI DerivedData (path is relative to $(IOS)).
IOS_DD := .build/DerivedData

.PHONY: ios-record-mock ios-device ios-playground help up down logs ps test test-stack lint fmt contract ios-gen ios-build ios-test ios-screens demo-seed secrets-scan dev

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-14s %s\n",$$1,$$2}'

up: ## Build and start api, worker, postgres, redis (waits for health)
	@test -f .env || cp .env.example .env
	$(COMPOSE) up -d --build --wait
	@curl -fsS http://localhost:8000/v1/health && echo

down: ## Stop the stack
	$(COMPOSE) down

logs: ## Tail stack logs
	$(COMPOSE) logs -f --tail=100

ps: ## Stack status
	$(COMPOSE) ps

dev: ## Run the API locally with reload (no Docker; in-memory store, fakeredis)
	cd $(API) && APP_ENV=test uv run uvicorn lifeline_api.main:app --reload --port 8000

test: ## Python tests: unit, contract, integration (offline, recorded fixtures)
	cd $(API) && uv run pytest

test-stack: ## Contract tests against the running docker stack
	cd $(API) && LIFELINE_BASE_URL=http://localhost:8000 uv run pytest tests/contract -q

lint: ## ruff + mypy strict
	cd $(API) && uv run ruff check . && uv run mypy

fmt: ## Auto-fix lint
	cd $(API) && uv run ruff check --fix . && uv run ruff format .

contract: ## Regenerate contracts/openapi.yaml from lifeline_contracts
	cd $(API) && uv run python ../../contracts/build_openapi.py

ios-gen: ## Generate the Xcode project with XcodeGen
	cp contracts/openapi.yaml $(IOS)/Lifeline/Networking/openapi.yaml && cd $(IOS) && xcodegen generate --quiet

ios-build: ios-gen ## Build the iOS app for the simulator
	cd $(IOS) && ../../tools/with-ios-lock.sh xcodebuild -project Lifeline.xcodeproj -scheme Lifeline -destination 'platform=iOS Simulator,name=$(SIM)' -derivedDataPath $(IOS_DD) -skipPackagePluginValidation -skipMacroValidation build | tail -20

ios-test: ios-gen ## Swift Testing + UI tests on the simulator
	cd $(IOS) && ../../tools/with-ios-lock.sh xcodebuild -project Lifeline.xcodeproj -scheme Lifeline -destination 'platform=iOS Simulator,name=$(SIM)' -derivedDataPath $(IOS_DD) -skipPackagePluginValidation -skipMacroValidation test | tail -40

ios-playground: ios-gen ## Build the Playground scheme (Mock config) for the simulator
	cd $(IOS) && ../../tools/with-ios-lock.sh xcodebuild -project Lifeline.xcodeproj -scheme Playground -configuration Mock -destination 'platform=iOS Simulator,name=$(SIM)' -derivedDataPath $(IOS_DD) -skipPackagePluginValidation -skipMacroValidation build | tail -20

ios-record-mock: ## Record real API responses for the iOS Mock config (stack must be up)
	cd $(API) && uv run python ../../tools/record_mock.py

ios-device: ## (CONFIG=Mock|Demo|Dev CHECKPOINT=n FEATURES=..) Build and install on the iPhone for the connected iPhone, install, launch (needs Config/Local.xcconfig team)
	tools/ios-device.sh

demo-seed: ## Load demo lives and rooms into the running stack
	$(COMPOSE) exec -T api python -m seed.load

secrets-scan: ## gitleaks over the working tree (no git history needed)
	gitleaks dir . --no-banner --redact -c .gitleaks.toml
