# Graph Report - .  (2026-05-17)

## Corpus Check
- Corpus is ~43,772 words - fits in a single context window. You may not need a graph.

## Summary
- 651 nodes · 1120 edges · 51 communities (41 shown, 10 thin omitted)
- Extraction: 80% EXTRACTED · 20% INFERRED · 0% AMBIGUOUS · INFERRED: 219 edges (avg confidence: 0.65)
- Token cost: 12,000 input · 1,500 output

## Community Hubs (Navigation)
- [[_COMMUNITY_3D Debug Rendering & Viewers|3D Debug Rendering & Viewers]]
- [[_COMMUNITY_3D Mathematics & Matrix Engine|3D Mathematics & Matrix Engine]]
- [[_COMMUNITY_HUD Drawing & Instrument Renderers|HUD Drawing & Instrument Renderers]]
- [[_COMMUNITY_Asteroid Generation & Mesh Rendering|Asteroid Generation & Mesh Rendering]]
- [[_COMMUNITY_Core Object Pooling Infrastructure|Core Object Pooling Infrastructure]]
- [[_COMMUNITY_Homing Missile Weapons System|Homing Missile Weapons System]]
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
- [[_COMMUNITY_Stealth Interceptor Enemy AI|Stealth Interceptor Enemy AI]]
- [[_COMMUNITY_Carrier Bounding Box Collision|Carrier Bounding Box Collision]]
- [[_COMMUNITY_Individual Particle Physics|Individual Particle Physics]]
- [[_COMMUNITY_Batch Color Numba Benchmark|Batch Color Numba Benchmark]]
- [[_COMMUNITY_Analog Stick HUD Widget|Analog Stick HUD Widget]]
- [[_COMMUNITY_Numba Vectorized Projection|Numba Vectorized Projection]]
- [[_COMMUNITY_Cockpit Shield Integrity Data|Cockpit Shield Integrity Data]]
- [[_COMMUNITY_Weapon Cooldown Status Data|Weapon Cooldown Status Data]]
- [[_COMMUNITY_Trigger Mapping Utilities|Trigger Mapping Utilities]]
- [[_COMMUNITY_Star Batch Submission Pipeline|Star Batch Submission Pipeline]]

## God Nodes (most connected - your core abstractions)
1. `Enemy` - 28 edges
2. `DS4Input` - 28 edges
3. `SpatialPartition` - 25 edges
4. `ObjectPool` - 24 edges
5. `ParticlePool` - 23 edges
6. `draw_cockpit_hud()` - 21 edges
7. `SpatialHash` - 20 edges
8. `main()` - 20 edges
9. `DebugViewer` - 20 edges
10. `LaserPool` - 19 edges

## Surprising Connections (you probably didn't know these)
- `Object Pooling` --rationale_for--> `ObjectPool`  [INFERRED]
  extra_docs/OPTIMIZATION_SUMMARY.md → src/object_pool.py
- `Spatial Partitioning` --rationale_for--> `SpatialPartition`  [INFERRED]
  extra_docs/OPTIMIZATION_SUMMARY.md → src/spatial_partition.py
- `Numba JIT Position Wrapping` --rationale_for--> `wrap_star_positions_batch()`  [INFERRED]
  extra_docs/STAR_OPTIMIZATION_SUMMARY.md → src/star.py
- `Batch Star Submission` --rationale_for--> `submit_batch_to_renderer()`  [INFERRED]
  extra_docs/STAR_OPTIMIZATION_SUMMARY.md → src/star.py
- `benchmark_realistic()` --calls--> `Camera`  [INFERRED]
  tests/benchmark_realistic.py → src/camera.py

## Hyperedges (group relationships)
- **Game Engine Optimization Framework** — src_object_pool_objectpool, src_spatial_partition_spatialpartition, src_star_wrap_star_positions_batch [INFERRED 0.85]

## Communities (51 total, 10 thin omitted)

### Community 0 - "3D Debug Rendering & Viewers"
Cohesion: 0.08
Nodes (29): _cross(), DebugViewer, _dot(), face_normal_and_center(), _FallbackShip, mesh_centroid(), _project(), _quat_conj() (+21 more)

