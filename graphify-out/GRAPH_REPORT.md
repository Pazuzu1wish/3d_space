# Graph Report - 3d_space  (2026-05-19)

## Corpus Check
- 44 files · ~49,810 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 942 nodes · 1434 edges · 65 communities (48 shown, 17 thin omitted)
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 223 edges (avg confidence: 0.65)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f6c989dd`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_3D Debug Rendering & Viewers|3D Debug Rendering & Viewers]]
- [[_COMMUNITY_3D Mathematics & Matrix Engine|3D Mathematics & Matrix Engine]]
- [[_COMMUNITY_HUD Drawing & Instrument Renderers|HUD Drawing & Instrument Renderers]]
- [[_COMMUNITY_Asteroid Generation & Mesh Rendering|Asteroid Generation & Mesh Rendering]]
- [[_COMMUNITY_Core Object Pooling Infrastructure|Core Object Pooling Infrastructure]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Enemy Ships & Visual Trails|Enemy Ships & Visual Trails]]
- [[_COMMUNITY_Cockpit Frame UI Panel Geometry|Cockpit Frame UI Panel Geometry]]
- [[_COMMUNITY_Engine Optimization Documentation|Engine Optimization Documentation]]
- [[_COMMUNITY_Enemy Projectiles & Weapon Behaviors|Enemy Projectiles & Weapon Behaviors]]
- [[_COMMUNITY_Spatial Hash Grid Implementation|Spatial Hash Grid Implementation]]
- [[_COMMUNITY_DS4 Input Controller Handler|DS4 Input Controller Handler]]
- [[_COMMUNITY_Particle Effects Spawning & Pools|Particle Effects Spawning & Pools]]
- [[_COMMUNITY_Player Ship Flight Mechanics|Player Ship Flight Mechanics]]
- [[_COMMUNITY_Utility Functions & Enemy Spawners|Utility Functions & Enemy Spawners]]
- [[_COMMUNITY_3D Face Transform & Screen Projection|3D Face Transform & Screen Projection]]
- [[_COMMUNITY_Camera Navigation & Render Loop|Camera Navigation & Render Loop]]
- [[_COMMUNITY_Laser Pooling & Fire Management|Laser Pooling & Fire Management]]
- [[_COMMUNITY_Laser Projectile Reinitialization|Laser Projectile Reinitialization]]
- [[_COMMUNITY_Controller Haptics & Vibration|Controller Haptics & Vibration]]
- [[_COMMUNITY_Enemy Ship Base Navigation AI|Enemy Ship Base Navigation AI]]
- [[_COMMUNITY_Controller D-Pad HUD Widget|Controller D-Pad HUD Widget]]
- [[_COMMUNITY_Encounter Spawn Director & AI|Encounter Spawn Director & AI]]
- [[_COMMUNITY_Controller Button HUD Grid|Controller Button HUD Grid]]
- [[_COMMUNITY_Scripted Encounter Timelines|Scripted Encounter Timelines]]
- [[_COMMUNITY_Optimization Suite Unit Tests|Optimization Suite Unit Tests]]
- [[_COMMUNITY_Corvette Heavy Fighter AI|Corvette Heavy Fighter AI]]
- [[_COMMUNITY_Sniper Flank Enemy AI|Sniper Flank Enemy AI]]
- [[_COMMUNITY_Star Rendering Optimization Docs|Star Rendering Optimization Docs]]
- [[_COMMUNITY_Octree Spatial Partition Tests|Octree Spatial Partition Tests]]
- [[_COMMUNITY_Bounding Box Geometry Tests|Bounding Box Geometry Tests]]
- [[_COMMUNITY_Star Rendering & Lifecycle|Star Rendering & Lifecycle]]
- [[_COMMUNITY_HUD Controller Event Logger|HUD Controller Event Logger]]
- [[_COMMUNITY_Trigger Input Normalisation|Trigger Input Normalisation]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Carrier Bounding Box Collision|Carrier Bounding Box Collision]]
- [[_COMMUNITY_Individual Particle Physics|Individual Particle Physics]]
- [[_COMMUNITY_Batch Color Numba Benchmark|Batch Color Numba Benchmark]]
- [[_COMMUNITY_Analog Stick HUD Widget|Analog Stick HUD Widget]]
- [[_COMMUNITY_Numba Vectorized Projection|Numba Vectorized Projection]]
- [[_COMMUNITY_Cockpit Shield Integrity Data|Cockpit Shield Integrity Data]]
- [[_COMMUNITY_Weapon Cooldown Status Data|Weapon Cooldown Status Data]]
- [[_COMMUNITY_Trigger Mapping Utilities|Trigger Mapping Utilities]]
- [[_COMMUNITY_Star Batch Submission Pipeline|Star Batch Submission Pipeline]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 72|Community 72]]

## God Nodes (most connected - your core abstractions)
1. `Enemy` - 29 edges
2. `DS4Input` - 28 edges
3. `SpatialPartition` - 26 edges
4. `ObjectPool` - 24 edges
5. `ParticlePool` - 24 edges
6. `draw_cockpit_hud()` - 23 edges
7. `SpatialHash` - 20 edges
8. `LaserPool` - 20 edges
9. `main()` - 20 edges
10. `DebugViewer` - 20 edges

## Surprising Connections (you probably didn't know these)
- `Spatial Partitioning` --rationale_for--> `SpatialPartition`  [INFERRED]
  extra_docs/OPTIMIZATION_SUMMARY.md → src/spatial_partition.py
- `Object Pooling` --rationale_for--> `ObjectPool`  [INFERRED]
  extra_docs/OPTIMIZATION_SUMMARY.md → src/object_pool.py
- `Numba JIT Position Wrapping` --rationale_for--> `wrap_star_positions_batch()`  [INFERRED]
  extra_docs/STAR_OPTIMIZATION_SUMMARY.md → src/star.py
- `Batch Star Submission` --rationale_for--> `submit_batch_to_renderer()`  [INFERRED]
  extra_docs/STAR_OPTIMIZATION_SUMMARY.md → src/star.py
- `=============================================================================` --cites--> `ParticlePool`  [EXTRACTED]
  extra_docs/INTEGRATION_EXAMPLE.md → src/object_pool.py

## Hyperedges (group relationships)
- **Game Engine Optimization Framework** — src_object_pool_objectpool, src_spatial_partition_spatialpartition, src_star_wrap_star_positions_batch [INFERRED 0.85]

## Communities (65 total, 17 thin omitted)

### Community 0 - "3D Debug Rendering & Viewers"
Cohesion: 0.08
Nodes (29): _cross(), DebugViewer, _dot(), face_normal_and_center(), _FallbackShip, mesh_centroid(), _project(), _quat_conj() (+21 more)

### Community 1 - "3D Mathematics & Matrix Engine"
Cohesion: 0.07
Nodes (32): get_basis_vectors(), get_forward_vector(), get_right_from_quat(), get_right_vector(), is_in_front_of_camera(), project_to_screen(), quat_from_axis_angle(), quat_identity() (+24 more)

### Community 2 - "HUD Drawing & Instrument Renderers"
Cohesion: 0.07
Nodes (55): _cached_label(), custom_font(), _draw_active_bracket(), draw_cockpit_hud(), draw_coordinates(), draw_crosshair(), _draw_dim_bracket(), draw_dodge_bg() (+47 more)

### Community 3 - "Asteroid Generation & Mesh Rendering"
Cohesion: 0.06
Nodes (17): Asteroid, AsteroidField, Create smaller fragments that explode away from each other., Game, Render a secondary pass for the magnified aim window., Render a secondary pass for the magnified aim window., Render a secondary pass for the magnified aim window., Render a secondary pass for the magnified aim window. (+9 more)

### Community 4 - "Core Object Pooling Infrastructure"
Cohesion: 0.07
Nodes (19): Object Pooling, Spatial Partitioning, ObjectPool, Generic object pool for managing reusable entities., Initialize the object pool.                  Args:             factory: Function, Default reset does nothing - override for specific types., Acquire an object from the pool.                  Returns None if pool is exhaus, Return an object to the pool for reuse. (+11 more)

### Community 5 - "Community 5"
Cohesion: 0.38
Nodes (3): True when close to target and still closing fast — signal to flip and brake., StealthInterceptor, StealthShotgun

### Community 6 - "Enemy Ships & Visual Trails"
Cohesion: 0.13
Nodes (9): DefaultEnemyShip, EntityViewer, entity_viewer.py ---------------- Standalone entity inspection tool. Load any dr, Rotate + scale a list of (x, y) unit coords around cx, cy., Transform a single local point., Call once per frame to keep trail particles alive., Interactive viewer. Pass an entity_factory callable that returns     an object w, Map horizontal mouse drag → rotation angle. (+1 more)

### Community 7 - "Cockpit Frame UI Panel Geometry"
Cohesion: 0.09
Nodes (33): _build_static(), _c(), draw_cockpit_frame(), _hex_plate(), _inset_panel(), interpolate_color(), _l(), _p() (+25 more)

### Community 8 - "Engine Optimization Documentation"
Cohesion: 0.13
Nodes (11): =============================================================================, Query all entities that might be visible to the camera.         Uses cell-level, Query all entities that might be visible to the camera.         Uses cell-level, Clear all entities from the hash., Clear all entities from the hash., Main spatial partitioning manager for the game.     Manages entity lifecycle and, SpatialPartition, Tests for combined spatial partition system. (+3 more)

### Community 9 - "Enemy Projectiles & Weapon Behaviors"
Cohesion: 0.13
Nodes (7): Dogfighter, CorvetteTurret, EnemyProjectile, HomingBolt, MachineGunBolt, Check if this projectile hits the player. Returns True if collision occurred., Check if this projectile hits an asteroid. Returns True if collision occurred.

### Community 10 - "Spatial Hash Grid Implementation"
Cohesion: 0.20
Nodes (7): Spatial Partitioning System Efficient collision detection and entity culling usi, Efficient spatial partitioning using a hash grid.     Optimized for fast inserti, SpatialHash, Tests for spatial hash grid., Test inserting and querying with spatial hash., Test clearing spatial hash., TestSpatialHash

### Community 11 - "DS4 Input Controller Handler"
Cohesion: 0.11
Nodes (11): DS4Input, Clear single-frame sets. Call exactly ONCE per frame,         AFTER processing a, True every frame the button is down., All buttons currently held., Left stick (x, y) with deadzone applied, –1..1., Right stick (x, y) with deadzone applied, –1..1., Raw hat value: (dx, dy) where each component is –1, 0, or 1., Human-readable D-pad direction, or 'neutral'. (+3 more)

### Community 12 - "Particle Effects Spawning & Pools"
Cohesion: 0.09
Nodes (16): ParticlePool, Spawn a particle at the given position., Spawn a particle at the given position., Update all active particles using NumPy vectorization and recycle dead ones., Update all active particles and recycle dead ones., Batch submit active particles to the renderer with frustum culling., Batch submit active particles to the renderer with frustum culling., Legacy shim for compatibility with existing game.py loops. (+8 more)

### Community 13 - "Player Ship Flight Mechanics"
Cohesion: 0.28
Nodes (5): Rotate nose toward desired_heading at turn_rate, fire main thrust,         apply, SuicideDrone, get_forward_from_quat(), Extract just the forward (Z) vector from a quaternion — avoids full basis build., SniperBeam

### Community 14 - "Utility Functions & Enemy Spawners"
Cohesion: 0.14
Nodes (18): draw_damage_overlay(), _forward_spawn_pos(), Carriers are boss-scale — spawn far ahead and slightly above so     they dominat, Generic factory — maps a string type to the right spawn function., Red vignette that fades in when the player is hit., Shared geometry for all forward-arc spawns.     Returns (x, y, z) — a world posi, Snipers hang back further than normal enemies so their railgun     has room to t, Corvettes spawn at standard range but with a tighter yaw cone     so they appear (+10 more)

### Community 15 - "3D Face Transform & Screen Projection"
Cohesion: 0.06
Nodes (28): Batch Star Submission, Numba JIT Position Wrapping, process_faces_batch_numba(), Submit a whole mesh for optimized rendering.         Uses Numba-optimized batch, Submit a single polygon., Submit a single polygon., Submit a 2D circle sprite., Submit a soft, semi-transparent nebula puff. (+20 more)

### Community 16 - "Camera Navigation & Render Loop"
Cohesion: 0.10
Nodes (9): test_batch_projection(), Camera, Fast frustum culling using a bounding sphere.         Returns (visible, cx, cy,, Transform world point to camera space using pre-computed rotation matrix., Transform batch of world points to camera space using Numba., Project batch of camera-space points to screen space using Numba., sphere_in_frustum_batch(), project_to_screen_batch() (+1 more)

### Community 17 - "Laser Pooling & Fire Management"
Cohesion: 0.11
Nodes (12): LaserPool, Object Pooling System Efficiently manages reusable game objects to avoid frequen, Specialized pool for laser projectiles., Specialized pool for laser projectiles., Fire a laser from the given position with the given velocity., Fire a laser from the given position with the given velocity., Update all active lasers and recycle expired ones., Update all active lasers and recycle expired ones. (+4 more)

### Community 18 - "Laser Projectile Reinitialization"
Cohesion: 0.14
Nodes (9): Laser, Reinitialize laser with new values (for object pooling)., Reset laser to default state (for object pooling)., Initialize a laser. Can be initialized with player orientation or with explicit, Test laser class compatibility with pooling., Test laser can be initialized with explicit parameters., Test laser can be reinitialized for pooling., Test laser reset for pooling. (+1 more)

### Community 19 - "Controller Haptics & Vibration"
Cohesion: 0.13
Nodes (7): Connect to the joystick. Returns True if successful., Trigger controller rumble. DS4 has two motors:         - low_frequency: left mot, Stop all rumble immediately., Simple pulse: both motors at same intensity.         intensity: 0.0–1.0, Sharp punch feeling: high-frequency spike (short duration).         intensity: 0, Continuous buzz: low-frequency vibration.         intensity: 0.0–1.0, Wave effect: both motors ramping up and down.         intensity: 0.0–1.0

### Community 20 - "Enemy Ship Base Navigation AI"
Cohesion: 0.14
Nodes (5): Enemy, Check if a projectile at (px, py, pz) hits this enemy using spherical collision., Check if a projectile at (px, py, pz) hits this enemy using spherical collision., Triggers proximity explosion and deals radial damage to player., Triggers proximity explosion and deals radial damage to player.

### Community 21 - "Controller D-Pad HUD Widget"
Cohesion: 0.23
Nodes (4): DPad, draw_rounded_rect(), lerp_color(), TriggerBar

### Community 23 - "Controller Button HUD Grid"
Cohesion: 0.27
Nodes (4): ButtonGrid, main(), True only on the frame the button went down., True only on the frame the button came up.

### Community 24 - "Scripted Encounter Timelines"
Cohesion: 0.27
Nodes (5): Gradually tighten spawn rate over time (6 s → 2 s floor)., Instantiate all enemies in a scripted encounter., Weighted random filler spawn, respecting per-type caps., Owns the enemy-spawn timeline for a session.      Scripted encounters are placed, WaveDirector

### Community 25 - "Optimization Suite Unit Tests"
Cohesion: 0.05
Nodes (36): Advanced Integration (Full Benefits), code:python (from .object_pool import ParticlePool, LaserPool), code:python (self.particle_pool = ParticlePool(None, initial_size=500, ma), code:python (# Old: self.particles.append(Particle(x, y, z))), code:python (# Old: self.lasers.append(Laser(self.pos, self.orientation))), code:python (# Old: for p in self.particles: p.draw(...)), code:python (# Create a particle pool), code:python (# Create spatial partition) (+28 more)

### Community 28 - "Star Rendering Optimization Docs"
Cohesion: 0.08
Nodes (23): 1. **src/star.py** - Added Optimized Batch Processing, 2. **src/game.py** - Updated Rendering Pipeline, Architecture Benefits, Benchmark: 100 frames at 1920x1080, Changes Made, code:python (@njit(cache=True, fastmath=True)), code:python (@njit(cache=True, fastmath=True)), code:python (@classmethod) (+15 more)

### Community 29 - "Octree Spatial Partition Tests"
Cohesion: 0.17
Nodes (8): Unit tests for object pooling and spatial partitioning systems. Run with: python, Tests for octree spatial partition., Test inserting and querying entities., Test removing entities., Test clearing all entities., Run all tests manually (for environments without pytest)., run_tests(), TestOctreeNode

### Community 30 - "Bounding Box Geometry Tests"
Cohesion: 0.25
Nodes (5): Tests for bounding box utilities., Test point containment., Test box intersection., Test box subdivision into octants., TestBoundingBox

### Community 31 - "Star Rendering & Lifecycle"
Cohesion: 0.06
Nodes (18): Loads and caches sound effect, validating WAV headers to prevent resampling over, Loads and caches sound effect, validating WAV headers to prevent resampling over, Loads and caches sound effect, validating WAV headers to prevent resampling over, Plays sound effect with voice limiting and trigger cooldowns to minimize CPU cyc, Plays sound effect with voice limiting and trigger cooldowns to minimize CPU cyc, Plays sound effect with voice limiting and trigger cooldowns to minimize CPU cyc, Streams BGM from disk to conserve RAM and avoid decompression overhead., Streams BGM from disk to conserve RAM and avoid decompression overhead. (+10 more)

### Community 32 - "HUD Controller Event Logger"
Cohesion: 0.33
Nodes (3): _btn_name(), EventLog, Feed a pygame event to the handler.         Returns True if the event was consum

### Community 33 - "Trigger Input Normalisation"
Cohesion: 0.40
Nodes (3): _normalise_trigger(), L2 normalised to 0..1., R2 normalised to 0..1.

### Community 37 - "Batch Color Numba Benchmark"
Cohesion: 0.11
Nodes (18): After (Faster - 6.9% improvement), Before (Slow), Benchmarking, Code Structure, code:python (# game.py - draw_game() method), code:python (# game.py - draw_game() method), code:block3 (Per-frame savings:  0.096ms), code:bash (python main.py) (+10 more)

### Community 39 - "Numba Vectorized Projection"
Cohesion: 0.08
Nodes (36): generate_armor_hit(), generate_engine_hum(), generate_explosion(), generate_laser(), generate_missile(), generate_music_drone(), generate_shield_hit(), main() (+28 more)

### Community 51 - "Community 51"
Cohesion: 0.12
Nodes (15): 1. Enemy Base Class (`src/enemy.py`, lines 29-30 and 155-159), 2. Carrier Class (`src/enemy.py`, lines 948-1016), 3. Main Game Loop (`src/game.py`, lines 103-127), Changes Made, code:python (# In __init__:), code:python (def __init__(self, x, y, z):), code:python (# Register with hardcoded 50-unit radius), code:python (# Register with each enemy's individual hit_radius) (+7 more)

### Community 52 - "Community 52"
Cohesion: 0.14
Nodes (13): 1. **Enhanced Numba Function Signature**, 2. **Color Shading Computed in Njit**, 3. **Pre-cached Face Arrays**, code:python (def process_faces_batch_numba(cam_verts, projected, face_ind), code:python (def process_faces_batch_numba(cam_verts, projected, face_ind), code:python (# OLD (Python loop after numba)), Future Optimizations, Impact on Ships & Asteroids (+5 more)

### Community 53 - "Community 53"
Cohesion: 0.22
Nodes (8): =============================================================================, =============================================================================, =============================================================================, =============================================================================, =============================================================================, INTEGRATION GUIDE, MIGRATION CHECKLIST, PERFORMANCE BENEFITS

### Community 58 - "Community 58"
Cohesion: 0.33
Nodes (4): Clear all active particles., Clear all active particles., Clear all active lasers., Clear all active lasers.

### Community 64 - "Community 64"
Cohesion: 0.06
Nodes (18): basis_from_forward(), HomingMissile, PlayerMissile, Player, Lock onto the nearest living, non-stealthed enemy within field of view., Lock onto the nearest living, non-stealthed enemy within field of view., Lock onto the nearest living, non-stealthed enemy within field of view., Lock onto the nearest living, non-stealthed enemy within field of view. (+10 more)

### Community 66 - "Community 66"
Cohesion: 0.10
Nodes (13): Register a new entity., Remove an entity from the system., Remove an entity from the system., Update an entity's position incrementally.         Call this every frame for mov, Update an entity's position incrementally.         Call this every frame for mov, Query entities near a position., Query entities near a position., Convert world position to grid cell coordinates using fast truncation. (+5 more)

## Knowledge Gaps
- **78 isolated node(s):** `Workflow: graphify`, `graphify`, `Overview`, `code:python (def process_faces_batch_numba(cam_verts, projected, face_ind)`, `code:python (def process_faces_batch_numba(cam_verts, projected, face_ind)` (+73 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **17 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Game` connect `Asteroid Generation & Mesh Rendering` to `Community 64`, `Engine Optimization Documentation`, `DS4 Input Controller Handler`, `Particle Effects Spawning & Pools`, `3D Face Transform & Screen Projection`, `Camera Navigation & Render Loop`, `Laser Pooling & Fire Management`, `Laser Projectile Reinitialization`, `Scripted Encounter Timelines`, `Star Rendering & Lifecycle`?**
  _High betweenness centrality (0.261) - this node is a cross-community bridge._
- **Why does `WaveDirector` connect `Scripted Encounter Timelines` to `Community 34`, `Asteroid Generation & Mesh Rendering`, `Carrier Bounding Box Collision`, `Community 5`, `Enemy Projectiles & Weapon Behaviors`, `Player Ship Flight Mechanics`, `Laser Pooling & Fire Management`, `Encounter Spawn Director & AI`, `Sniper Flank Enemy AI`?**
  _High betweenness centrality (0.145) - this node is a cross-community bridge._
- **Why does `DS4Input` connect `DS4 Input Controller Handler` to `HUD Controller Event Logger`, `Trigger Input Normalisation`, `3D Mathematics & Matrix Engine`, `Asteroid Generation & Mesh Rendering`, `Laser Pooling & Fire Management`, `Controller Haptics & Vibration`, `Controller D-Pad HUD Widget`, `Controller Button HUD Grid`?**
  _High betweenness centrality (0.123) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `Enemy` (e.g. with `MachineGunBolt` and `HomingBolt`) actually correct?**
  _`Enemy` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `DS4Input` (e.g. with `Game` and `Viewer`) actually correct?**
  _`DS4Input` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `SpatialPartition` (e.g. with `TestObjectPool` and `TestParticlePool`) actually correct?**
  _`SpatialPartition` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `ObjectPool` (e.g. with `TestObjectPool` and `TestParticlePool`) actually correct?**
  _`ObjectPool` has 12 INFERRED edges - model-reasoned connections that need verification._