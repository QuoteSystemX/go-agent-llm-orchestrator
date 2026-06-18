package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"os"
	"os/exec"
	"regexp"
	"runtime"
	"strings"
	"time"
)

func getAvailableMemory() uint64 {
	if runtime.GOOS == "linux" {
		data, err := os.ReadFile("/proc/meminfo")
		if err == nil {
			lines := strings.Split(string(data), "\n")
			for _, line := range lines {
				if strings.HasPrefix(line, "MemAvailable:") {
					fields := strings.Fields(line)
					if len(fields) >= 2 {
						var val uint64
						fmt.Sscanf(fields[1], "%d", &val)
						return val * 1024 // kB to bytes
					}
				}
			}
		}
	} else if runtime.GOOS == "darwin" {
		out, err := exec.Command("sysctl", "-n", "hw.memsize").Output()
		if err == nil {
			var total uint64
			_, err := fmt.Sscanf(strings.TrimSpace(string(out)), "%d", &total)
			if err == nil {
				// Conservative estimation: 60% of total memory is free/available
				return uint64(float64(total) * 0.6)
			}
		}
	}
	return 8 * 1024 * 1024 * 1024 // Fallback to 8GB
}

func parseModelSize(modelName string) float64 {
	re := regexp.MustCompile(`(?i)(\d+(\.\d+)?)[b]`)
	matches := re.FindStringSubmatch(modelName)
	if len(matches) >= 2 {
		var size float64
		_, err := fmt.Sscanf(matches[1], "%f", &size)
		if err == nil {
			return size
		}
	}
	return 7.0 // Default fallback size (e.g. 7B)
}

func isHardwareMemoryLimitOk(modelName string) bool {
	size := parseModelSize(modelName)
	// RAM_required = Size * 0.5 GB + 2 GB
	requiredBytes := uint64(size*0.5*1024*1024*1024) + 2*1024*1024*1024
	availableBytes := getAvailableMemory()
	return requiredBytes <= uint64(float64(availableBytes)*0.85)
}

func tokenizeAndNormalize(s string) []string {
	s = strings.ToLower(s)
	s = strings.Map(func(r rune) rune {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') {
			return r
		}
		return ' '
	}, s)

	rawWords := strings.Fields(s)
	var words []string
	for _, w := range rawWords {
		w = strings.TrimSpace(w)
		if w != "" && w != "instruct" && w != "gguf" {
			words = append(words, w)
		}
	}
	return words
}

func tokenOverlap(target, candidate string) float64 {
	tWords := tokenizeAndNormalize(target)
	cWords := tokenizeAndNormalize(candidate)

	if len(tWords) == 0 {
		return 0.0
	}

	matches := 0
	for _, tw := range tWords {
		for _, cw := range cWords {
			if tw == cw {
				matches++
				break
			}
		}
	}
	return float64(matches) / float64(len(tWords))
}

