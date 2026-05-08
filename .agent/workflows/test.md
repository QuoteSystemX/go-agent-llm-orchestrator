---
description: Test generation and test running command. Creates and executes tests for code.
---

# /test - Test Generation and Execution

$ARGUMENTS

---

## Purpose

This command generates tests, runs existing tests, or checks test coverage.

---

## Sub-commands

```
/test                - Run all tests
/test [file/feature] - Generate tests for specific target
/test coverage       - Show test coverage report
/test chaos          - Run resilience tests via Chaos Monkey
/test stress         - Run autonomous fuzzing (stress tests)
/test audit          - Run security scans and auto-patching
/test watch          - Run tests in watch mode
```

---

## Behavior

### 1. Generate Tests

When asked to test a file or feature:

1. **Analyze the code**
   - Identify functions and methods
   - Find edge cases
   - Detect dependencies to mock
   - Run `python3 .agent/scripts/test_factory.py "<file/feature>"` to generate boilerplates.

2. **Generate test cases**
   - Happy path tests
   - Error cases
   - Edge cases
   - Integration tests (if needed)

3. **Write tests**
   - Use project's test framework (Jest, Vitest, etc.)
   - Follow existing test patterns
   - Mock external dependencies

---

### 2. Advanced Testing Modes

#### Chaos Resilience (`/test chaos`)
- Run `CHAOS_ENABLED=1 python3 .agent/scripts/chaos_monkey.py --corrupt-bus --kill-mcp`.
- **Goal**: Verify if the system can detect and repair state corruption via `bus_debugger.py`.
- **Success**: System remains operational and repairs corrupted files automatically.

#### Stress Fuzzing (`/test stress`)
- Run `python3 .agent/scripts/autonomous_fuzzer.py`.
- **Goal**: Detect edge cases and panics through random input generation.

#### 🟢 Mode: Audit (Architecture & Governance)
1. // turbo
   Run `python3 .agent/scripts/verify_all.py`
2. // turbo
   Run `python3 .agent/scripts/drift_detector.py`
3. // turbo
   Run `python3 .agent/scripts/hallucination_detector.py`
4. // turbo
   Run `python3 .agent/scripts/qa_golden_engine.py` to verify output against architectural standards.
5. // turbo
   Run `python3 .agent/scripts/security_scan.py` and `dependency_analyzer.py`.
- If vulnerabilities found:
  - // turbo
    Run `python3 .agent/scripts/vulnerability_patcher.py` to prepare fixes.
  - Apply fixes using `security-auditor` agent.

## Output Format

### For Test Generation

```markdown
## 🧪 Tests: [Target]

### Test Plan
| Test Case | Type | Coverage |
|-----------|------|----------|
| Should create user | Unit | Happy path |
| Should reject invalid email | Unit | Validation |
| Should handle db error | Unit | Error case |

### Generated Tests

`tests/[file].test.ts`

[Code block with tests]

---

Run with: `npm test`
```

### For Test Execution

```
🧪 Running tests...

✅ auth.test.ts (5 passed)
✅ user.test.ts (8 passed)
❌ order.test.ts (2 passed, 1 failed)

Failed:
  ✗ should calculate total with discount
    Expected: 90
    Received: 100

Total: 15 tests (14 passed, 1 failed)
```

---

## Examples

```
/test src/services/auth.service.ts
/test user registration flow
/test coverage
/test fix failed tests
```

---

## Test Patterns

### Unit Test Structure

```typescript
describe('AuthService', () => {
  describe('login', () => {
    it('should return token for valid credentials', async () => {
      // Arrange
      const credentials = { email: 'test@test.com', password: 'pass123' };
      
      // Act
      const result = await authService.login(credentials);
      
      // Assert
      expect(result.token).toBeDefined();
    });

    it('should throw for invalid password', async () => {
      // Arrange
      const credentials = { email: 'test@test.com', password: 'wrong' };
      
      // Act & Assert
      await expect(authService.login(credentials)).rejects.toThrow('Invalid credentials');
    });
  });
});
```

---

## Key Principles

- **Test behavior not implementation**
- **One assertion per test** (when practical)
- **Descriptive test names**
- **Arrange-Act-Assert pattern**
- **Mock external dependencies**
