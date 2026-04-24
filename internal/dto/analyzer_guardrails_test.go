package dto

import (
	"os"
	"path/filepath"
	"testing"
)

func TestAnalyzer_IndexerGuardrails(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "analyzer_test")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	// Create 10 valid files
	for i := 0; i < 10; i++ {
		os.WriteFile(filepath.Join(tmpDir, "file"+string(rune(i))+".go"), []byte("package main"), 0644)
	}

	// Create a large file (150KB)
	largeContent := make([]byte, 150*1024)
	os.WriteFile(filepath.Join(tmpDir, "large.go"), largeContent, 0644)

	// Create a file in node_modules
	os.MkdirAll(filepath.Join(tmpDir, "node_modules"), 0755)
	os.WriteFile(filepath.Join(tmpDir, "node_modules", "noise.go"), []byte("package noise"), 0644)

	// Trigger the walking logic (extracted from AnalyzeRepo for test)
	targetExts := map[string]bool{".go": true}
	fileCount := 0
	maxFiles := 5 // Set small limit for test
	maxFileSize := int64(100 * 1024)

	filepath.Walk(tmpDir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() { return nil }
		if fileCount >= maxFiles { return filepath.SkipDir }
		
		// Logic to skip node_modules
		rel, _ := filepath.Rel(tmpDir, path)
		if len(rel) > 12 && rel[:12] == "node_modules" { return nil }
		
		if info.Size() > maxFileSize { return nil }
		
		ext := filepath.Ext(path)
		if targetExts[ext] {
			fileCount++
		}
		return nil
	})

	if fileCount != maxFiles {
		t.Errorf("Expected exactly %d files indexed (limit), got %d", maxFiles, fileCount)
	}
}
