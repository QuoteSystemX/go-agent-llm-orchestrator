BIN     := bin
NAME    := mcp-server
OS      := $(shell go env GOOS)
ARCH    := $(shell go env GOARCH)
LDFLAGS := -ldflags="-s -w"
# Isolate from parent go.work so mcp-server is always a standalone module
export GOWORK := off

.PHONY: build deps clean db-up db-down db-logs db-reset

## build: compile for the current platform
build: deps
	@mkdir -p $(BIN)
	go build $(LDFLAGS) -o $(BIN)/$(NAME) .
	@echo "Built: $(BIN)/$(NAME)"

## deps: fetch and tidy dependencies
deps:
	go mod download
	go mod tidy

## clean: remove compiled binaries
clean:
	rm -rf $(BIN)

## db-up: start a local Postgres for dev/tests (docker-compose.yml), matching both
## testutil_test.go's default DSN and CI's Postgres service (docker-build-push.yml) — no
## external repo needed to run `go test ./...` locally.
db-up:
	docker compose up -d postgres
	@echo "Waiting for Postgres..."
	@i=0; \
	until docker compose exec -T postgres pg_isready -U mcpkit >/dev/null 2>&1; do \
		i=$$((i+1)); \
		if [ $$i -ge 30 ]; then \
			echo "Postgres did not become ready after 30s — check 'docker compose logs postgres' (possible port 5432 conflict with another local Postgres)." >&2; \
			exit 1; \
		fi; \
		sleep 1; \
	done
	@echo "Postgres ready at postgres://mcpkit:mcpkit@localhost:5432/mcpkit?sslmode=disable"

## db-down: stop and remove the local Postgres container (data volume persists)
db-down:
	docker compose down

## db-reset: stop the container AND delete its data volume — full clean slate
db-reset:
	docker compose down -v

## db-logs: tail the local Postgres container's logs
db-logs:
	docker compose logs -f postgres
