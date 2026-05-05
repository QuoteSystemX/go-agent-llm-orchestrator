BIN     := bin
NAME    := local-skill-server
OS      := $(shell go env GOOS)
ARCH    := $(shell go env GOARCH)
LDFLAGS := -ldflags="-s -w"
# Isolate from parent go.work so skill-server is always a standalone module
export GOWORK := off

.PHONY: build build-all build-linux build-darwin build-darwin-universal deps clean

## build: compile for the current platform
build: deps
	@mkdir -p $(BIN)
	go build $(LDFLAGS) -o $(BIN)/$(NAME)-$(OS)-$(ARCH) .
	@echo "Built: $(BIN)/$(NAME)-$(OS)-$(ARCH)"

## build-all: cross-compile for all supported platforms
build-all: deps
	@mkdir -p $(BIN)
	GOOS=linux  GOARCH=amd64 go build $(LDFLAGS) -o $(BIN)/$(NAME)-linux-amd64   .
	GOOS=linux  GOARCH=arm64 go build $(LDFLAGS) -o $(BIN)/$(NAME)-linux-arm64   .
	GOOS=darwin GOARCH=amd64 go build $(LDFLAGS) -o $(BIN)/$(NAME)-darwin-amd64  .
	GOOS=darwin GOARCH=arm64 go build $(LDFLAGS) -o $(BIN)/$(NAME)-darwin-arm64  .
	@echo "All binaries built in $(BIN)/"

## build-darwin: cross-compile only darwin targets (arch-specific)
build-darwin: deps
	@mkdir -p $(BIN)
	GOOS=darwin GOARCH=amd64 go build $(LDFLAGS) -o $(BIN)/$(NAME)-darwin-amd64 .
	GOOS=darwin GOARCH=arm64 go build $(LDFLAGS) -o $(BIN)/$(NAME)-darwin-arm64 .

## build-darwin-universal: build a macOS universal (fat) binary via lipo
build-darwin-universal: build-darwin
	lipo -create -output $(BIN)/$(NAME)-darwin \
		$(BIN)/$(NAME)-darwin-amd64 \
		$(BIN)/$(NAME)-darwin-arm64
	@echo "Universal binary: $(BIN)/$(NAME)-darwin"

## build-linux: cross-compile only linux targets (used in CI)
build-linux: deps
	@mkdir -p $(BIN)
	GOOS=linux GOARCH=amd64 go build $(LDFLAGS) -o $(BIN)/$(NAME)-linux-amd64 .
	GOOS=linux GOARCH=arm64 go build $(LDFLAGS) -o $(BIN)/$(NAME)-linux-arm64 .

## deps: fetch and tidy dependencies
deps:
	go mod download
	go mod tidy

## clean: remove compiled binaries
clean:
	rm -rf $(BIN)
