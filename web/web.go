package web

import "embed"

// StaticFiles contains the dashboard frontend assets
//go:embed static/*
var StaticFiles embed.FS
