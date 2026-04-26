---
name: refactoring-patterns
description: Systematic refactoring techniques — code smell detection, safe transformation sequences, legacy code modernization, and technical debt reduction. Use when improving existing code without changing behavior.
allowed-tools: Read, Grep, Glob, Edit, Write
version: 1.0
priority: HIGH
---

# Refactoring Patterns

> **Refactoring** = improving code structure without changing observable behavior.
> **Golden Rule**: Never refactor and fix bugs simultaneously. One thing at a time.

---

## Code Smell Catalog

| Smell | Symptom | Refactoring |
|-------|---------|-------------|
| **Long Method** | Function > 20 lines, does multiple things | Extract Method |
| **Large Class** | Class > 200 lines, many responsibilities | Extract Class / Move Method |
| **Long Parameter List** | Function takes 4+ params | Introduce Parameter Object |
| **Duplicate Code** | Same logic in 2+ places | Extract Method / Pull Up Method |
| **Divergent Change** | One class changes for many different reasons | Extract Class |
| **Shotgun Surgery** | One change requires edits across many classes | Move Method / Inline Class |
| **Feature Envy** | Method uses another class's data more than its own | Move Method |
| **Data Clumps** | Same 3+ fields always appear together | Extract Class |
| **Primitive Obsession** | Strings/ints used instead of domain objects | Replace Primitive with Object |
| **Switch Statements** | Switch on type/kind repeatedly | Replace with Polymorphism |
| **Parallel Inheritance** | New subclass forces another subclass elsewhere | Move Method |
| **Dead Code** | Unused variables, methods, classes | Delete |
| **Speculative Generality** | Abstract hooks for imagined future use | Collapse Hierarchy / Inline |
| **Temporary Field** | Object field only set in some scenarios | Extract Class, Introduce Null Object |
| **Message Chains** | `a.b().c().d()` — Law of Demeter violation | Hide Delegate |
| **Middle Man** | Class delegates most work, does little itself | Remove Middle Man |
| **Inappropriate Intimacy** | Classes know too much about each other | Move Method, Extract Class |
| **Comments** | Comment explains WHAT not WHY | Rename / Extract Method (make it self-documenting) |

---

## Core Refactoring Techniques

### 1. Extract Method
Split long function into smaller, named pieces.

```
// Before
function processOrder(order) {
  // validate
  if (!order.id || !order.items.length) throw new Error(...)
  // calculate total
  let total = order.items.reduce(...)
  // apply discount
  if (order.customerType === 'vip') total *= 0.9
  // save
  db.save({...order, total})
}

// After
function processOrder(order) {
  validateOrder(order)
  const total = calculateTotal(order)
  db.save({...order, total})
}
```

**When**: Method does 2+ distinct things. Name reveals intent.

### 2. Extract Class
Single class with multiple responsibilities → split by cohesion.

**Trigger**: "AND" in the class description. "Handles users AND sends emails."

### 3. Move Method / Move Field
Put behavior where the data it uses lives.

**Trigger**: Method uses more of another class's data than its own.

### 4. Replace Temp with Query
```
// Before
const basePrice = quantity * itemPrice
if (basePrice > 1000) return basePrice * 0.95

// After
if (basePrice() > 1000) return basePrice() * 0.95
function basePrice() { return quantity * itemPrice }
```

### 5. Introduce Parameter Object
```
// Before
function report(startDate, endDate, minAmount, maxAmount) {...}

// After
function report(dateRange: DateRange, amountRange: AmountRange) {...}
```

### 6. Replace Conditional with Polymorphism
```
// Before
function getSpeed(bird) {
  switch (bird.type) {
    case 'European': return baseSpeed()
    case 'African': return baseSpeed() - loadFactor() * bird.numberOfCoconuts
  }
}

// After
class EuropeanBird { getSpeed() { return baseSpeed() } }
class AfricanBird  { getSpeed() { return baseSpeed() - loadFactor() * this.numberOfCoconuts } }
```

### 7. Inline Method / Inline Variable
Remove indirection that no longer adds clarity.

### 8. Rename (Variable / Method / Class)
The most impactful, lowest-risk refactoring. A good name eliminates the need for a comment.

---

## Safety Protocol (MANDATORY)

```
1. TESTS FIRST — Run existing tests. All must pass before touching anything.
2. COMMIT — Commit working state before refactoring.
3. ONE STEP — Make the smallest possible change.
4. TEST AGAIN — Run tests after each change.
5. COMMIT — Commit after each green step.
```

> 🔴 If tests don't exist: write characterization tests (snapshot current behavior) BEFORE refactoring.

---

## Legacy Code Strategy

### Strangler Fig Pattern
Gradually replace legacy system by routing new code alongside old:
```
New Request → Router → [New Handler] or [Legacy System]
```
1. Build new implementation behind feature flag
2. Route % of traffic to new
3. Verify parity
4. Flip 100%, delete old

### Seam Model (Michael Feathers)
A **seam** is a place where you can change behavior without editing existing code.
- **Object Seam**: override via subclass / interface
- **Parameter Seam**: inject dependency instead of hard-coding
- **Link Seam**: swap linked library at build time

**Use to**: make untestable legacy code testable without rewriting it first.

### Characterization Tests
When you don't know what legacy code SHOULD do — capture what it DOES:
```python
def test_characterize_process_order():
    result = process_order(fixture_order())
    assert result == "whatever_it_returns_today"  # document current behavior
```
Now you can refactor safely.

---

## Technical Debt Assessment

| Debt Type | Description | Priority |
|-----------|-------------|----------|
| **Reckless / Deliberate** | "We don't have time for design" | HIGH — pay now |
| **Reckless / Inadvertent** | "What's layering?" | HIGH — educate + fix |
| **Prudent / Deliberate** | "Ship now, fix later" — tracked | MEDIUM — schedule |
| **Prudent / Inadvertent** | "Now we know better" — learned | LOW — fix opportunistically |

---

## Refactoring Workflow

```
1. IDENTIFY smell → name it from the catalog above
2. CHOOSE technique → pick from core techniques
3. CHECK for tests → write characterization tests if missing
4. APPLY in smallest step possible
5. RUN tests → must stay green
6. COMMIT with message: "refactor: extract X from Y"
7. REPEAT → one smell at a time
```

---

## Commit Message Convention

```
refactor: extract validateOrder from processOrder
refactor: replace switch with polymorphism in BirdSpeed
refactor: introduce DateRange parameter object in Report
refactor: rename confusing variable n → userCount
```

> Never mix: `fix: bug + refactor: cleanup` in one commit. Split them.

## Changelog

- **1.0** (2026-04-26): Initial version
