# Build stage
FROM golang:1.25-alpine AS builder

WORKDIR /app

# Install build dependencies (if any)
RUN apk add --no-cache git

# Copy dependencies
COPY go.mod go.sum ./
RUN go mod download

# Copy source
COPY . .

# Build the application
# CGO_ENABLED=0 ensures we use the pure-go sqlite driver
RUN CGO_ENABLED=0 GOOS=linux go build -o orchestrator cmd/orchestrator/main.go

# Final stage
FROM alpine:latest

# Security: Add a non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

# Copy the binary from builder
COPY --from=builder /app/orchestrator .

# Create data directory for SQLite and set permissions
RUN mkdir -p /app/data && chown -R appuser:appgroup /app/data

# Use the non-root user
USER appuser

# Environment defaults
ENV DB_PATH=/app/data/tasks.db

CMD ["./orchestrator"]
