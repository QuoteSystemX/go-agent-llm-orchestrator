BIN     := bin
NAME    := mcp-llm-broker
LDFLAGS := -ldflags="-s -w"
export GOWORK := off

.PHONY: build deps clean build-darwin build-linux all

## build: compile for the current platform (fast dev loop)
build: deps
	@mkdir -p $(BIN)
	go build $(LDFLAGS) -o $(BIN)/$(NAME) .
	@echo "Built: $(BIN)/$(NAME)"

## build-darwin: build amd64 + arm64 and lipo them into a universal binary
build-darwin: deps
	@mkdir -p $(BIN)
	GOOS=darwin GOARCH=amd64 go build $(LDFLAGS) -o $(BIN)/$(NAME)-darwin-amd64 .
	GOOS=darwin GOARCH=arm64 go build $(LDFLAGS) -o $(BIN)/$(NAME)-darwin-arm64 .
	@if command -v lipo >/dev/null 2>&1; then \
		lipo -create -output $(BIN)/$(NAME)-darwin $(BIN)/$(NAME)-darwin-amd64 $(BIN)/$(NAME)-darwin-arm64; \
		rm $(BIN)/$(NAME)-darwin-amd64 $(BIN)/$(NAME)-darwin-arm64; \
		echo "Built: $(BIN)/$(NAME)-darwin (universal fat binary)"; \
	else \
		echo "Built: $(BIN)/$(NAME)-darwin-amd64 and $(BIN)/$(NAME)-darwin-arm64 (lipo not available)"; \
	fi

## build-linux: build linux amd64 binary
build-linux: deps
	@mkdir -p $(BIN)
	GOOS=linux GOARCH=amd64 go build $(LDFLAGS) -o $(BIN)/$(NAME)-linux-amd64 .
	@echo "Built: $(BIN)/$(NAME)-linux-amd64"

## all: build all platforms
all: build-darwin build-linux

deps:
	go mod download
	go mod tidy

clean:
	rm -rf $(BIN)
