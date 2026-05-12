---
name: shadcn-best-practices
description: Standards for adding, styling, and composing shadcn/ui components in React projects.
version: 1.0.0
---

# 🎨 shadcn/ui Best Practices

Expert guidelines for building beautiful, accessible, and themeable components using shadcn/ui and Tailwind CSS.

## 🏗 Component Architecture

- **Composition**: Prefer composing simple components (Slot, Button, Input) into complex ones rather than creating massive "God Components".
- **Ref Forwarding**: Always use `React.forwardRef` to allow components to be used with libraries like Framer Motion or React Hook Form.
- **Display Name**: Explicitly set `.displayName` on all exported components for better debugging.

## 💅 Theming & Styling

- **CSS Variables**: Use CSS variables (e.g., `bg-background`, `text-primary`) for all colors to support Dark Mode and dynamic themes automatically.
- **CN Utility**: Always use the `cn` utility to merge classNames and handle Tailwind conflicts.
- **CVA**: Use `class-variance-authority` (CVA) to define component variants (sizes, colors, shapes) in a type-safe way.

## 🚀 Tools & Verification

### 1. Component Linter
Run the internal audit script to ensure UI components follow shadcn standards:

```bash
python3 .agent/skills/shadcn-best-practices/scripts/verify_components.py
```

### 2. Custom Patterns
Refer to `examples/custom-component.tsx` for a "Golden Path" implementation of a variant-heavy component with glassmorphism support.

## 📈 UI Hygiene Checklist
- [ ] Does it use `cn()` for class merging?
- [ ] Is `forwardRef` implemented correctly?
- [ ] Is `.displayName` set?
- [ ] Are hardcoded colors replaced with CSS variables?
- [ ] Are accessibility attributes (ARIA) present?

---
> **Note**: This skill ensures that the Paperclip interface remains premium, accessible, and easy to theme.

