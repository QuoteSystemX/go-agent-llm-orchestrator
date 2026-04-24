package dto

import (
	"context"
	"testing"

	"go-agent-llm-orchestrator/internal/db"
)

func TestTemplateManager(t *testing.T) {
	database, err := db.InitDB(":memory:")
	if err != nil {
		t.Fatalf("failed to init db: %v", err)
	}
	defer database.Close()

	mgr := NewTemplateManager(database)
	ctx := context.Background()

	// Test Save
	err = mgr.SaveTemplate(ctx, "test-tpl", "content here")
	if err != nil {
		t.Errorf("failed to save template: %v", err)
	}

	// Test Get
	tpl, err := mgr.GetTemplate(ctx, "test-tpl")
	if err != nil {
		t.Errorf("failed to get template: %v", err)
	}
	if tpl == nil || tpl.Content != "content here" {
		t.Errorf("unexpected template content: %v", tpl)
	}

	// Test List
	list, err := mgr.ListTemplates(ctx)
	if err != nil {
		t.Errorf("failed to list templates: %v", err)
	}
	if len(list) < 1 {
		t.Errorf("expected at least 1 template, got %d", len(list))
	}

	// Test Delete
	err = mgr.DeleteTemplate(ctx, "test-tpl")
	if err != nil {
		t.Errorf("failed to delete template: %v", err)
	}

	tpl, _ = mgr.GetTemplate(ctx, "test-tpl")
	if tpl != nil {
		t.Error("expected template to be deleted")
	}
}
