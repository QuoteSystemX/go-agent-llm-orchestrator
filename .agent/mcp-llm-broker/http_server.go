package main

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"
)

// ---------------------------------------------------------------------------
// OpenAI-compatible request/response types
// ---------------------------------------------------------------------------

// Tool represents an OpenAI-format tool definition.
type Tool struct {
	Type     string       `json:"type"` // "function"
	Function ToolFunction `json:"function"`
}

type ToolFunction struct {
	Name        string          `json:"name"`
	Description string          `json:"description,omitempty"`
	Parameters  json.RawMessage `json:"parameters,omitempty"`
}

// ToolCall represents a tool call made by the model (OpenAI format).
type ToolCall struct {
	ID       string           `json:"id"`
	Type     string           `json:"type"` // "function"
	Function ToolCallFunction `json:"function"`
	Index    int              `json:"index,omitempty"`
}

type ToolCallFunction struct {
	Name      string `json:"name"`
	Arguments string `json:"arguments"` // JSON string
}

type ChatCompletionRequest struct {
	Model       string        `json:"model"`
	Messages    []ChatMessage `json:"messages"`
	Stream      bool          `json:"stream,omitempty"`
	Temperature *float64      `json:"temperature,omitempty"`
	Tools       []Tool        `json:"tools,omitempty"`
	ToolChoice  interface{}   `json:"tool_choice,omitempty"`
}

// ChatMessage supports string content, array-of-parts, and tool_calls.
type ChatMessage struct {
	Role       string     `json:"-"` // populated by UnmarshalJSON
	Content    string     `json:"-"` // text content
	ToolCalls  []ToolCall `json:"-"` // for assistant messages
	ToolCallID string     `json:"-"` // for tool result messages (role="tool")
}

func (m *ChatMessage) UnmarshalJSON(data []byte) error {
	type raw struct {
		Role       string          `json:"role"`
		Content    json.RawMessage `json:"content"`
		ToolCalls  json.RawMessage `json:"tool_calls"`
		ToolCallID string          `json:"tool_call_id"`
	}
	var r raw
	if err := json.Unmarshal(data, &r); err != nil {
		return err
	}
	m.Role = r.Role
	m.ToolCallID = r.ToolCallID

	// Parse content — may be null, string, or array-of-parts.
	if len(r.Content) > 0 && string(r.Content) != "null" {
		var s string
		if err := json.Unmarshal(r.Content, &s); err == nil {
			m.Content = s
		} else {
			var parts []struct {
				Type string `json:"type"`
				Text string `json:"text"`
			}
			if err := json.Unmarshal(r.Content, &parts); err == nil {
				var sb strings.Builder
				for _, p := range parts {
					if p.Type == "text" {
						sb.WriteString(p.Text)
					}
				}
				m.Content = sb.String()
			}
		}
	}

	// Parse tool_calls for assistant messages.
	if len(r.ToolCalls) > 0 && string(r.ToolCalls) != "null" {
		_ = json.Unmarshal(r.ToolCalls, &m.ToolCalls)
	}
	return nil
}

type ChatCompletionResponse struct {
	ID      string              `json:"id"`
	Object  string              `json:"object"`
	Created int64               `json:"created"`
	Model   string              `json:"model"`
	Choices []ResponseChoice    `json:"choices"`
	Usage   *ResponseUsage      `json:"usage,omitempty"`
	Error   *ResponseError      `json:"error,omitempty"`
}

type ResponseChoice struct {
	Index        int              `json:"index"`
	Message      ResponseMessage  `json:"message"`
	FinishReason string           `json:"finish_reason"`
}

type ResponseMessage struct {
	Role      string     `json:"role"`
	Content   string     `json:"content"`
	ToolCalls []ToolCall `json:"tool_calls,omitempty"`
}

type ResponseUsage struct {
	PromptTokens     int `json:"prompt_tokens"`
	CompletionTokens int `json:"completion_tokens"`
	TotalTokens      int `json:"total_tokens"`
}

type ResponseError struct {
	Code    string `json:"code,omitempty"`
	Message string `json:"message"`
}

// SSE streaming chunk
type ChatCompletionChunk struct {
	ID      string        `json:"id"`
	Object  string        `json:"object"`
	Created int64         `json:"created"`
	Model   string        `json:"model"`
	Choices []ChunkChoice `json:"choices"`
}

type ChunkChoice struct {
	Index int          `json:"index"`
	Delta MessageDelta `json:"delta"`
	FinishReason *string `json:"finish_reason,omitempty"`
}

type MessageDelta struct {
	Role      string     `json:"role,omitempty"`
	Content   string     `json:"content,omitempty"`
	ToolCalls []ToolCall `json:"tool_calls,omitempty"`
}

// ModelObject for GET /v1/models
type ModelObject struct {
	ID       string `json:"id"`
	Object   string `json:"object"`
	OwnedBy  string `json:"owned_by"`
}

type ListModelsResponse struct {
	Object string        `json:"object"`
	Data   []ModelObject `json:"data"`
}

// ---------------------------------------------------------------------------
// Request conversion helpers
// ---------------------------------------------------------------------------

// extractPromptFromMessages extracts prompt + systemPrompt from the OpenAI messages array.
// The last user message becomes the prompt; the first system message becomes systemPrompt.
func extractPromptFromMessages(messages []ChatMessage) (prompt, systemPrompt string) {
	for _, msg := range messages {
		if msg.Role == "system" && systemPrompt == "" {
			systemPrompt = msg.Content
		}
	}
	// Last user message is the prompt
	for i := len(messages) - 1; i >= 0; i-- {
		if messages[i].Role == "user" {
			prompt = messages[i].Content
			break
		}
	}
	return
}

