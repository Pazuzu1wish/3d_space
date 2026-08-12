# 🚀 3D Cockpit Dogfighter — *Python Space: Snakes in Space*

A from-scratch 3D space-combat sandbox built in pure Python with **pygame-ce** and **NumPy/Numba**. Fly a fighter from a first-person cockpit, dogfight waves of procedurally-flown enemy ships, manage heat/shields/missiles, and chase a high score that persists between sessions.

Inspired by the *Elite Dangerous* combat loop — tight, juicy, controller-first — implemented as an "indie Elite" with zero external game engine.

> **North star (from the design bible):** An indie Elite Dangerous. Start with a tight combat sandbox. Build outward. Never refactor twice.

---

## ✨ Features

**Flight Model**
- Full 6-degrees-of-freedom Newtonian flight on unit quaternions (pitch / yaw / roll).
- Throttle, retro-thrust, drag, terminal velocity, and a **drift mode** toggle (kill throttle, keep momentum).
- Analog **dodge** maneuver on a cooldown, with screen flash + rumble.

**Combat**
- Dual wingtip **lasers** with a heat/overheat system — spread and SFX worsen as heat climbs.
- **Homing missiles** with a 2-second lock-on aided by an aim-FOV check (10 max ammo).
- **Targeting computer**: lock nearest visible enemy (`T`), cycle targets in FOV (`Y` / D-Pad Up). Stealthed enemies are skipped.
- Shield + hull damage model with regenerating shields (delay-based) and `take_damage` screen shake / rumble.

**Enemies** — 7 classes in `src/enemy.py`, each with its own AI state machine, mesh, Newtonian physics profile, and engine trail:
| Enemy | HP | Behaviour |
|---|---|---|
| **SuicideDrone** | 1 | Weave/spiral/corkscrew approach, proximity detonation with radial falloff |
| **Dogfighter** | 10 | Circle-strafe positioning ↔ predictive attack runs; evasive barrel-rolls when you aim at it |
| **Sniper** | 1 | Long-range charging beam; raycast LOS-blocked by asteroids/enemies; flees when you close in |
| **StealthInterceptor** | 2 | Stealths while flanking, uncloaks for a 7-shot shotgun pass, then re-cloaks |
| **Minelayer** | 12 | Stealths, drops proximity **Mines**, defends with a heavy MG when cornered |
| **Mine** | 1 | Stationary blinking AoE explosive — triggers on player/asteroid/enemy proximity |
| **Corvette** | 30 | Heavy gunship; turret fire and SuicideDrone spawning |
| **Carrier** | 100 | Capital ship — sniper beam + homing bolts + point-defence MG + drone/fighter spawning |

**Game Flow** (implemented as a state stack in `src/state.py`)
- **Title state** — a scripted cinematic intro (`TitleCinematic`): dogfighter fly-by, drone swarm formation, explosion shockwave, animated title drop, then menu.
- **Gameplay state** — endless Arcade mode driven by a `WaveDirector`.
- **Pause state** — orbit-camera photo mode, trail-colour picker, tactical stats sidebar.
- **GameOver state** — animated score breakdown (kills × accuracy/survival/damage modifiers), top-10 high scores.

**Wave Director** (`src/director.py`)
- Endless, procedural waves that always spawn around the *player's current position* — no flying back to a fixed spawn point.
- Threat-budget composition; cheaper enemies dominate early, expensive types (`Carrier` only unlocks at wave 12) scale in as the run goes on.
- Shrinking intermission rest period (floored at 1.5s so it never vanishes).

