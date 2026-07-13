---
name: 2d-games
description: 2D game development principles. Sprites, tilemaps, physics, camera.
allowed-tools: Read, Write, Edit, Glob, Grep
---

# 2D Game Development

> Principles for 2D game systems.

---

## 1. Sprite Systems

### Sprite Organization

| Component | Purpose |
|-----------|---------|
| **Atlas** | Combine textures, reduce draw calls |
| **Animation** | Frame sequences |
| **Pivot** | Rotation/scale origin |
| **Layering** | Z-order control |

### Animation Principles

- Frame rate: 8-24 FPS typical
- Squash and stretch for impact
- Anticipation before action
- Follow-through after action

---

## 2. Tilemap Design

### Tile Considerations

| Factor | Recommendation |
|--------|----------------|
| **Size** | 16x16, 32x32, 64x64 |
| **Auto-tiling** | Use for terrain |
| **Collision** | Simplified shapes |

### Layers

| Layer | Content |
|-------|---------|
| Background | Non-interactive scenery |
| Terrain | Walkable ground |
| Props | Interactive objects |
| Foreground | Parallax overlay |

---

## 3. 2D Physics

### Collision Shapes

| Shape | Use Case |
|-------|----------|
| Box | Rectangular objects |
| Circle | Balls, rounded |
| Capsule | Characters |
| Polygon | Complex shapes |

### Physics Considerations

- Pixel-perfect vs physics-based
- Fixed timestep for consistency
- Layers for filtering

---

## 4. Camera Systems

### Camera Types

| Type | Use |
|------|-----|
| **Follow** | Track player |
| **Look-ahead** | Anticipate movement |
| **Multi-target** | Two-player |
| **Room-based** | Metroidvania |

### Screen Shake

- Short duration (50-200ms)
- Diminishing intensity
- Use sparingly

---

## 5. Genre Patterns

### Platformer

- Coyote time (leniency after edge)
- Jump buffering
- Variable jump height

### Top-down

- 8-directional or free movement
- Aim-based or auto-aim
- Consider rotation or not

---

## 6. Anti-Patterns

| ❌ Don't | ✅ Do |
|----------|-------|
| Separate textures | Use atlases |
| Complex collision shapes | Simplified collision |
| Jittery camera | Smooth following |
| Pixel-perfect on physics | Choose one approach |

---

> **Remember:** 2D is about clarity. Every pixel should communicate.


## When to Use

- **Building a 2D game** — choose a framework (Phaser, PixiJS,
  Godot, Unity 2D) based on your team's skills.
- **Setting up a sprite system** — atlas + JSON metadata is the
  standard pattern.
- **Implementing physics** — start with arcade physics, upgrade
  to AABB or full rigid-body only if needed.
- **Adding UI** — separate UI from gameplay (UI scene).
- **Performance optimization** — batch draw calls, object pool
  bullets/enemies, cull off-screen.

Avoid using this skill for:
- 3D games (use `@3d-games`).
- VR games (use `@vr-ar`).
- Web-only interactions (use `@frontend-specialist`).

## Anti-Patterns

- **Don't create GameObjects in update()** — pre-allocate
  and pool them. `Instantiate` is expensive.
- **Don't use Find or FindObjectOfType in hot paths** — cache
  references in `Awake`/`Start`.
- **Don't put physics in Update()** — use `FixedUpdate` for
  consistent simulation.
- **Don't use string-based Animator parameters** — use hashes
  (`Animator.StringToHash`) for performance.
- **Don't skip the camera culling** — off-screen objects still
  cost CPU. Use culling masks.
- **Don't ship without a framerate target** — design for 60 FPS
  from day 1, optimize later if needed.
- **Don't use `Time.deltaTime` inconsistently** — always normalize
  your game logic to it, or use `Time.fixedDeltaTime` in physics.