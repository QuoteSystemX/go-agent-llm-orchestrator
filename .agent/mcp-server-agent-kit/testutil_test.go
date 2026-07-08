package main

import (
	"database/sql"
	"fmt"
	"net/url"
	"os"
	"testing"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib"
)

// testAdminPgURL returns the connection string used to create/drop per-test
// databases. Override with TEST_PG_URL (CI sets this to the service
// container); defaults to the docker-compose Postgres started by `make
// db-up` in the main multica repo, since that's what local dev already has
// running.
func testAdminPgURL() string {
	if v := os.Getenv("TEST_PG_URL"); v != "" {
		return v
	}
	return "postgres://multica:multica@localhost:5432/multica?sslmode=disable"
}

// dsnWithDatabase returns dsn with its path replaced by /dbName.
func dsnWithDatabase(dsn, dbName string) (string, error) {
	u, err := url.Parse(dsn)
	if err != nil {
		return "", err
	}
	u.Path = "/" + dbName
	return u.String(), nil
}

// newTestDB creates a throwaway Postgres database, runs InitDB's migrations
// against it, and drops it on test cleanup. Production InitDB is
// Postgres-only (no SQLite fallback since the storage migration), so any
// test exercising *DB behavior needs a real server connection — this is
// that connection, isolated per test so tests can run concurrently and
// never touch the shared multica dev database.
//
// Skips (not fails) when no reachable Postgres is configured, so `go test`
// still succeeds in environments without a database (e.g. `go build`
// sanity checks) while running for real wherever TEST_PG_URL or the local
// dev Postgres is available.
func newTestDB(t *testing.T) *DB {
	t.Helper()

	adminDSN := testAdminPgURL()
	admin, err := sql.Open("pgx", adminDSN)
	if err != nil {
		t.Skipf("test postgres unavailable, skipping: %v", err)
	}
	defer admin.Close()
	if err := admin.Ping(); err != nil {
		t.Skipf("test postgres unreachable at %s, skipping: %v", adminDSN, err)
	}

	dbName := fmt.Sprintf("mcpkit_test_%d", time.Now().UnixNano())
	if _, err := admin.Exec("CREATE DATABASE " + dbName); err != nil {
		t.Fatalf("failed to create test database %s: %v", dbName, err)
	}
	t.Cleanup(func() {
		// Reconnect fresh: can't DROP DATABASE from a pool that still holds
		// a connection to it.
		cleanup, err := sql.Open("pgx", adminDSN)
		if err != nil {
			return
		}
		defer cleanup.Close()
		_, _ = cleanup.Exec("DROP DATABASE IF EXISTS " + dbName)
	})

	testDSN, err := dsnWithDatabase(adminDSN, dbName)
	if err != nil {
		t.Fatalf("failed to build test DSN: %v", err)
	}
	db, err := InitDB(testDSN)
	if err != nil {
		t.Fatalf("InitDB failed for test database %s: %v", dbName, err)
	}
	t.Cleanup(func() { _ = db.conn.Close() })
	return db
}
