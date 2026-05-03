BIN     := bin
NAME    := mcp-server
OS      := $(shell go env GOOS)
ARCH    := $(shell go env GOARCH)
LDFLAGS := -ldflags="-s -w"
# Isolate from parent go.work so mcp-server is always a standalone module
export GOWORK := off

.PHONY: build deps clean

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