// ---------------------------------------------------------------------------
// Response builders
// ---------------------------------------------------------------------------

func buildChatCompletionResponse(result *ExecutionResult, usage ResponseUsage) *ChatCompletionResponse {
	now := time.Now()
	return &ChatCompletionResponse{
		ID:      fmt.Sprintf("chatcmpl-%d", now.UnixNano()),
		Object:  "chat.completion",
		Created: now.Unix(),
		Model:   result.Model,
		Choices: []ResponseChoice{{
			Index:        0,
			Message:      ResponseMessage{Role: "assistant", Content: result.Response},
			FinishReason: "stop",
		}},
		Usage: &usage,
	}
}

func buildErrorResponse(status int, msg string) *ChatCompletionResponse {
	return &ChatCompletionResponse{
		Error: &ResponseError{
			Code:    fmt.Sprintf("%d", status),
			Message: msg,
		},
	}
}

func buildTokenUsage(prompt, response string) ResponseUsage {
	pt := estimateTokenCount(prompt)
	ct := estimateTokenCount(response)
	return ResponseUsage{
		PromptTokens:     pt,
		CompletionTokens: ct,
		TotalTokens:      pt + ct,
	}
}

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

// handleChatCompletions implements POST /v1/chat/completions (OpenAI-compatible).
func (b *BrokerServer) handleChatCompletions(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		writeJSON(w, http.StatusMethodNotAllowed, buildErrorResponse(405, "method not allowed, use POST"))
		return
	}

	// Parse request body
	var req ChatCompletionRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, buildErrorResponse(400, "invalid JSON: "+err.Error()))
		return
	}

	// Extract prompt + system prompt from messages
	prompt, systemPrompt := extractPromptFromMessages(req.Messages)
	if prompt == "" {
		writeJSON(w, http.StatusBadRequest, buildErrorResponse(400, "no user message found in messages"))
		return
	}

	// Derive jsonSchema from response_format if present (simplified)
	var jsonSchema string

	ctx, cancel := context.WithTimeout(r.Context(), 300*time.Second)
	defer cancel()

	fmt.Fprintf(os.Stderr, "[DEBUG] http-server: received model=%q stream=%v msgs=%d syspromptLen=%d\n",
		req.Model, req.Stream, len(req.Messages), len(systemPrompt))
	if len(req.Messages) > 0 {
		fmt.Fprintf(os.Stderr, "[DEBUG] http-server: msgs[0].role=%q msgs[0].contentLen=%d\n",
			req.Messages[0].Role, len(req.Messages[0].Content))
	}

	if req.Stream {
		b.handleStreamingChat(w, ctx, &req, prompt, systemPrompt, jsonSchema)
		return
	}

	// Determine routing:
	//   "auto" / "" / "mcp-llm-broker/auto" → complexity-based scoring across L1–L4.
	//   "L1"/"L2"/"L3"/"L4" (or "mcp-llm-broker/L2") → pin to that tier directly.
	//   anything else → modelOverride: exact/fuzzy match then cloud fallback.

	// Strip provider prefix if present (e.g. "mcp-llm-broker/L2" → "L2")
	modelShortName := req.Model
	if idx := strings.LastIndex(modelShortName, "/"); idx >= 0 {
		modelShortName = modelShortName[idx+1:]
	}

	modelOverride := req.Model
	difficultyHint := ""
	autoMode := modelShortName == "auto" || modelShortName == ""
	tierMode := isTierName(strings.ToUpper(modelShortName))
	if autoMode {
		fmt.Fprintf(os.Stderr, "[DEBUG] http-server: auto mode triggered (%q) — scoring from prompt (%d chars)\n", req.Model, len(prompt))
		modelOverride = ""
		difficultyHint = prompt
	} else if tierMode {
		fmt.Fprintf(os.Stderr, "[DEBUG] http-server: tier mode triggered (%q) — pinning to tier %s\n", req.Model, strings.ToUpper(modelShortName))
		modelOverride = strings.ToUpper(modelShortName) // executor detects "L2" as tier override
		difficultyHint = ""
	}

	result, err := b.executePromptLogic(ctx, prompt, systemPrompt, difficultyHint, jsonSchema, modelOverride, false)
	if err != nil {
		errRes := &ExecutionResult{
			Response: formatErrorMessageForClient(err),
			Source:   "error-proxy",
			Model:    modelOverride,
		}
		usage := buildTokenUsage(prompt, errRes.Response)
		resp := buildChatCompletionResponse(errRes, usage)
		writeJSON(w, http.StatusOK, resp)
		return
	}

	// Strip reasoning blocks from thinking models before returning to client.
	cleaned := stripThinkBlocks(result.Response)
	if cleaned != "" {
		result.Response = cleaned
	}

	usage := buildTokenUsage(prompt, result.Response)
	resp := buildChatCompletionResponse(result, usage)
	writeJSON(w, http.StatusOK, resp)
}

