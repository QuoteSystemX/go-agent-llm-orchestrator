FROM golang:1.23-alpine AS build
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o mcp-server .

FROM gcr.io/distroless/static:nonroot
COPY --from=build /app/mcp-server /mcp-server
ENTRYPOINT ["/mcp-server"]
CMD ["--mode=http", "--port=3200"]
