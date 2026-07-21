package main

import (
	"net"
	"strconv"
	"strings"
	"testing"
)

// -------- windowsUserProfileToWSLPath --------

func TestWindowsUserProfileToWSLPath_Valid(t *testing.T) {
	got, err := windowsUserProfileToWSLPath(`C:\Users\artur`)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != "/mnt/c/Users/artur" {
		t.Errorf("expected /mnt/c/Users/artur, got %q", got)
	}
}

func TestWindowsUserProfileToWSLPath_TrimsWhitespace(t *testing.T) {
	// cmd.exe's `echo %USERPROFILE%` output over WSL interop includes a trailing newline.
	got, err := windowsUserProfileToWSLPath("C:\\Users\\artur\r\n")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != "/mnt/c/Users/artur" {
		t.Errorf("expected /mnt/c/Users/artur, got %q", got)
	}
}

func TestWindowsUserProfileToWSLPath_DifferentDrive(t *testing.T) {
	got, err := windowsUserProfileToWSLPath(`D:\Users\artur`)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != "/mnt/d/Users/artur" {
		t.Errorf("expected /mnt/d/Users/artur, got %q", got)
	}
}

func TestWindowsUserProfileToWSLPath_RejectsNonWindowsPath(t *testing.T) {
	_, err := windowsUserProfileToWSLPath("/home/artur")
	if err == nil {
		t.Error("expected an error for a non-Windows-style path, got nil")
	}
}

func TestWindowsUserProfileToWSLPath_RejectsEmpty(t *testing.T) {
	_, err := windowsUserProfileToWSLPath("")
	if err == nil {
		t.Error("expected an error for an empty path, got nil")
	}
}

// -------- patchJSONField --------

func TestPatchJSONField_ReplacesValuePreservingOtherKeys(t *testing.T) {
	raw := []byte(`{
  "_llamacpp_base_url_comment": "edit me after each llama-server restart",
  "llamacpp_base_url": "http://localhost:8080",
  "pricing_per_1k_tokens": {
    "_comment": "USD cost per 1K tokens.",
    "local": 0.0
  }
}`)

	patched, err := patchJSONField(raw, "llamacpp_base_url", "http://172.31.0.1:54321")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	got := string(patched)
	if !strings.Contains(got, `"llamacpp_base_url": "http://172.31.0.1:54321"`) {
		t.Errorf("expected patched value present, got: %s", got)
	}
	if !strings.Contains(got, `"_llamacpp_base_url_comment": "edit me after each llama-server restart"`) {
		t.Errorf("expected unrelated comment field to survive the patch untouched, got: %s", got)
	}
	if !strings.Contains(got, `"_comment": "USD cost per 1K tokens."`) {
		t.Errorf("expected nested pricing comment to survive the patch untouched, got: %s", got)
	}
	if !strings.Contains(got, `"local": 0.0`) {
		t.Errorf("expected nested pricing value to survive the patch untouched, got: %s", got)
	}
}

func TestPatchJSONField_ErrorsWhenKeyMissing(t *testing.T) {
	raw := []byte(`{"some_other_field": "value"}`)
	_, err := patchJSONField(raw, "llamacpp_base_url", "http://localhost:9999")
	if err == nil {
		t.Error("expected an error when the target key is absent, got nil")
	}
}

func TestPatchJSONField_EscapesValueCorrectly(t *testing.T) {
	// A value containing a quote or backslash must round-trip through valid JSON,
	// not corrupt the surrounding document.
	raw := []byte(`{"llamacpp_base_url": "http://localhost:8080"}`)
	patched, err := patchJSONField(raw, "llamacpp_base_url", `http://host/weird"path`)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !strings.Contains(string(patched), `\"path`) {
		t.Errorf("expected the embedded quote to be JSON-escaped, got: %s", patched)
	}
}

// -------- pickFreePort --------

func TestPickFreePort_ReturnsBindablePort(t *testing.T) {
	port, err := pickFreePort()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if port <= 0 || port > 65535 {
		t.Fatalf("expected a valid port number, got %d", port)
	}

	l, err := net.Listen("tcp", net.JoinHostPort("127.0.0.1", strconv.Itoa(port)))
	if err != nil {
		t.Fatalf("expected the returned port %d to be immediately bindable, got: %v", port, err)
	}
	l.Close()
}