// handleStreamingChat implements SSE streaming for POST /v1/chat/completions with stream:true.
func (b *BrokerServer) handleStreamingChat(w http.ResponseWriter, ctx context.Context, req *ChatCompletionRequest, prompt, systemPrompt, jsonSchema string) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		writeJSON(w, http.StatusInternalServerError, buildErrorResponse(500, "streaming not supported"))
		return
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	idBase := fmt.Sprintf("chatcmpl-%d", time.Now().UnixNano())
	roleSent := false
	sendChunk := func(content string, finish bool) {
		var finishReason *string
		if finish {
			s := "stop"
			finishReason = &s
		}
		delta := MessageDelta{Content: content}
		if !roleSent {
			delta.Role = "assistant"
			roleSent = true
		}
		chunk := ChatCompletionChunk{
			ID:      idBase,
			Object:  "chat.completion.chunk",
			Created: time.Now().Unix(),
			Model:   req.Model,
			Choices: []ChunkChoice{{
				Index:        0,
				Delta:        delta,
				FinishReason: finishReason,
			}},
		}
		data, _ := json.Marshal(chunk)
		_, _ = fmt.Fprintf(w, "data: %s\n\n", data)
		flusher.Flush()
	}

	// Send initial role-only chunk immediately so opencode establishes the SSE
	// connection and resets its first-byte timeout. Without this, clients that
	// have a short first-byte timeout (e.g. 10 s) time out while the broker
	// is waiting for the local model to load and generate (which can take 20–30 s).
	sendChunk("", false)

	// Derive tier override and fallback routing params from the model field.
	modelShortName2 := req.Model
	if idx := strings.LastIndex(modelShortName2, "/"); idx >= 0 {
		modelShortName2 = modelShortName2[idx+1:]
	}
	modelOverride := req.Model
	difficultyHint := ""
	tierOverride := ""
	autoMode2 := modelShortName2 == "auto" || modelShortName2 == ""
	tierMode2 := isTierName(strings.ToUpper(modelShortName2))
	if autoMode2 {
		modelOverride = ""
		difficultyHint = prompt
	} else if tierMode2 {
		tierOverride = strings.ToUpper(modelShortName2)
		modelOverride = tierOverride
		difficultyHint = ""
	}

	fmt.Fprintf(os.Stderr, "[DEBUG] http-server streaming: model=%q tierOverride=%q\n", req.Model, tierOverride)

	// Keep SSE connection alive with periodic empty-delta data events while the model
	// generates. SSE comment lines (": keepalive") are NOT counted as "activity" by many
	// SSE clients (including opencode) — use real data events so client-side first-token
	// timeouts are reset and the connection stays open through long model-load waits.
	keepaliveDone := make(chan struct{})
	var closeOnce sync.Once
	stopKeepalive := func() { closeOnce.Do(func() { close(keepaliveDone) }) }
	go func() {
		ticker := time.NewTicker(5 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				sendChunk("", false) // proper SSE data event — resets client timeout
			case <-keepaliveDone:
				return
			}
		}
	}()

	// Tool-use path: when opencode provides tool definitions, use tryToolsDirect
	// which sends a non-streaming request and returns tool_calls in OpenAI format.
	// Only return early when the model actually emitted tool_use blocks.
	// If Jan returns text-only (no tool calls), fall through to the agentic loop —
	// the model likely generated pseudo-code instead of proper tool_use JSON.
	//
	// IMPORTANT: skip tryToolsDirect for orchestrator context. When the full 11-file
	// orchestrator system prompt is sent alongside all MCP tool definitions, the model
	// follows the orchestrator.md initialization protocol (loads skills, asks Socratic
	// Gate questions) instead of doing the actual task. The agentic loop uses a minimal
	// ~300-token system prompt and injects only call_agent, preventing that behavior.
	orchCtxForTools := isOrchestratorContext(systemPrompt)
	if orchCtxForTools {
		fmt.Fprintf(os.Stderr, "[INFO] http-server: orchestrator context — skipping tryToolsDirect, going to agentic loop\n")
		// Inject streaming callback so executeAgenticLoop emits progress markers and
		// final synthesis tokens directly to the SSE response in real-time.
		ctx = context.WithValue(ctx, agenticStreamKey{}, func(tok string) {
			sendChunk(tok, false)
		})
	}
	if len(req.Tools) > 0 && !orchCtxForTools {
		toolResult, toolErr := b.tryToolsDirect(ctx, prompt, systemPrompt, req.Messages, req.Tools, tierOverride)
		if toolErr != nil {
			fmt.Fprintf(os.Stderr, "[WARN] http-server: tryToolsDirect failed (%v) — falling through\n", toolErr)
			// Keep keepalive running; fall through to streaming below.
		} else if len(toolResult.ToolCalls) > 0 {
			stopKeepalive()
			// Set index on each tool call for OpenAI streaming format.
			for i := range toolResult.ToolCalls {
				toolResult.ToolCalls[i].Index = i
			}
			delta := MessageDelta{
				Role:      "assistant",
				Content:   toolResult.Text,
				ToolCalls: toolResult.ToolCalls,
			}
			chunk := ChatCompletionChunk{
				ID:      idBase,
				Object:  "chat.completion.chunk",
				Created: time.Now().Unix(),
				Model:   req.Model,
				Choices: []ChunkChoice{{Index: 0, Delta: delta}},
			}
			data, _ := json.Marshal(chunk)
			_, _ = fmt.Fprintf(w, "data: %s\n\n", data)
			flusher.Flush()
			// Final chunk with finish_reason.
			fr := "tool_calls"
			chunk2 := ChatCompletionChunk{
				ID: idBase, Object: "chat.completion.chunk",
				Created: time.Now().Unix(), Model: req.Model,
				Choices: []ChunkChoice{{Index: 0, Delta: MessageDelta{}, FinishReason: &fr}},
			}
			data2, _ := json.Marshal(chunk2)
			_, _ = fmt.Fprintf(w, "data: %s\n\ndata: [DONE]\n\n", data2)
			flusher.Flush()
			return
		} else {
			fmt.Fprintf(os.Stderr, "[WARN] http-server: tryToolsDirect returned no tool_use blocks (text-only) — falling through to agentic loop\n")
			// Keep keepalive running; fall through.
		}
	}

	// Fast path: stream tokens directly from Jan as they arrive (no buffering).
	// Skipped for orchestrator context: tryStreamDirect has no tool support, the
	// agentic loop in executePromptLogic must run to enable real call_agent calls.
	if !isOrchestratorContext(systemPrompt) {
		hasContent := false
		streamErr := b.tryStreamDirect(ctx, prompt, systemPrompt, tierOverride, req.Messages, func(tok string) {
			if tok != "" {
				hasContent = true
				sendChunk(tok, false)
			}
		})

		if streamErr == nil && hasContent {
			stopKeepalive()
			sendChunk("", true)
			_, _ = fmt.Fprintf(w, "data: [DONE]\n\n")
			flusher.Flush()
			return
		}

		if streamErr != nil {
			fmt.Fprintf(os.Stderr, "[WARN] http-server: direct stream failed (%v) — falling back to buffered path\n", streamErr)
		} else {
			fmt.Fprintf(os.Stderr, "[WARN] http-server: direct stream produced no content — falling back to buffered path\n")
		}
	} else {
		fmt.Fprintf(os.Stderr, "[INFO] http-server: orchestrator context — skipping direct stream, using agentic loop\n")
	}

	// Slow path: buffer the full response then emit word-by-word.
	result, err := b.executePromptLogic(ctx, prompt, systemPrompt, difficultyHint, jsonSchema, modelOverride, false)
	stopKeepalive()

	if err != nil {
		errMsg := formatErrorMessageForClient(err)
		sendChunk(errMsg, false)
		sendChunk("", true)
		_, _ = fmt.Fprintf(w, "data: [DONE]\n\n")
		flusher.Flush()
		return
	}

	content := stripThinkBlocks(result.Response)
	if content == "" {
		content = result.Response
	}
	words := strings.Fields(content)
	for i, word := range words {
		text := word
		if i > 0 {
			text = " " + word
		}
		sendChunk(text, false)
	}
	sendChunk("", true)
	_, _ = fmt.Fprintf(w, "data: [DONE]\n\n")
	flusher.Flush()
}