### Community 1 - "3D Mathematics & Matrix Engine"
Cohesion: 0.08
Nodes (29): calculate_lead_position(), get_basis_vectors(), get_forward_vector(), get_right_from_quat(), get_right_vector(), project_to_screen(), quat_from_axis_angle(), quat_identity() (+21 more)

### Community 2 - "HUD Drawing & Instrument Renderers"
Cohesion: 0.13
Nodes (33): _cached_label(), custom_font(), _draw_active_bracket(), draw_cockpit_hud(), draw_crosshair(), _draw_dim_bracket(), draw_dodge_bg(), draw_dodge_fill() (+25 more)

### Community 3 - "Asteroid Generation & Mesh Rendering"
Cohesion: 0.08
Nodes (10): Asteroid, AsteroidField, Create smaller fragments that explode away from each other., Game, Render a secondary pass for the magnified aim window., # TODO: Refactor asteroid field creation logic, NebulaCloud, NebulaSystem (+2 more)

### Community 4 - "Core Object Pooling Infrastructure"
Cohesion: 0.08
Nodes (17): ObjectPool, Generic object pool for managing reusable entities., Initialize the object pool.                  Args:             factory: Function, Default reset does nothing - override for specific types., Acquire an object from the pool.                  Returns None if pool is exhaus, Return an object to the pool for reuse., Return all in-use objects to the pool., Get number of objects currently in use. (+9 more)

### Community 5 - "Homing Missile Weapons System"
Cohesion: 0.08
Nodes (7): basis_from_forward(), HomingMissile, PlayerMissile, Player, Lock onto the nearest living, non-stealthed enemy within field of view., Advance to the next non-stealthed enemy in FOV (wraps around)., Nullify the active target if it has been destroyed.

### Community 6 - "Enemy Ships & Visual Trails"
Cohesion: 0.13
Nodes (9): DefaultEnemyShip, EntityViewer, entity_viewer.py ---------------- Standalone entity inspection tool. Load any dr, Rotate + scale a list of (x, y) unit coords around cx, cy., Transform a single local point., Call once per frame to keep trail particles alive., Interactive viewer. Pass an entity_factory callable that returns     an object w, Map horizontal mouse drag → rotation angle. (+1 more)

### Community 7 - "Cockpit Frame UI Panel Geometry"
Cohesion: 0.16
Nodes (21): _build_static(), _c(), draw_cockpit_frame(), _hex_plate(), _inset_panel(), _l(), _p(), _poly() (+13 more)

### Community 8 - "Engine Optimization Documentation"
Cohesion: 0.11
Nodes (12): Object Pooling, Spatial Partitioning, Remove an entity from the system., Update an entity's position incrementally.         Call this every frame for mov, Query all entities that might be visible to the camera.         Uses cell-level, Main spatial partitioning manager for the game.     Manages entity lifecycle and, Register a new entity., SpatialPartition (+4 more)

### Community 9 - "Enemy Projectiles & Weapon Behaviors"
Cohesion: 0.12
Nodes (6): EnemyProjectile, HomingBolt, Mine, Check if this projectile hits the player. Returns True if collision occurred., Check if this projectile hits an asteroid. Returns True if collision occurred., SniperBeam

### Community 10 - "Spatial Hash Grid Implementation"
Cohesion: 0.12
Nodes (10): Spatial Partitioning System Efficient collision detection and entity culling usi, Efficient spatial partitioning using a hash grid.     Optimized for fast inserti, Query entities near a position., Convert world position to grid cell coordinates using fast truncation., Insert an entity into the spatial hash., Remove an entity from the spatial hash., Incrementally move an entity between cells., Query all entities within a sphere. (+2 more)

### Community 11 - "DS4 Input Controller Handler"
Cohesion: 0.11
Nodes (11): DS4Input, Clear single-frame sets. Call exactly ONCE per frame,         AFTER processing a, True every frame the button is down., All buttons currently held., Left stick (x, y) with deadzone applied, –1..1., Right stick (x, y) with deadzone applied, –1..1., Raw hat value: (dx, dy) where each component is –1, 0, or 1., Human-readable D-pad direction, or 'neutral'. (+3 more)