func levenshteinDistance(s, t string) int {
	d := make([][]int, len(s)+1)
	for i := range d {
		d[i] = make([]int, len(t)+1)
		d[i][0] = i
	}
	for j := range d[0] {
		d[0][j] = j
	}
	for i := 1; i <= len(s); i++ {
		for j := 1; j <= len(t); j++ {
			cost := 1
			if s[i-1] == t[j-1] {
				cost = 0
			}
			d[i][j] = minInt(d[i-1][j]+1, minInt(d[i][j-1]+1, d[i-1][j-1]+cost))
		}
	}
	return d[len(s)][len(t)]
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func getNormalizedLevenshtein(s, t string) float64 {
	sNorm := strings.Join(tokenizeAndNormalize(s), "")
	tNorm := strings.Join(tokenizeAndNormalize(t), "")
	if len(sNorm) == 0 && len(tNorm) == 0 {
		return 1.0
	}
	maxLen := len(sNorm)
	if len(tNorm) > maxLen {
		maxLen = len(tNorm)
	}
	dist := levenshteinDistance(sNorm, tNorm)
	return 1.0 - float64(dist)/float64(maxLen)
}

func getQuantizationScore(name string) float64 {
	nameLower := strings.ToLower(name)
	if strings.Contains(nameLower, "q4_k_m") || strings.Contains(nameLower, "iq4_xs") || strings.Contains(nameLower, "q4_k_s") {
		return 10.0
	}
	if strings.Contains(nameLower, "q5_k_m") || strings.Contains(nameLower, "q5_k_s") {
		return 8.0
	}
	if strings.Contains(nameLower, "q3_k_l") || strings.Contains(nameLower, "q3_k_m") {
		return 6.0
	}
	if strings.Contains(nameLower, "q8_0") || strings.Contains(nameLower, "q8") {
		return 2.0
	}
	if strings.Contains(nameLower, "q2_k") || strings.Contains(nameLower, "q2") {
		return 1.0
	}
	return 5.0 // default
}

func calculateMCDAScore(target, candidate string) float64 {
	if !isHardwareMemoryLimitOk(candidate) {
		return -1e9 // Disqualified
	}

	overlap := tokenOverlap(target, candidate)
	lev := getNormalizedLevenshtein(target, candidate)
	sName := 0.7*overlap + 0.3*lev

	sQuant := getQuantizationScore(candidate) / 10.0

	targetSize := parseModelSize(target)
	candidateSize := parseModelSize(candidate)
	sizeDiff := math.Abs(targetSize - candidateSize)
	sHW := 1.0 / (1.0 + sizeDiff)

	wName := 0.5
	wHW := 0.3
	wQuant := 0.2
	return wName*sName + wHW*sHW + wQuant*sQuant
}

func (b *BrokerServer) selectBestRegistryModel(target string, candidates []string) (string, error) {
	if len(candidates) == 0 {
		return "", fmt.Errorf("empty registry candidates list")
	}

	var bestModel string
	bestScore := -1e8

	for _, cand := range candidates {
		score := calculateMCDAScore(target, cand)
		if score > bestScore && score > -1e7 {
			bestScore = score
			bestModel = cand
		}
	}

	if bestModel == "" {
		return "", fmt.Errorf("no suitable registry model matches hardware limits or criteria")
	}
	return bestModel, nil
}

func (b *BrokerServer) performModelPull(model string, rules *RouterRules, env EnvironmentInfo) error {
	var baseURL string
	if b.urlOverrides != nil {
		if override, ok := b.urlOverrides["ollama"]; ok {
			baseURL = override
		}
	}
	if baseURL == "" {
		baseURL = b.getOllamaURL(env)
	}
	url := fmt.Sprintf("%s/api/pull", baseURL)

	payload := map[string]interface{}{
		"name":   model,
		"stream": false,
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Minute)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("status code %d: %s", resp.StatusCode, string(bodyBytes))
	}

	return nil
}

func (b *BrokerServer) triggerBackgroundPull(model string, rules *RouterRules, env EnvironmentInfo) {
	b.isPullingActiveMu.Lock()
	if b.isPullingActive {
		b.isPullingActiveMu.Unlock()
		return
	}

	b.pullingStatesMu.Lock()
	if b.pullingStates == nil {
		b.pullingStates = make(map[string]string)
	}
	status := b.pullingStates[model]
	if status == "downloading" || status == "completed" {
		b.pullingStatesMu.Unlock()
		b.isPullingActiveMu.Unlock()
		return
	}
	b.pullingStates[model] = "downloading"
	b.pullingStatesMu.Unlock()

	b.isPullingActive = true
	b.isPullingActiveMu.Unlock()

	go func() {
		defer func() {
			b.isPullingActiveMu.Lock()
			b.isPullingActive = false
			b.isPullingActiveMu.Unlock()
		}()

		err := b.performModelPull(model, rules, env)

		b.pullingStatesMu.Lock()
		if err != nil {
			b.pullingStates[model] = "failed"
			fmt.Fprintf(os.Stderr, "mcp-llm-broker: failed to pull model %s: %v\n", model, err)
		} else {
			b.pullingStates[model] = "completed"
			fmt.Fprintf(os.Stderr, "mcp-llm-broker: successfully pulled model %s\n", model)
		}
		b.pullingStatesMu.Unlock()
	}()
}