// ---------------------------------------------------------------------------
// Real-time think-block filter for streaming responses
// ---------------------------------------------------------------------------

// thinkFilter strips <think>...</think> blocks from a streaming response in
// real-time, calling out() for each non-think content chunk. A small lookahead
// buffer handles tags that arrive split across two consecutive chunks.
type thinkFilter struct {
	inThink bool
	buf     strings.Builder
	out     func(string)
}

func (f *thinkFilter) feed(chunk string) {
	f.buf.WriteString(chunk)
	s := f.buf.String()
	f.buf.Reset()
	for len(s) > 0 {
		if !f.inThink {
			if idx := strings.Index(s, "<think>"); idx >= 0 {
				if idx > 0 {
					f.out(s[:idx])
				}
				s = s[idx+len("<think>"):]
				f.inThink = true
				continue
			}
			// No complete <think> tag found; keep last 6 runes buffered
			// in case the tag straddles a chunk boundary.
			// Use rune count (not byte count) so multibyte UTF-8 chars (e.g. Cyrillic)
			// are never split between the output and the lookahead buffer.
			runes := []rune(s)
			safeR := len(runes) - 6
			if safeR <= 0 {
				f.buf.WriteString(s)
				return
			}
			f.out(string(runes[:safeR]))
			f.buf.WriteString(string(runes[safeR:]))
			return
		}
		// Inside think block — discard until closing tag.
		if idx := strings.Index(s, "</think>"); idx >= 0 {
			s = s[idx+len("</think>"):]
			f.inThink = false
			continue
		}
		// Still inside think block; keep last 8 chars for split-tag detection.
		if len(s) > 8 {
			s = s[len(s)-8:]
		}
		f.buf.WriteString(s)
		return
	}
}

func (f *thinkFilter) flush() {
	if !f.inThink && f.buf.Len() > 0 {
		f.out(f.buf.String())
		f.buf.Reset()
	}
}

// ---------------------------------------------------------------------------
// Direct streaming from Jan
// ---------------------------------------------------------------------------

// anthropicTurn is an intermediate representation before building the final messages array.
type anthropicTurn struct {
	role    string
	text    string   // set for plain text messages
	content []any    // set for structured content (tool_use, tool_result)
}

func (t anthropicTurn) charLen() int { return len(t.text) }

func (t anthropicTurn) toMap() map[string]any {
	if t.content != nil {
		return map[string]any{"role": t.role, "content": t.content}
	}
	return map[string]any{"role": t.role, "content": t.text}
}

