---
name: vr-ar
description: VR/AR development principles. Comfort, interaction, performance requirements.
allowed-tools: Read, Write, Edit, Glob, Grep
---

# VR/AR Development

> Immersive experience principles.

---

## 1. Platform Selection

### VR Platforms

| Platform | Use Case |
|----------|----------|
| **Quest** | Standalone, wireless |
| **PCVR** | High fidelity |
| **PSVR** | Console market |
| **WebXR** | Browser-based |

### AR Platforms

| Platform | Use Case |
|----------|----------|
| **ARKit** | iOS devices |
| **ARCore** | Android devices |
| **WebXR** | Browser AR |
| **HoloLens** | Enterprise |

---

## 2. Comfort Principles

### Motion Sickness Prevention

| Cause | Solution |
|-------|----------|
| **Locomotion** | Teleport, snap turn |
| **Low FPS** | Maintain 90 FPS |
| **Camera shake** | Avoid or minimize |
| **Rapid acceleration** | Gradual movement |

### Comfort Settings

- Vignette during movement
- Snap vs smooth turning
- Seated vs standing modes
- Height calibration

---

## 3. Performance Requirements

### Target Metrics

| Platform | FPS | Resolution |
|----------|-----|------------|
| Quest 2 | 72-90 | 1832x1920 |
| Quest 3 | 90-120 | 2064x2208 |
| PCVR | 90 | 2160x2160+ |
| PSVR2 | 90-120 | 2000x2040 |

### Frame Budget

- VR requires consistent frame times
- Single dropped frame = visible judder
- 90 FPS = 11.11ms budget

---

## 4. Interaction Principles

### Controller Interaction

| Type | Use |
|------|-----|
| **Point + click** | UI, distant objects |
| **Grab** | Manipulation |
| **Gesture** | Magic, special actions |
| **Physical** | Throwing, swinging |

### Hand Tracking

- More immersive but less precise
- Good for: social, casual
- Challenging for: action, precision

---

## 5. Spatial Design

### World Scale

- 1 unit = 1 meter (critical)
- Objects must feel right size
- Test with real measurements

### Depth Cues

| Cue | Importance |
|-----|------------|
| Stereo | Primary depth |
| Motion parallax | Secondary |
| Shadows | Grounding |
| Occlusion | Layering |

---

## 6. Anti-Patterns

| ❌ Don't | ✅ Do |
|----------|-------|
| Move camera without player | Player controls camera |
| Drop below 90 FPS | Maintain frame rate |
| Use tiny UI text | Large, readable text |
| Ignore arm length | Scale to player reach |

---

> **Remember:** Comfort is not optional. Sick players don't play.


## When to Use

- **Building a VR or AR experience** — choose a platform
  (Quest, Vision Pro, ARKit, ARCore).
- **Setting up comfort settings** — snap turning, vignette,
  teleport locomotion to avoid motion sickness.
- **Hand tracking** — use the platform's SDK (Meta XR, etc.),
  not raw camera input.
- **Performance targets** — VR needs 90 FPS minimum; 72 FPS
  is acceptable for casual content.
- **Spatial UI** — use world-space UI, not screen-space, where
  possible.

Avoid using this skill for:
- 2D-only games (use `@2d-games`).
- 3D non-VR (use `@3d-games`).
- Multiplayer VR (use `@multiplayer` + this skill).

## Anti-Patterns

- **Don't force artificial locomotion** — many users get
  motion sick. Use teleport by default; smooth as opt-in.
- **Don't use dark backgrounds** — low contrast = eye strain in
  headset.
- **Don't put text at fixed distance** — text should be at
  comfortable reading distance (1-3m) and large enough.
- **Don't skip the comfort vignette** — fade-to-black during
  movement is essential for susceptible users.
- **Don't use 2D UI in 3D space without depth** — flat UI at
  fixed Z causes eye strain.
- **Don't ship without testing on actual hardware** — emulator
  performance is not headset performance.
- **Don't ignore controller battery** — many VR users forget to
  charge. Show a battery warning on launch.