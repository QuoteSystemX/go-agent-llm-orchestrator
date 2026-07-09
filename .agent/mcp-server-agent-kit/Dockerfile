# NOTE: build context must be the REPOSITORY ROOT, not this directory
# (docker build -f .agent/mcp-server-agent-kit/Dockerfile .).
# The runtime image bakes in the full .agent/ tree so discovery tools
# (agents_load, skills_load, workflows_list, ...) can serve content in
# environments without a mounted checkout (e.g. Kubernetes).
FROM golang:1.26-alpine AS build
WORKDIR /app
COPY .agent/mcp-server-agent-kit/go.mod .agent/mcp-server-agent-kit/go.sum ./
RUN go mod download
COPY .agent/mcp-server-agent-kit/ ./
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o mcp-server .

FROM gcr.io/distroless/static:nonroot
WORKDIR /app
COPY .agent/ /app/.agent/
COPY --from=build /app/mcp-server /mcp-server
ENV PROJECT_ROOT=/app
ENTRYPOINT ["/mcp-server"]
CMD ["--mode=http", "--port=3200"]