// buildAnthropicMessages converts OpenAI messages to the Anthropic /messages format.
// System messages are excluded (they go to the top-level "system" field).
// Tool call / tool result messages are converted to Anthropic's structured format.
// The result is trimmed to fit within maxChars to avoid overflowing Jan's context window.
func buildAnthropicMessages(messages []ChatMessage, maxChars int) []map[string]any {
	var turns []anthropicTurn

	for _, msg := range messages {
		switch msg.Role {
		case "system":
			continue

		case "user":
			if msg.Content != "" {
				turns = append(turns, anthropicTurn{role: "user", text: msg.Content})
			}

		case "tool":
			// Tool result → Anthropic structured user message.
			toolResult := map[string]any{
				"type":    "tool_result",
				"content": msg.Content,
			}
			if msg.ToolCallID != "" {
				toolResult["tool_use_id"] = msg.ToolCallID
			}
			turns = append(turns, anthropicTurn{role: "user", content: []any{toolResult}})

		case "assistant":
			if len(msg.ToolCalls) > 0 {
				// Assistant with tool calls → Anthropic structured content.
				var parts []any
				if msg.Content != "" {
					parts = append(parts, map[string]any{"type": "text", "text": msg.Content})
				}
				for _, tc := range msg.ToolCalls {
					var input any
					if err := json.Unmarshal([]byte(tc.Function.Arguments), &input); err != nil {
						input = map[string]any{}
					}
					parts = append(parts, map[string]any{
						"type":  "tool_use",
						"id":    tc.ID,
						"name":  tc.Function.Name,
						"input": input,
					})
				}
				turns = append(turns, anthropicTurn{role: "assistant", content: parts})
			} else if msg.Content != "" {
				turns = append(turns, anthropicTurn{role: "assistant", text: msg.Content})
			}
		}
	}

	// Ensure the last message is from the user (Anthropic requirement).
	for len(turns) > 0 && turns[len(turns)-1].role != "user" {
		turns = turns[:len(turns)-1]
	}

	// Trim from the front so total chars ≤ maxChars (keep most recent turns).
	if maxChars > 0 {
		total := 0
		keep := len(turns)
		for i := len(turns) - 1; i >= 0; i-- {
			total += turns[i].charLen()
			if total > maxChars {
				keep = i + 1
				break
			}
		}
		turns = turns[keep:]
	}

	// Collapse consecutive same-role messages (Anthropic requires strict alternation).
	// When mixing plain text and structured content, promote both to array form.
	var merged []anthropicTurn
	for _, t := range turns {
		if len(merged) == 0 || merged[len(merged)-1].role != t.role {
			merged = append(merged, t)
			continue
		}
		prev := &merged[len(merged)-1]
		// Both plain text → simple concatenation.
		if prev.content == nil && t.content == nil {
			prev.text += "\n" + t.text
			continue
		}
		// At least one is structured → merge into array content.
		var parts []any
		if prev.content != nil {
			parts = append(parts, prev.content...)
		} else if prev.text != "" {
			parts = append(parts, map[string]any{"type": "text", "text": prev.text})
		}
		if t.content != nil {
			parts = append(parts, t.content...)
		} else if t.text != "" {
			parts = append(parts, map[string]any{"type": "text", "text": t.text})
		}
		prev.text = ""
		prev.content = parts
	}

	result := make([]map[string]any, len(merged))
	for i, t := range merged {
		result[i] = t.toMap()
	}
	return result
}

// convertToolsToAnthropic converts OpenAI tool definitions to Anthropic format.
func convertToolsToAnthropic(tools []Tool) []map[string]any {
	result := make([]map[string]any, 0, len(tools))
	for _, t := range tools {
		if t.Type != "function" {
			continue
		}
		schema := t.Function.Parameters
		if len(schema) == 0 {
			schema = json.RawMessage(`{"type":"object","properties":{}}`)
		}
		entry := map[string]any{
			"name":         t.Function.Name,
			"input_schema": schema,
		}
		if t.Function.Description != "" {
			entry["description"] = t.Function.Description
		}
		result = append(result, entry)
	}
	return result
}

