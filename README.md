🚀 3D Cockpit Space Dogfighter

A high-performance, retro-futurist 3D space combat dogfighter built from scratch
in Python using Pygame, NumPy, and Numba. Inspired by classic space flight
simulators (Descent, Wing Commander, Star Fox, Terminal Velocity, Wing
Commander), this game features custom software 3D rendering, quaternion flight
physics, a full cockpit HUD, magnified aim scope, dynamic tactical voice AI, and
an endless procedural wave director.

🌟 Key Features

🎨 Custom Software 3D Graphics Pipeline

  - Batch Vertex & Face Processing: Powered by Numba JIT compilation and NumPy
    matrix math for near-GPU-speed software rendering.
  - OBJ Mesh Loader & Cache: Pre-baked OBJ/MTL 3D mesh parser for complex
    capital ships, stations, and fighters.
  - Volumetric Effects: Semi-transparent multi-puff nebula clouds, procedural
    starfields, and particle explosion bursts.
  - Procedural Asteroid Fields: Jittered icosahedron meshes that dynamically
    fragment and split into physical debris upon destruction.

🕹️ Flight Physics & Mechanics

  - 6-DOF Quaternion Flight Model: Body-local pitch, yaw, and roll calculations
    free of gimbal lock.
  - Flight Drift Mode (Inertial Decoupling): Toggle engine thrust off to rotate
    and fire in any direction while maintaining orbital momentum.
  - Evasive Dodging: High-impulse thruster dodge maneuver with dynamic cooldown
    and visual feedback.
  - Customizable Engine Trails: Fixed-capacity ring-buffer particle trails
    with 8 selectable neon palette themes (Hyper Cyan, Solar Orange, Void
    Purple, etc.).

🖥️ Immersive Cockpit & Tactical HUD

  - Holosphere 3D Radar: Pseudo-3D isometric sensor sphere with elevation stems,
    depth cueing, directional headings, and player velocity vectors.
  - Flight Instruments: Flight pitch ladder, heading compass tape, coordinates
    readout, and prograde/retrograde velocity markers.
  - Targeting & Lead PIP: Target locking system with distance/hull stats,
    missile lock-on reticle, and calculated lead intercept point (PIP).
  - Magnified Aim Scope (Picture-in-Picture): Real-time dual-pass zoomed scope
    window for precision long-range sniping.

👾 Enemy AI & Wave Progression

  - 8 Enemy Classes:
      - Suicide Drone: Swarmers that rush and detonate on proximity.
      - Dogfighter: Agile fighters performing evasive barrel rolls and
        predictive lead-angle shooting.
      - Sniper: Long-range railgun platforms that telegraph beam charges.
      - Minelayer: Stealthy cross-pattern ships dropping proximity explosive
        mines.
      - Stealth Interceptor: Cloaked flankers firing close-range shotgun bursts.
      - Corvette & Carrier: Heavy capital ships with multi-turret batteries and
        fighter-launching capabilities.
  - Endless Wave Director: Procedurally scales wave threat budgets, unlocks
    harder enemy rosters, and spawns encounters near the player.
  - Spatial Broadphase Partitioning: Vectorized NumPy/Numba broadphase for
    collision detection and frustum culling.

🔊 Dynamic Audio & Voice AI (ShipAI)

  - Tactical Voice Announcements: Priority-queued voice clip warnings for low
    shields, hull breach, incoming homing missiles, weapon overheating, and
    capital ship encounters.
  - Synthetic Multi-Layer Engine Hum: Dynamic 4-channel audio blending reacting
    to engine throttle and rotational control inputs.
  - Audio Optimization: Low-overhead voice channel limiting and zero-resampling
    WAV header verification.

🎮 Controller & Gamepad Support

  - Native Gamepad Integration: Autodetect for DS4, DualSense, Xbox, and Switch
    controllers via SDL2 GameController API.
  - Full Haptic Support: Context-aware rumble feedback for firing lasers,
    missile launches, and taking damage.
  - Built-in Controller Debugger: Interactive input analyzer and visual layout
    mapper (src/controller.py).

📐 Controls

Gamepad Controls (DualShock 4 / DualSense / Xbox)

| Input                      | Action                                       |
| :------------------------- | :------------------------------------------- |
| **Left Stick**             | Pitch & Roll                                 |
| **Right Stick**            | Yaw                                          |
| **R1 / L1**                | Increase / Decrease Throttle                 |
| **R2 (Right Trigger)**     | Fire Main Blasters                           |
| **L2 (Left Trigger)**      | Hold for Magnified Aim Scope (Variable Zoom) |
| **Square (X on Xbox)**     | Launch Missile (Homing if locked)            |
| **Circle (B on Xbox)**     | Evasive Dodge / Thruster Boost               |
| **R3 (Right Stick Click)** | Toggle Drift Mode (Inertial Decoupling)      |
| **DPad Up**                | Target Nearest / Cycle Targets               |
| **DPad Left**              | Toggle Waypoints HUD                         |
| **DPad Right**             | Toggle Prograde Marker                       |
| **DPad Down**              | Toggle Coordinates Readout                   |
| **Options / Start**        | Pause Game / Access Photo Orbit Camera       |

