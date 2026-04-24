package dto

import (
	"context"
	"database/sql"
	"go-agent-llm-orchestrator/internal/db"
)

type Template struct {
	Name      string `json:"name"`
	Content   string `json:"content"`
	UpdatedAt string `json:"updated_at"`
}

type TemplateManager struct {
	db *db.DB
}

func NewTemplateManager(database *db.DB) *TemplateManager {
	return &TemplateManager{db: database}
}

func (m *TemplateManager) ListTemplates(ctx context.Context) ([]Template, error) {
	rows, err := m.db.QueryContext(ctx, "SELECT name, content, updated_at FROM templates ORDER BY name")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var templates []Template
	for rows.Next() {
		var t Template
		if err := rows.Scan(&t.Name, &t.Content, &t.UpdatedAt); err != nil {
			continue
		}
		templates = append(templates, t)
	}
	return templates, nil
}

func (m *TemplateManager) GetTemplate(ctx context.Context, name string) (*Template, error) {
	var t Template
	err := m.db.QueryRowContext(ctx, "SELECT name, content, updated_at FROM templates WHERE name = ?", name).
		Scan(&t.Name, &t.Content, &t.UpdatedAt)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, err
	}
	return &t, nil
}

func (m *TemplateManager) SaveTemplate(ctx context.Context, name, content string) error {
	_, err := m.db.ExecContext(ctx, 
		"INSERT OR REPLACE INTO templates (name, content, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)", 
		name, content)
	return err
}

func (m *TemplateManager) DeleteTemplate(ctx context.Context, name string) error {
	_, err := m.db.ExecContext(ctx, "DELETE FROM templates WHERE name = ?", name)
	return err
}