// tryStreamDirect routes the request, opens a streaming connection to Jan, and
// forwards non-think content tokens to onContent as they arrive. It returns a
// non-nil error if routing fails or Jan is unreachable; the caller should then
// fall back to the buffered executePromptLogic path.
func (b *BrokerServer) tryStreamDirect(
	ctx context.Context,
	prompt, systemPrompt, tierOverride string,
	allMessages []ChatMessage,
	onContent func(string),
) error {
	env := b.detectEnv()
	discoverCtx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()

	// Detect Jan and record its base URL.
	pulled := make(map[string]string)
	var janURL string
	if models, err := b.fetchOpenAICompatibleModels(discoverCtx, DefaultJanURL); err == nil {
		for _, m := range models {
			pulled[m] = ProviderJan
		}
		janURL = DefaultJanURL
	} else if env.IsWSL && env.WSLGateway != "" {
		wslURL := fmt.Sprintf("http://%s:1337", env.WSLGateway)
		if models, err := b.fetchOpenAICompatibleModels(discoverCtx, wslURL); err == nil {
			for _, m := range models {
				pulled[m] = ProviderJan
			}
			janURL = wslURL
		}
	}
	if janURL == "" {
		return fmt.Errorf("Jan not reachable")
	}

	decision, err := b.makeRoutingDecision(prompt, pulled, tierOverride)
	if err != nil {
		return fmt.Errorf("routing: %w", err)
	}
	if decision.Provider != ProviderJan {
		return fmt.Errorf("routed to %q (not Jan) — buffered path handles cloud", decision.Provider)
	}

	// Jan loads one model at a time; concurrent requests cause 500 "failed to load".
	// Serialize all Jan streaming calls through the same semaphore used by the executor.
	janLimit := 1
	if rules, err := b.loadRules(); err == nil {
		janLimit = b.getConcurrencyLimit(ProviderJan, rules)
	}
	releaseSem, err := b.acquireSemaphore(ctx, ProviderJan, janLimit)
	if err != nil {
		return fmt.Errorf("Jan semaphore: %w", err)
	}
	defer releaseSem()

	// No per-tier output limit — let the model generate until it stops naturally.
	// Jan caps output to whatever n_ctx is set to in its model settings.
	maxTokens := 32768
	if rules, rErr := b.loadRules(); rErr == nil {
		if ps, ok := rules.ProviderSettings["jan"]; ok && ps.NCtx > 0 {
			maxTokens = ps.NCtx
		}
	}

	fmt.Fprintf(os.Stderr, "[INFO] tryStreamDirect: streaming model=%s tier=%s maxTokens=%d url=%s/messages\n",
		decision.ModelID, decision.Tier, maxTokens, janURL)

	// No system prompt truncation — Jan's context window is configured by the user in the app.
	// Pass full conversation history (0 = no char limit).
	var anthropicMessages []map[string]any
	if len(allMessages) > 0 {
		anthropicMessages = buildAnthropicMessages(allMessages, 0)
	}
	if len(anthropicMessages) == 0 {
		anthropicMessages = []map[string]any{{"role": "user", "content": prompt}}
	}

	// Use Anthropic Messages API — /messages handles system prompt as a top-level field
	// (fast, no new llamacpp process), unlike /v1/chat/completions which creates a new
	// process per unique system-prompt prefix and can take minutes to start.
	payload := map[string]any{
		"model":      decision.ModelID,
		"messages":   anthropicMessages,
		"stream":     true,
		"max_tokens": maxTokens,
	}
	if systemPrompt != "" {
		payload["system"] = systemPrompt
	}
	jsonData, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	streamReq, err := http.NewRequestWithContext(ctx,
		"POST", fmt.Sprintf("%s/messages", janURL),
		bytes.NewReader(jsonData))
	if err != nil {
		return err
	}
	streamReq.Header.Set("Content-Type", "application/json")
	streamReq.Header.Set("anthropic-version", "2023-06-01")

	resp, err := (&http.Client{Timeout: 300 * time.Second}).Do(streamReq)
	if err != nil {
		return fmt.Errorf("Jan streaming request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("Jan returned HTTP %d: %s", resp.StatusCode, string(body))
	}

	// Parse Anthropic SSE: paired event:/data: lines.
	// Extract delta.text from content_block_delta; collect usage from message_delta.
	streamStart := time.Now()
	var outputTokens int
	filter := &thinkFilter{out: onContent}
	scanner := bufio.NewScanner(resp.Body)
	scanner.Buffer(make([]byte, 64*1024), 64*1024)
	var lastEvent string
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if strings.HasPrefix(line, "event: ") {
			lastEvent = strings.TrimPrefix(line, "event: ")
			if lastEvent == "message_stop" {
				break
			}
			continue
		}
		if !strings.HasPrefix(line, "data: ") {
			continue
		}
		raw := []byte(strings.TrimPrefix(line, "data: "))
		switch lastEvent {
		case "content_block_delta":
			var delta struct {
				Delta struct {
					Text string `json:"text"`
				} `json:"delta"`
			}
			if json.Unmarshal(raw, &delta) == nil && delta.Delta.Text != "" {
				filter.feed(delta.Delta.Text)
			}
		case "message_delta":
			var md struct {
				Usage struct {
					OutputTokens int `json:"output_tokens"`
				} `json:"usage"`
			}
			if json.Unmarshal(raw, &md) == nil {
				outputTokens = md.Usage.OutputTokens
			}
		}
	}
	filter.flush()
	if err := scanner.Err(); err != nil {
		return err
	}
	if stats := formatPerfStats(outputTokens, time.Since(streamStart), decision.ModelID, decision.Tier, decision.Score); stats != "" {
		onContent("\n\n" + stats)
	}
	return nil
}

// ---------------------------------------------------------------------------
// Tool-use path: non-streaming request to Jan with tool forwarding
// ---------------------------------------------------------------------------

// ToolUseResult holds the parsed result of a Jan response that may contain tool calls.
type ToolUseResult struct {
	Text       string
	ToolCalls  []ToolCall
	StopReason string // "tool_use" or "end_turn"
}

