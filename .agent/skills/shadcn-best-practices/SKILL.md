---
name: shadcn-best-practices
description: Standards for adding, styling, and composing shadcn/ui components in React projects.
version: 1.0.0
---

# 🎨 Shadcn UI Best Practices

Guidelines for maintaining a consistent and scalable UI system using shadcn/ui components.

## 🏗 Component Management

- **Atomic Addition**: Add only the components you need (`npx shadcn@latest add ...`).
- **Customization**: Do not edit the `components/ui` folder directly for global changes; use the `ui-ux-pro-max` design tokens via `tailwind.config.ts`.
- **Composition**: Prefer composing simple components (e.g., `Button` + `Dropdown`) into complex widgets rather than building monolithic components.

## 💅 Styling & Theme

- **Tailwind-First**: Use Tailwind utility classes for all styling.
- **Color Variables**: Reference CSS variables (e.g., `--primary`, `--background`) to support dynamic theming and Dark Mode.
- **Consistency**: Follow the Paperclip design system spacing and border-radius tokens.

## 🧱 Accessible Forms

- **React Hook Form**: Use with `Zod` for type-safe validation.
- **Accessible Labels**: Ensure every input has a corresponding `Label` and correct `aria-describedby` attributes.

---
> **Note**: This skill was imported from `skills.sh` to ensure Auth Hub's UI is consistent with Paperclip core.
