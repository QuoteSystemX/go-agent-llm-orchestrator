---
name: playwright-best-practices
description: Best practices for writing, debugging, and optimizing Playwright tests and browser automation.
version: 1.0.0
---

# 🎭 Playwright Best Practices

Guidelines for creating stable, fast, and maintainable browser automation and UI tests.

## 🛠 Stability & Reliability

- **Auto-waiting**: Rely on Playwright's built-in auto-waiting for elements to be visible/stable. Avoid `time.sleep()` or fixed timeouts.
- **Locators**: Use user-visible locators like `getByRole` or `getByText` instead of fragile CSS selectors or XPaths.
- **Web-First Assertions**: Use `expect(page).toHaveURL()` instead of manual URL checks.

## 🐛 Debugging in Complex Environments (WSL/CI)

- **Headless Debugging**: Use `page.screenshot()` and `browserContext.tracing` to visualize failures in CI/headless modes.
- **Networking**: Use `--host-resolver-rules` for custom DNS mapping without modifying `/etc/hosts`.
- **Ignore HTTPS Errors**: Use `ignoreHTTPSErrors: true` for local development with self-signed certificates.

## 🚀 Performance

- **Parallelization**: Run tests in parallel to reduce CI time.
- **Resource Reuse**: Reuse browser contexts and authentication states to avoid repeated logins.

---
> **Note**: This skill was imported from `skills.sh` to stabilize UI interactions within Paperclip.