### Community 12 - "Particle Effects Spawning & Pools"
Cohesion: 0.12
Nodes (11): ParticlePool, Spawn a particle at the given position., Update all active particles and recycle dead ones., Batch submit active particles to the renderer with frustum culling., Legacy shim for compatibility with existing game.py loops., Specialized high-performance pool for particle effects using parallel lists., Tests for particle pool., Test spawning particles. (+3 more)

### Community 13 - "Player Ship Flight Mechanics"
Cohesion: 0.22
Nodes (6): Dogfighter, Rotate nose toward desired_heading at turn_rate, fire main thrust,         apply, True when close to target and still closing fast — signal to flip and brake., get_forward_from_quat(), Extract just the forward (Z) vector from a quaternion — avoids full basis build., MachineGunBolt

### Community 14 - "Utility Functions & Enemy Spawners"
Cohesion: 0.16
Nodes (16): _forward_spawn_pos(), Carriers are boss-scale — spawn far ahead and slightly above so     they dominat, Generic factory — maps a string type to the right spawn function., Shared geometry for all forward-arc spawns.     Returns (x, y, z) — a world posi, Snipers hang back further than normal enemies so their railgun     has room to t, Corvettes spawn at standard range but with a tighter yaw cone     so they appear, Minelayers enter from the side (large yaw offset) so they can     cut across the, Stealth Interceptors sneak in from the flanks at close-ish range     so their de (+8 more)

### Community 15 - "3D Face Transform & Screen Projection"
Cohesion: 0.12
Nodes (8): process_faces_batch_numba(), Submit a single polygon., Submit a 2D circle sprite., Submit a soft, semi-transparent nebula puff., Sort and render all submitted primitives by layer., Create a soft, radial gradient puff texture for nebulae., Submit a whole mesh for optimized rendering.         Uses Numba-optimized batch, RenderPipeline