Keyboard & Mouse Controls

| Key                          | Action                                     |
| :--------------------------- | :----------------------------------------- |
| **W / S**                    | Pitch Up / Pitch Down                      |
| **A / D**                    | Roll Left / Roll Right                     |
| **Left Arrow / Right Arrow** | Yaw Left / Yaw Right                       |
| **Up Arrow / Down Arrow**    | Incremental Throttle Up / Down             |
| **Spacebar**                 | Fire Main Blasters                         |
| **Left Shift**               | Activate Magnified Aim Scope               |
| **X**                        | Launch Missile                             |
| **F**                        | Toggle Drift Mode                          |
| **T / Y**                    | Target Closest Enemy / Cycle Targets       |
| **H**                        | Toggle Prograde / Retrograde Vector Marker |
| **C**                        | Toggle Coordinates Display                 |
| **O**                        | Toggle FPS Counter                         |
| **P or ESC**                 | Pause Game                                 |

🛠️ Installation & Setup

Prerequisites

  - Python 3.10+ (Python 3.11 or 3.12 recommended)

1. Clone the Repository

git clone https://github.com/your-username/3d-cockpit-dogfighter.git
cd 3d-cockpit-dogfighter

2. Create a Virtual Environment (Optional but Recommended)

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

3. Install Dependencies

pip install pygame numpy numba

4. Run the Game

python game.py

🕹️ Controller Input Debugger

The repository includes an interactive controller visualizer tool to test axis
mapping, deadzones, trigger response, and button inputs:

python src/controller.py --mode all --deadzone 0.20

📂 Project Architecture

.
├── game.py                  # Game application entry point & state loop
├── save.json                # Persistent high scores & run stats
├── assets/                  # 3D .obj/.mtl models, fonts, audio & voice clips
└── src/
    ├── aim_scope.py         # Secondary render-pass magnified aim scope
    ├── asteroid.py          # Procedural icosahedron asteroids & splitting mechanics
    ├── camera.py            # 3D Camera, rotation matrices, frustum culling & shake
    ├── cinematic_motion.py  # Scripted motion steps for title sequences & swarms
    ├── cockpit.py           # HUD drawing (Compass, Pitch Ladder, Radar, Target Brackets, PIP)
    ├── cockpit_geometry.py  # Low-poly retro cockpit frame drawing
    ├── constants.py         # Game balance, UI colors, and speed constants
    ├── controller.py        # Controller abstraction layer & input visualizer
    ├── director.py          # Wave Director for endless procedural wave encounters
    ├── enemy.py             # Enemy AI ship behaviors (Drone, Dogfighter, Sniper, Carrier, etc.)
    ├── hud_data.py          # Dataclass container for HUD overlay state
    ├── laser.py             # Blaster projectile implementation
    ├── level.py             # Arcade mode level, score multipliers, and objectives
    ├── math_engine.py       # Numba-accelerated quaternion & projection math
    ├── mesh_loader.py       # OBJ/MTL loader and BakedMesh caching engine
    ├── missile.py           # Unguided and Homing Missile mechanics
    ├── nebula.py            # Volumetric nebula particle cloud system
    ├── object_pool.py       # Fast NumPy memory pools for particles, lasers, & trails
    ├── particle.py          # Visual particle effect entities
    ├── physics.py           # Newtonian flight & player throttle integration
    ├── player.py            # Player state, controls, heat, shields, & engine trail
    ├── projectile.py        # Enemy weapon bolts, beams, and mines
    ├── renderer.py          # Core 3D Software Render Pipeline (Numba face-shading)
    ├── save_data.py         # Run results & JSON persistence
    ├── ship_ai.py           # Voice AI event priority monitor & tactical warnings
    ├── sound_handler.py     # SFX manager, WAV header validator, dynamic engine hum
    ├── space_station.py     # Station entity model
    ├── spatial_partition.py # Broadphase spatial query engine
    ├── star.py              # Procedural starfield with batch processing
    ├── state.py             # State Manager (Title, Gameplay, Pause, GameOver)
    ├── title_screen.py      # Cinematic title sequence
    ├── utils.py             # Enemy spawners & UI overlay helpers
    └── weapon_system.py     # Weapon firing logic (lasers & missiles)

⚡ Performance & Optimization Notes

  - Numba JIT Warmup: On the first launch, Numba compiles its vector kernels. A
    lightweight warmup pass runs during game initialization to eliminate
    hitching on the first frame of gameplay.
  - Zero-Resampling Audio: SoundHandler validates WAV file sample rates
    (44.1kHz 16-bit stereo) at boot to ensure the CPU doesn't waste cycles
    resampling audio streams during action-heavy moments.
  - Contiguous Ring Buffers: Particle trails and broadphase spatial lookups use
    pre-allocated NumPy arrays to avoid runtime Python memory allocations and
    garbage collection stutter.

📜 License

Distributed under the MIT License. See LICENSE for more information.

