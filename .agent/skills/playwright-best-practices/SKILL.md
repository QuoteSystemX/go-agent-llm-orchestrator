---
name: playwright-best-practices
description: Best practices for writing, debugging, and optimizing Playwright tests and browser automation.
version: 1.0.0
---

# 🎭 Playwright Best Practices

Expert guidelines for building robust, fast, and reliable End-to-End (E2E) tests with Playwright.

## 🏗 Test Strategy

- **Web-First Assertions**: Always use `expect(locator).toBeVisible()` or similar. Playwright will automatically wait for the condition to be met.
- **Isolation**: Each test should be independent. Use `beforeEach` to set up state (auth, cookies) rather than chaining tests.
- **Parallelism**: Design tests to run in parallel. Avoid shared global state that can cause race conditions.

## 🎯 Locators & Selectors

- **Semantic Locators**: Prefer `getByRole`, `getByLabel`, `getByText`. This ensures your tests also verify accessibility.
- **Data Attributes**: Use `data-testid` for elements that don't have a clear semantic role or are prone to text changes.
- **Brittle Selectors**: NEVER use auto-generated CSS selectors (e.g., `.css-1v23...`) or deep XPath.

## 🚀 Tools & Verification

### 1. Test Quality Auditor
Run the internal audit script to check for brittle selectors and hardcoded waits:

```bash
python3 .agent/skills/playwright-best-practices/scripts/verify_tests.py
```

### 2. Standard Patterns
Refer to `examples/basic-e2e.spec.ts` for a "Golden Path" implementation of a stable dashboard test.

## 📈 Testing Checklist
- [ ] Are web-first assertions used instead of manual waits?
- [ ] Are semantic locators (`getByRole`) prioritized?
- [ ] Are tests isolated and parallelizable?
- [ ] Is there a `data-testid` for non-semantic elements?
- [ ] Does the test verify the success/failure UI state?

---
> **Note**: This skill ensures that Paperclip features are verified automatically without brittle regressions.