### Community 16 - "Camera Navigation & Render Loop"
Cohesion: 0.12
Nodes (6): test_batch_projection(), Camera, Fast frustum culling using a bounding sphere.         Returns (visible, cx, cy,, Transform world point to camera space using pre-computed rotation matrix., Transform batch of world points to camera space using Numba., sphere_in_frustum_batch()

### Community 17 - "Laser Pooling & Fire Management"
Cohesion: 0.12
Nodes (9): LaserPool, Object Pooling System Efficiently manages reusable game objects to avoid frequen, Clear all active particles., Specialized pool for laser projectiles., Fire a laser from the given position with the given velocity., Update all active lasers and recycle expired ones., Get list of active lasers., Get number of active lasers. (+1 more)

### Community 18 - "Laser Projectile Reinitialization"
Cohesion: 0.14
Nodes (9): Laser, Reinitialize laser with new values (for object pooling)., Reset laser to default state (for object pooling)., Initialize a laser. Can be initialized with player orientation or with explicit, Test laser class compatibility with pooling., Test laser can be initialized with explicit parameters., Test laser can be reinitialized for pooling., Test laser reset for pooling. (+1 more)

### Community 19 - "Controller Haptics & Vibration"
Cohesion: 0.13
Nodes (7): Connect to the joystick. Returns True if successful., Trigger controller rumble. DS4 has two motors:         - low_frequency: left mot, Stop all rumble immediately., Simple pulse: both motors at same intensity.         intensity: 0.0–1.0, Sharp punch feeling: high-frequency spike (short duration).         intensity: 0, Continuous buzz: low-frequency vibration.         intensity: 0.0–1.0, Wave effect: both motors ramping up and down.         intensity: 0.0–1.0

### Community 20 - "Enemy Ship Base Navigation AI"
Cohesion: 0.18
Nodes (3): Enemy, Check if a projectile at (px, py, pz) hits this enemy using spherical collision., Triggers proximity explosion and deals radial damage to player.

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
Cohesion: 0.20
Nodes (7): Unit tests for object pooling and spatial partitioning systems. Run with: python, Tests for spatial hash grid., Test inserting and querying with spatial hash., Test clearing spatial hash., Run all tests manually (for environments without pytest)., run_tests(), TestSpatialHash

### Community 26 - "Corvette Heavy Fighter AI"
Cohesion: 0.36
Nodes (3): Corvette, SuicideDrone, CorvetteTurret

### Community 28 - "Star Rendering Optimization Docs"
Cohesion: 0.43
Nodes (5): Batch Star Submission, Numba JIT Position Wrapping, Batch wrap star positions around player.     Avoids 220 individual Python functi, submit_batch_to_renderer(), wrap_star_positions_batch()

### Community 29 - "Octree Spatial Partition Tests"
Cohesion: 0.25
Nodes (5): Tests for octree spatial partition., Test inserting and querying entities., Test removing entities., Test clearing all entities., TestOctreeNode

### Community 30 - "Bounding Box Geometry Tests"
Cohesion: 0.25
Nodes (5): Tests for bounding box utilities., Test point containment., Test box intersection., Test box subdivision into octants., TestBoundingBox

### Community 31 - "Star Rendering & Lifecycle"
Cohesion: 0.33
Nodes (3): Star, benchmark_realistic(), Benchmark actual game rendering pipeline.

### Community 32 - "HUD Controller Event Logger"
Cohesion: 0.33
Nodes (3): _btn_name(), EventLog, Feed a pygame event to the handler.         Returns True if the event was consum

### Community 33 - "Trigger Input Normalisation"
Cohesion: 0.40
Nodes (3): _normalise_trigger(), L2 normalised to 0..1., R2 normalised to 0..1.

### Community 37 - "Batch Color Numba Benchmark"
Cohesion: 0.40
Nodes (4): compute_star_colors_batch(), Batch compute final star colors with distance-based dimming.     All 220 stars p, benchmark_batch_processing(), Test the optimized batch star processing.

### Community 39 - "Numba Vectorized Projection"
Cohesion: 0.50
Nodes (3): Project batch of camera-space points to screen space using Numba., project_to_screen_batch(), Numba-optimized batch projection.     cam_verts: (N, 3) float64 array     return

## Knowledge Gaps
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Game` connect `Asteroid Generation & Mesh Rendering` to `Homing Missile Weapons System`, `Engine Optimization Documentation`, `DS4 Input Controller Handler`, `Particle Effects Spawning & Pools`, `3D Face Transform & Screen Projection`, `Camera Navigation & Render Loop`, `Laser Pooling & Fire Management`, `Laser Projectile Reinitialization`, `Scripted Encounter Timelines`, `Star Rendering & Lifecycle`?**
  _High betweenness centrality (0.328) - this node is a cross-community bridge._
- **Why does `WaveDirector` connect `Scripted Encounter Timelines` to `Stealth Interceptor Enemy AI`, `Asteroid Generation & Mesh Rendering`, `Carrier Bounding Box Collision`, `Player Ship Flight Mechanics`, `Encounter Spawn Director & AI`, `Corvette Heavy Fighter AI`, `Sniper Flank Enemy AI`?**
  _High betweenness centrality (0.226) - this node is a cross-community bridge._
- **Why does `DS4Input` connect `DS4 Input Controller Handler` to `HUD Controller Event Logger`, `Trigger Input Normalisation`, `3D Mathematics & Matrix Engine`, `Asteroid Generation & Mesh Rendering`, `Controller Haptics & Vibration`, `Controller D-Pad HUD Widget`, `Controller Button HUD Grid`?**
  _High betweenness centrality (0.207) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `Enemy` (e.g. with `MachineGunBolt` and `HomingBolt`) actually correct?**
  _`Enemy` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `DS4Input` (e.g. with `Game` and `Viewer`) actually correct?**
  _`DS4Input` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `SpatialPartition` (e.g. with `TestObjectPool` and `TestParticlePool`) actually correct?**
  _`SpatialPartition` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `ObjectPool` (e.g. with `TestObjectPool` and `TestParticlePool`) actually correct?**
  _`ObjectPool` has 12 INFERRED edges - model-reasoned connections that need verification._