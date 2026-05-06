package main

import (
	"context"
	"fmt"
	"strings"

	"github.com/mark3labs/mcp-go/mcp"
)

func (h *handler) registerHook(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	uri, _ := req.RequireString("uri")
	event, _ := req.RequireString("event")
	script, _ := req.RequireString("script")
	
	if err := h.db.AddHook(uri, event, script); err != nil {
		return mcp.NewToolResultError("Failed to add hook: " + err.Error()), nil
	}
	return mcp.NewToolResultText(fmt.Sprintf("Hook registered: %s for %s on %s", script, uri, event)), nil // nosec
}

func (h *handler) listHooks(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	hooks, err := h.db.GetHooks()
	if err != nil {
		return nil, err
	}
	var lines []string
	for _, hook := range hooks {
		lines = append(lines, fmt.Sprintf("%s [%s] -> %s", hook.ResourceURI, hook.EventType, hook.ScriptPath)) // nosec
	}
	if len(lines) == 0 {
		return mcp.NewToolResultText("No active hooks."), nil
	}
	return mcp.NewToolResultText(strings.Join(lines, "\n")), nil
}

func (h *handler) removeHook(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	uri, _ := req.RequireString("uri")
	event, _ := req.RequireString("event")
	if err := h.db.RemoveHook(uri, event); err != nil {
		return mcp.NewToolResultError("Failed to remove hook: " + err.Error()), nil
	}
	return mcp.NewToolResultText("Hook removed."), nil
}
