---
name: pc-games
description: PC and console game development principles. Engine selection, platform features, optimization strategies.
allowed-tools: Read, Write, Edit, Glob, Grep
---

# PC/Console Game Development

> Engine selection and platform-specific principles.

---

## 1. Engine Selection

### Decision Tree

```
What are you building?
│
├── 2D Game
│   ├── Open source important? → Godot
│   └── Large team/assets? → Unity
│
├── 3D Game
│   ├── AAA visual quality? → Unreal
│   ├── Cross-platform priority? → Unity
│   └── Indie/open source? → Godot 4
│
└── Specific Needs
    ├── DOTS performance? → Unity
    ├── Nanite/Lumen? → Unreal
    └── Lightweight? → Godot
```

### Comparison

| Factor | Unity 6 | Godot 4 | Unreal 5 |
|--------|---------|---------|----------|
| 2D | Good | Excellent | Limited |
| 3D | Good | Good | Excellent |
| Learning | Medium | Easy | Hard |
| Cost | Revenue share | Free | 5% after $1M |
| Team | Any | Solo-Medium | Medium-Large |

---

## 2. Platform Features

### Steam Integration

| Feature | Purpose |
|---------|---------|
| Achievements | Player goals |
| Cloud Saves | Cross-device progress |
| Leaderboards | Competition |
| Workshop | User mods |
| Rich Presence | Show in-game status |

### Console Requirements

| Platform | Certification |
|----------|--------------|
| PlayStation | TRC compliance |
| Xbox | XR compliance |
| Nintendo | Lotcheck |

---

## 3. Controller Support

### Input Abstraction

```
Map ACTIONS, not buttons:
- "confirm" → A (Xbox), Cross (PS), B (Nintendo)
- "cancel" → B (Xbox), Circle (PS), A (Nintendo)
```

### Haptic Feedback

| Intensity | Use |
|-----------|-----|
| Light | UI feedback |
| Medium | Impacts |
| Heavy | Major events |

---

## 4. Performance Optimization

### Profiling First

| Engine | Tool |
|--------|------|
| Unity | Profiler Window |
| Godot | Debugger → Profiler |
| Unreal | Unreal Insights |

### Common Bottlenecks

| Bottleneck | Solution |
|------------|----------|
| Draw calls | Batching, atlases |
| GC spikes | Object pooling |
| Physics | Simpler colliders |
| Shaders | LOD shaders |

---

## 5. Engine-Specific Principles

### Unity 6

- DOTS for performance-critical systems
- Burst compiler for hot paths
- Addressables for asset streaming

### Godot 4

- GDScript for rapid iteration
- C# for complex logic
- Signals for decoupling

### Unreal 5

- Blueprint for designers
- C++ for performance
- Nanite for high-poly environments
- Lumen for dynamic lighting

---

## 6. Anti-Patterns

| ❌ Don't | ✅ Do |
|----------|-------|
| Choose engine by hype | Choose by project needs |
| Ignore platform guidelines | Study certification requirements |
| Hardcode input buttons | Abstract to actions |
| Skip profiling | Profile early and often |

---

> **Remember:** Engine is a tool. Master the principles, then adapt to any engine.


## When to Use

- **Building a desktop game** — Unity, Unreal, or Godot for
  3D; Unity 2D or Godot for 2D.
- **Setting up version control** — Git LFS for binary assets
  (textures, models, audio).
- **Build pipeline** — CI builds the game for each target
  platform on every PR.
- **Distribution** — Steam, itch.io, Epic Games Store, or
  self-hosted (for early access).
- **Modding support** — expose a clean scripting API if you want
  community mods.

Avoid using this skill for:
- Web games (use `@web-games`).
- Mobile-only (use mobile skills).
- Server-side multiplayer (use `@multiplayer`).

## Anti-Patterns

- **Don't commit binary assets to Git** — use Git LFS
  or DVC. Otherwise repo size explodes.
- **Don't use `Time.deltaTime` in Update for game logic** — use
  `Time.fixedDeltaTime` for physics, normalized `Time.deltaTime`
  for visuals.
- **Don't ship a debug build** — always ship `Release` with
  `Development Build` off.
- **Don't ignore the Profiler** — if you can't see where frames
  are spent, you can't optimize.
- **Don't use `Find` in Update** — cache references in `Awake`.
- **Don't ship without a crash reporter** — Sentry, Backtrace,
  or your own. You need to know what crashes in production.
- **Don't hardcode paths** — use `Application.persistentDataPath`.