**Presentation**
- Custom software 3D pipeline: `math_engine.py` (quaternions, batched world→camera→projection via **Numba**), `renderer.py` (face batching, painter's-sort, frustum cull), `camera.py` (screen shake).
- Baked OBJ/MTL meshes (`mesh_loader.py`) for all ships, pre-converted to NumPy arrays.
- Neon **cockpit HUD** (`cockpit.py` + `hud_data.py`): throttle ladder, prograde indicator, shield/HP/heat bars, ammo, target lock timer, damage overlay, FPS toggle.
- **L2 aim scope** — magnified zoom window with crosshair for precision shots.
- Volumetric engine trails via vectorised `object_pool.TrailPool` (zero per-frame allocation); 8 swappable neon trail colours.
- Starfields, nebula system, asteroid fields (with splitting), and a space station model.

**Input** (`src/controller.py` — `DS4Input`)
- DualShock 4 / DualSense first-class, with auto-fallback profiles for Xbox, Switch Pro, and generic gamepads via the SDL2 GameController API.
- Radial deadzones, normalised triggers, synthesised D-Pad button events, hotplug support, and rumble helpers (`pulse`, `punch`, `buzz`, `wave`).
- Full keyboard fallback (WASD pitch/roll, arrows yaw/throttle, Space fire, X missile, T/Y targeting, F drift, etc.).

**Persistence** (`src/save_data.py`)
- `save.json` stores the top 10 runs (kills list, survival time, accuracy, damage taken, final score).
- `RunResult` scores with kill-points table × accuracy modifier × survival modifier × damage modifier.

---

## 🎮 Controls

### PlayStation controller (primary)
| Action | Input |
|---|---|
| Pitch / Roll | Left stick |
| Yaw | Right stick X |
| Throttle up / down | `R1` / `L1` |
| Fire lasers | `R2` |
| Fire missile | `Square` |
| Aim scope (zoom) | `L2` (analog) |
| Drift mode toggle | `R3` |
| Dodge (with stick direction) | `Circle` + left stick |
| Target nearest / cycle | `Triangle` / D-Pad Up |
| Pause | `Options` |
| Toggle HUD overlays | D-Pad Left / Right / Down |

### Keyboard
| Action | Keys |
|---|---|
| Pitch / Roll | `W` `S` `A` `D` |
| Yaw | `←` `→` |
| Throttle | `↑` `↓` |
| Fire lasers | `Space` |
| Fire missile | `X` |
| Aim scope | `LShift` |
| Drift mode | `F` |
| Target nearest / cycle | `T` / `Y` |
| Pause | `P` |
| Toggle prograde / coords / fps | `H` `C` `O` |
| Quit | `Esc` |

---

## 🏗️ Project Structure

```
3d_space/
├── main.py                  # entry point — boots Game().main()
├── save.json                # persisted high scores (gitignored in spirit)
├── requirements.txt         # pygame-ce, numpy, numba
├── src/
│   ├── game.py              # Game context: pygame init, sound, main loop, StateManager
│   ├── state.py             # State stack — Title / Gameplay / Pause / GameOver
│   ├── constants.py         # all tunable balance & UI constants in one place
│   ├── player.py            # Player ship: flight, shields, heat, targeting, trails
│   ├── enemy.py            # 7 enemy classes + movement patterns + Mine
│   ├── weapon_system.py     # fire_lasers / fire_missile
│   ├── laser.py / missile.py / projectile.py
│   ├── director.py          # WaveDirector — endless procedural waves
│   ├── level.py             # BaseLevel / ArcadeLevel (environment + score/combo)
│   ├── ship_ai.py           # voice-line call-out state machine (triggered off director)
│   ├── encounters.py        # encounter helpers
│   ├── physics.py / math_engine.py     # Newtonian integration + Numba vectorised maths
│   ├── camera.py / renderer.py / cockpit*.py / hud_data.py / aim_scope.py
│   ├── star.py / nebula.py / asteroid.py / space_station.py
│   ├── object_pool.py / spatial_partition.py  # zero-alloc pools + broadphase
│   ├── mesh_loader.py       # baked OBJ/MTL → NumPy arrays
│   ├── sound_handler.py     # SFX bank + dynamic engine hum
│   ├── title_screen.py      # TitleCinematic intro
│   ├── save_data.py         # RunResult + SaveData (JSON persistence)
│   ├── controller.py        # DS4Input multi-gamepad abstraction + debugger UI
│   └── utils.py             # damages overlays, spawn helpers
├── assets/
│   ├── *.obj / *.mtl        # ship & station meshes (player, drone, dogfighter, sniper,
│   │                        #   interceptor, minelayer, corvette, carrier, station1)
│   ├── sounds/              # SFX, BGM, voice call-outs
│   └── fonts/interdictionexpand.ttf
├── tools/                   # offline dev tools (NOT used at runtime)
│   ├── 3d_viewer.py / 2d_viewer.py / 3d_viewer_debug_claude.py
│   ├── mesh_editor.py / mesh_exporter.py
│   └── generate_sfx.py / generate_voice_lines.py
├── tests/                   # benchmarks + sanity tests (star opt, sound, controller)
├── scratch/                 # throwaway debug scripts
├── extra_docs/             # design bible, optimization & collision-system write-ups
└── .agents/rules/graphify.md  # graphify knowledge-graph workflow
```

### Architecture in one paragraph
The main loop is a conductor, not a performer — it dispatches `dt` and events to the active `GameState` on a stack (`StateManager`). States own their update/draw/input cycle; systems (physics, weapons, audio, AI) don't import each other and communicate through the `Game` context. `SaveData` is the single source of truth for anything that persists.

---

## ▶️ Getting Started

### Requirements
- Python 3.10+
- A **DualShock 4 / DualSense** is the recommended input device. Xbox / Switch Pro / generic gamepads auto-fallback. Keyboard works too.

### Install
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt    # pygame-ce, numpy, numba
```

### Run
```bash
python main.py
```
The window opens fullscreen at `1280×760` (`FULLSCREEN = True` in `constants.py`) with the title cinematic; press any key to skip to the menu, then select **ARCADE** to play.

---

## 🔧 Tuning

All gameplay numbers live in `src/constants.py` — flight rates, weapon damage/heat/cooldowns, spawn distances, dodge impulse, sniper charge time, screen-shake decay, colour palette, and window mode. The wave roster / cost weights live in `src/director.py:_WAVE_ROSTER`.

Run a netcode/balance tweak, then rerun — there's no build step.

---

## 🧪 Testing & Benchmarks

```bash
python tests/test_optimizations.py     # unit checks for hot paths
python tests/benchmark_star_optimization.py
python tests/benchmark_realistic.py
python tests/test_sound.py            # audio init + SFX sanity
python tools/3d_viewer.py              # standalone mesh viewer
python tools/generate_sfx.py           # regenerate SFX assets
python src/controller.py              # standalone DS4 debugger GUI
```
Scripts in `scratch/` (`diagnose_controller.py`, `verify_numba.py`, `test_trail.py`, ...) are throwaway diagnostics — safe to delete.

---

## 📚 Further Reading

Deeper design write-ups and post-mortems live in `extra_docs/`:
- `GDD_Ideal_not_current.md` — the design bible (philosophy, target architecture, future modes)
- `QUICK_REFERENCE.md` — star-batching optimization notes
- `STAR_OPTIMIZATION_SUMMARY.md`, `OPTIMIZATION_RENDERING_FACES.md`, `OPTIMIZATION_SUMMARY.md`
- `COLLISION_SYSTEM_UPDATE.md`, `COLLISION_AVOIDANCE_SYSTEM.md`, `COLLISION_FIX_SUMMARY.md`
- `SPAWN_IMMUNITY_SYSTEM.md`, `INTEGRATION_EXAMPLE.md`

A graphify knowledge graph is generated at `graphify-out/` — use `graphify query "<question>"` for codebase/architecture nav instead of grepping.

---

## 📝 License

MIT — Copyright © 2026 Anthony A. Andrews. See [`LICENSE`](LICENSE).

---

## 🛣️ Roadmap (stubs from the design bible)

- Galaxy map + station trading states (currently stubbed in `GDD_Ideal_not_current.md`)
- Persistent commander, credits, reputation, ship loadout (Phase 2 fields already stubbed in `SaveData`)
- Friendly/neutral ship alignments (`enemy.py` is `# TODO: rename to ship`)
- GPU-accelerated star batching
