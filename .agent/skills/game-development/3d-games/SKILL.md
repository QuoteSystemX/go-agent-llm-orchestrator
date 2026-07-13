---
name: 3d-games
description: 3D game development principles. Rendering, shaders, physics, cameras.
allowed-tools: Read, Write, Edit, Glob, Grep
---

# 3D Game Development

> Principles for 3D game systems.

---

## 1. Rendering Pipeline

### Stages

```
1. Vertex Processing → Transform geometry
2. Rasterization → Convert to pixels
3. Fragment Processing → Color pixels
4. Output → To screen
```

### Optimization Principles

| Technique | Purpose |
|-----------|---------|
| **Frustum culling** | Don't render off-screen |
| **Occlusion culling** | Don't render hidden |
| **LOD** | Less detail at distance |
| **Batching** | Combine draw calls |

---

## 2. Shader Principles

### Shader Types

| Type | Purpose |
|------|---------|
| **Vertex** | Position, normals |
| **Fragment/Pixel** | Color, lighting |
| **Compute** | General computation |

### When to Write Custom Shaders

- Special effects (water, fire, portals)
- Stylized rendering (toon, sketch)
- Performance optimization
- Unique visual identity

---

## 3. 3D Physics

### Collision Shapes

| Shape | Use Case |
|-------|----------|
| **Box** | Buildings, crates |
| **Sphere** | Balls, quick checks |
| **Capsule** | Characters |
| **Mesh** | Terrain (expensive) |

### Principles

- Simple colliders, complex visuals
- Layer-based filtering
- Raycasting for line-of-sight

---

## 4. Camera Systems

### Camera Types

| Type | Use |
|------|-----|
| **Third-person** | Action, adventure |
| **First-person** | Immersive, FPS |
| **Isometric** | Strategy, RPG |
| **Orbital** | Inspection, editors |

### Camera Feel

- Smooth following (lerp)
- Collision avoidance
- Look-ahead for movement
- FOV changes for speed

---

## 5. Lighting

### Light Types

| Type | Use |
|------|-----|
| **Directional** | Sun, moon |
| **Point** | Lamps, torches |
| **Spot** | Flashlight, stage |
| **Ambient** | Base illumination |

### Performance Consideration

- Real-time shadows are expensive
- Bake when possible
- Shadow cascades for large worlds

---

## 6. Level of Detail (LOD)

### LOD Strategy

| Distance | Model |
|----------|-------|
| Near | Full detail |
| Medium | 50% triangles |
| Far | 25% or billboard |

---

## 7. Anti-Patterns

| ❌ Don't | ✅ Do |
|----------|-------|
| Mesh colliders everywhere | Simple shapes |
| Real-time shadows on mobile | Baked or blob shadows |
| One LOD for all distances | Distance-based LOD |
| Unoptimized shaders | Profile and simplify |

---

> **Remember:** 3D is about illusion. Create the impression of detail, not the detail itself.


## When to Use

- **Building a 3D game** — Unity, Unreal, or Godot.
- **Setting up the render pipeline** — URP/HDRP (Unity),
  Blueprint/ Niagara (UE), or Godot's Vulkan renderer.
- **Asset pipeline** — import FBX/glTF, set up LODs, configure
  texture compression.
- **Lighting** — baked vs real-time, lightmaps, probes.
- **Performance** — draw call batching, occlusion culling,
  GPU instancing.

Avoid using this skill for:
- 2D games (use `@2d-games`).
- VR/AR (use `@vr-ar`).
- Multiplayer (use `@multiplayer`).

## Anti-Patterns

- **Don't use uncompressed textures** — use ASTC (mobile),
  BCn (desktop), or KTX2 with basis compression.
- **Don't render objects outside the camera frustum** — use
  occlusion culling, especially for dense scenes.
- **Don't use real-time lighting for static scenes** — bake
  lightmaps. Real-time lights are expensive.
- **Don't use high-poly models in mobile builds** — use LODs
  aggressively; mobile can drop 80% of geometry and look the same.
- **Don't forget to test on target hardware** — dev machine
  performance is not shipping performance.
- **Don't use forward rendering when deferred is appropriate** —
  match the renderer to your lighting scenario.