// tryToolsDirect sends a non-streaming request to Jan with Anthropic-format tools
// and returns any text content + tool_use blocks as OpenAI-format ToolCalls.
func (b *BrokerServer) tryToolsDirect(
	ctx context.Context,
	prompt, systemPrompt string,
	allMessages []ChatMessage,
	tools []Tool,
	tierOverride string,
) (*ToolUseResult, error) {
	env := b.detectEnv()
	discoverCtx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()

	pulled := make(map[string]string)
	var janURL string
	if models, err := b.fetchOpenAICompatibleModels(discoverCtx, DefaultJanURL); err == nil {
		for _, m := range models {
			pulled[m] = ProviderJan
		}
		janURL = DefaultJanURL
	} else if env.IsWSL && env.WSLGateway != "" {
		wslURL := fmt.Sprintf("http://%s:1337", env.WSLGateway)
		if models, err := b.fetchOpenAICompatibleModels(discoverCtx, wslURL); err == nil {
			for _, m := range models {
				pulled[m] = ProviderJan
			}
			janURL = wslURL
		}
	}
	if janURL == "" {
		return nil, fmt.Errorf("Jan not reachable")
	}

	decision, err := b.makeRoutingDecision(prompt, pulled, tierOverride)
	if err != nil {
		return nil, fmt.Errorf("routing: %w", err)
	}
	if decision.Provider != ProviderJan {
		return nil, fmt.Errorf("routed to %q (not Jan)", decision.Provider)
	}

	maxTokens := 32768
	janLimit := 1
	if rules, rErr := b.loadRules(); rErr == nil {
		janLimit = b.getConcurrencyLimit(ProviderJan, rules)
		if ps, ok := rules.ProviderSettings["jan"]; ok && ps.NCtx > 0 {
			maxTokens = ps.NCtx
		}
	}
	releaseSem, err := b.acquireSemaphore(ctx, ProviderJan, janLimit)
	if err != nil {
		return nil, fmt.Errorf("Jan semaphore: %w", err)
	}
	defer releaseSem()

	// No system prompt truncation — Jan's context window is configured by the user in the app.
	// Pass full conversation history (0 = no char limit).
	anthropicMessages := buildAnthropicMessages(allMessages, 0)
	if len(anthropicMessages) == 0 {
		anthropicMessages = []map[string]any{{"role": "user", "content": prompt}}
	}

	payload := map[string]any{
		"model":      decision.ModelID,
		"messages":   anthropicMessages,
		"stream":     false,
		"max_tokens": maxTokens,
	}
	if systemPrompt != "" {
		payload["system"] = systemPrompt
	}
	if len(tools) > 0 {
		payload["tools"] = convertToolsToAnthropic(tools)
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequestWithContext(ctx, "POST",
		fmt.Sprintf("%s/messages", janURL), bytes.NewReader(jsonData))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("anthropic-version", "2023-06-01")

	fmt.Fprintf(os.Stderr, "[INFO] tryToolsDirect: model=%s tier=%s tools=%d url=%s/messages\n",
		decision.ModelID, decision.Tier, len(tools), janURL)

	resp, err := (&http.Client{Timeout: 300 * time.Second}).Do(req)
	if err != nil {
		return nil, fmt.Errorf("Jan request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("Jan returned HTTP %d: %s", resp.StatusCode, string(body))
	}

	// Parse Anthropic non-streaming response.
	var anthropicResp struct {
		Content []struct {
			Type  string          `json:"type"`
			Text  string          `json:"text,omitempty"`
			ID    string          `json:"id,omitempty"`
			Name  string          `json:"name,omitempty"`
			Input json.RawMessage `json:"input,omitempty"`
		} `json:"content"`
		StopReason string `json:"stop_reason"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&anthropicResp); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	result := &ToolUseResult{StopReason: anthropicResp.StopReason}
	for _, block := range anthropicResp.Content {
		switch block.Type {
		case "text":
			result.Text += block.Text
		case "tool_use":
			args := "{}"
			if len(block.Input) > 0 {
				args = string(block.Input)
			}
			result.ToolCalls = append(result.ToolCalls, ToolCall{
				ID:   block.ID,
				Type: "function",
				Function: ToolCallFunction{
					Name:      block.Name,
					Arguments: args,
				},
			})
		}
	}
	result.Text = stripThinkBlocks(result.Text)
	return result, nil
}

// stripThinkBlocks removes <think>...</think> reasoning blocks and DeepSeek-R1
// tool-format special tokens from model output. DeepSeek-R1 uses <｜...｜> tokens
// for its native tool-call format; when the broker doesn't parse them as real calls
// they leak into the visible response as garbage.
func stripThinkBlocks(s string) string {
	// 1. Remove <think>...</think> blocks (unclosed block → strip to end).
	for {
		start := strings.Index(s, "<think>")
		if start == -1 {
			break
		}
		end := strings.Index(s[start:], "</think>")
		if end == -1 {
			s = strings.TrimSpace(s[:start])
			break
		}
		s = s[:start] + s[start+end+len("</think>"):]
	}

	// 2. Strip DeepSeek-R1 special token blocks that appear after </think>.
	// Pattern: everything from <｜tool▁outputs▁begin｜> to end, or line-by-line.
	deepseekMarkers := []string{
		"<｜tool▁outputs▁begin｜>",
		"<｜tool▁output▁begin｜>",
		"<｜tool▁outputs▁end｜>",
		"<｜tool▁call▁begin｜>",
		"<｜tool▁call▁end｜>",
		"<｜tool▁sep｜>",
		"<｜fim▁begin｜>",
		"<｜fim▁hole｜>",
		"<｜fim▁end｜>",
	}
	for _, marker := range deepseekMarkers {
		// If any marker found — everything from first marker to end is tool-format garbage.
		if idx := strings.Index(s, marker); idx >= 0 {
			s = strings.TrimSpace(s[:idx])
			break
		}
	}

	return strings.TrimSpace(s)
}

// fetchModelsWithWSLFallback tries the given URL first, then falls back to WSL gateway.
func (b *BrokerServer) fetchModelsWithWSLFallback(ctx context.Context, localURL, port string, env EnvironmentInfo) ([]string, string, error) {
	models, err := b.fetchOpenAICompatibleModels(ctx, localURL)
	if err == nil {
		return models, localURL, nil
	}
	if env.IsWSL && env.WSLGateway != "" {
		wslURL := fmt.Sprintf("http://%s:%s", env.WSLGateway, port)
		models, err = b.fetchOpenAICompatibleModels(ctx, wslURL)
		if err == nil {
			return models, wslURL, nil
		}
	}
	return nil, localURL, err
}

// handleListModels implements GET /v1/models.
func (b *BrokerServer) handleListModels(w http.ResponseWriter, r *http.Request) {
	if r.Method != "GET" {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]interface{}{"error": "method not allowed, use GET"})
		return
	}

	listCtx, cancel := context.WithTimeout(r.Context(), 1*time.Second)
	defer cancel()

	env := b.detectEnv()
	var models []ModelObject

	// Ollama
	ollamaURL := b.getOllamaURL(env)
	if ollamaModels, err := b.fetchOllamaModels(listCtx, ollamaURL); err == nil {
		for _, m := range ollamaModels {
			models = append(models, ModelObject{ID: m, Object: "model", OwnedBy: "ollama"})
		}
	}

	// Jan (with WSL gateway fallback)
	if janModels, janURL, err := b.fetchModelsWithWSLFallback(listCtx, DefaultJanURL, "1337", env); err == nil {
		for _, m := range janModels {
			models = append(models, ModelObject{ID: m, Object: "model", OwnedBy: "jan"})
		}
		_ = janURL // used for logging if needed
	}

	// LM Studio (with WSL gateway fallback)
	if lmsModels, lmsURL, err := b.fetchModelsWithWSLFallback(listCtx, DefaultLMStudioURL, "1234", env); err == nil {
		for _, m := range lmsModels {
			models = append(models, ModelObject{ID: m, Object: "model", OwnedBy: "lm-studio"})
		}
		_ = lmsURL
	}

	// Always prepend "auto" as the first model for dynamic routing
	autoModel := ModelObject{ID: "auto", Object: "model", OwnedBy: "mcp-llm-broker"}
	models = append([]ModelObject{autoModel}, models...)

	resp := ListModelsResponse{
		Object: "list",
		Data:   models,
	}
	writeJSON(w, http.StatusOK, resp)
}

// handleHealthz implements GET /healthz.
func (b *BrokerServer) handleHealthz(w http.ResponseWriter, r *http.Request) {
	if r.Method != "GET" {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]interface{}{"error": "method not allowed, use GET"})
		return
	}

	circuitStateName := func(state int) string {
		switch state {
		case CircuitOpen:
			return "open"
		case CircuitHalfOpen:
			return "half-open"
		default:
			return "closed"
		}
	}

	// Read current health cache
	b.healthCacheMu.RLock()
	ollamaOK := false
	janOK := false
	lmsOK := false
	var ollamaCircuit, janCircuit, lmsCircuit string
	if h, ok := b.healthCache[ProviderOllama]; ok {
		ollamaOK = h.Available
		ollamaCircuit = circuitStateName(h.CircuitState)
	} else {
		ollamaCircuit = "unknown"
	}
	if h, ok := b.healthCache[ProviderJan]; ok {
		janOK = h.Available
		janCircuit = circuitStateName(h.CircuitState)
	} else {
		janCircuit = "unknown"
	}
	if h, ok := b.healthCache[ProviderLMStudio]; ok {
		lmsOK = h.Available
		lmsCircuit = circuitStateName(h.CircuitState)
	} else {
		lmsCircuit = "unknown"
	}
	b.healthCacheMu.RUnlock()

	status := "ok"
	if !ollamaOK && !janOK && !lmsOK {
		status = "degraded"
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"status":       status,
		"version":      serverVersion,
		"backends": map[string]interface{}{
			"ollama":         ollamaOK,
			"ollama_circuit": ollamaCircuit,
			"jan":            janOK,
			"jan_circuit":    janCircuit,
			"lm-studio":         lmsOK,
			"lm-studio_circuit": lmsCircuit,
		},
	})
}

// ---------------------------------------------------------------------------
// Server lifecycle
// ---------------------------------------------------------------------------

// createHTTPServer creates the HTTP server with all route handlers configured.
func (b *BrokerServer) createHTTPServer(port int) *http.Server {
	mux := http.NewServeMux()
	mux.HandleFunc("/v1/chat/completions", b.handleChatCompletions)
	mux.HandleFunc("/v1/models", b.handleListModels)
	mux.HandleFunc("/healthz", b.handleHealthz)

	return &http.Server{
		Addr:         fmt.Sprintf(":%d", port),
		Handler:      corsMiddleware(mux),
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 310 * time.Second, // slightly above LLM timeout
	}
}

// ---------------------------------------------------------------------------
// Middleware
// ---------------------------------------------------------------------------

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		next.ServeHTTP(w, r)
	})
}

// ---------------------------------------------------------------------------
// JSON writer helper
// ---------------------------------------------------------------------------

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

func formatErrorMessageForClient(err error) string {
	errStr := err.Error()
	return fmt.Sprintf("⚠️ **[mcp-llm-broker Error]**: Не удалось выполнить запрос к локальной модели.\n\n"+
		"**Детали ошибки**:\n```\n%s\n```\n\n"+
		"**Рекомендуемые действия**:\n"+
		"1. Убедитесь, что локальный провайдер (Jan или Ollama) запущен.\n"+
		"2. Проверьте настройки модели в Jan: возможно, требуется увеличить размер контекста (`n_ctx`) или освободить VRAM.\n"+
		"3. Посмотрите подробные логи в файле `/tmp/mcp-broker.log`:\n"+
		"   ```bash\n   tail -n 50 /tmp/mcp-broker.log\n   ```\n"+
		"4. Если контекст переполнен, очистите историю текущего чата.", errStr)
}