// -------- llamaCppBuildAdvice --------

func TestLlamaCppBuildAdvice_WSLWarnsAgainstDriverPackage(t *testing.T) {
	advice := llamaCppBuildAdvice(EnvironmentInfo{OS: "linux", IsWSL: true})
	if !advice.Supported {
		t.Fatal("expected WSL to be a supported build environment")
	}
	if advice.CMakeFlag != "-DGGML_CUDA=ON" {
		t.Errorf("expected CUDA cmake flag for WSL, got %q", advice.CMakeFlag)
	}
	if !strings.Contains(advice.PrereqMessage, "WSL-Ubuntu") {
		t.Errorf("expected WSL-specific installer guidance, got: %s", advice.PrereqMessage)
	}
	if !strings.Contains(advice.PrereqMessage, "cuda-drivers") {
		t.Errorf("expected explicit warning against cuda-drivers meta-package, got: %s", advice.PrereqMessage)
	}
}

func TestLlamaCppBuildAdvice_NativeLinuxDiffersFromWSL(t *testing.T) {
	// This is the actual bug this function exists to prevent: WSL and native
	// Linux must NOT get the same driver-install advice — WSL must avoid
	// installing a driver, native Linux needs one installed normally.
	wsl := llamaCppBuildAdvice(EnvironmentInfo{OS: "linux", IsWSL: true})
	native := llamaCppBuildAdvice(EnvironmentInfo{OS: "linux", IsWSL: false})

	if wsl.PrereqMessage == native.PrereqMessage {
		t.Fatal("expected WSL and native Linux to receive different prerequisite guidance, got identical messages")
	}
	if strings.Contains(native.PrereqMessage, "cuda-drivers") && strings.Contains(native.PrereqMessage, "NEVER") {
		t.Error("native Linux advice must not carry WSL's 'never install the driver' warning")
	}
	if native.CMakeFlag != "-DGGML_CUDA=ON" {
		t.Errorf("expected CUDA cmake flag for native Linux too, got %q", native.CMakeFlag)
	}
}

func TestLlamaCppBuildAdvice_MacOSUsesMetalNotCUDA(t *testing.T) {
	advice := llamaCppBuildAdvice(EnvironmentInfo{OS: "darwin"})
	if !advice.Supported {
		t.Fatal("expected macOS to be a supported build environment")
	}
	if advice.CMakeFlag != "-DGGML_METAL=ON" {
		t.Errorf("expected Metal cmake flag on macOS, got %q", advice.CMakeFlag)
	}
	if strings.Contains(advice.PrereqMessage, "cuda-downloads") || strings.Contains(advice.PrereqMessage, "cuda-installation-guide") {
		t.Errorf("macOS advice must not point at a CUDA install URL, got: %s", advice.PrereqMessage)
	}
	if !strings.Contains(advice.PrereqMessage, "Xcode") {
		t.Errorf("expected macOS advice to mention the actual prerequisite (Xcode CLT), got: %s", advice.PrereqMessage)
	}
}

func TestLlamaCppBuildAdvice_NativeWindowsUnsupported(t *testing.T) {
	advice := llamaCppBuildAdvice(EnvironmentInfo{OS: "windows"})
	if advice.Supported {
		t.Fatal("expected native Windows (non-WSL) to be marked unsupported for building from source")
	}
	if !strings.Contains(advice.PrereqMessage, "win-cuda") {
		t.Errorf("expected guidance to point at the prebuilt Windows release instead, got: %s", advice.PrereqMessage)
	}
}

func TestLlamaCppBuildAdvice_ContainerAppendsWarning(t *testing.T) {
	advice := llamaCppBuildAdvice(EnvironmentInfo{OS: "linux", IsContainer: true})
	if !strings.Contains(advice.PrereqMessage, "Container Toolkit") {
		t.Errorf("expected a container-specific GPU passthrough note appended, got: %s", advice.PrereqMessage)
	}
}
