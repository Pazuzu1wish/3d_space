# Space Game — Design Bible v0.1

> **North star:** An indie Elite Dangerous. Start with a tight combat sandbox. Build outward. Never refactor twice.

---

## 0. Philosophy

The game loop is a conductor, not a performer. At a glance it should tell you *who has the floor* — not *what they're doing with it*. Every system is a black box that owns its own state, exposes a clean interface, and gets out of the way when it's not its turn.

Three rules that govern every architectural decision:

1. **States own their loop.** Each `GameState` subclass runs its own update/draw/input cycle. The top-level loop hands control to the active state and does nothing else.
2. **Systems don't know about each other.** They talk through an event bus or through the `GameContext` object — never by importing each other directly.
3. **Data lives in one place.** `SaveData` is the single source of truth for anything that persists. Systems read from it; they never cache their own copy of persistent state.

---

## 1. Project structure

```
space_game/
├── main.py                  # entry point — init pygame, create GameContext, run loop
├── core/
│   ├── game_loop.py         # StateManager, the main loop, dt
│   ├── game_context.py      # shared services: event_bus, save_data, asset_manager, settings
│   ├── state.py             # GameState base class
│   ├── event_bus.py         # lightweight pub/sub
│   └── save_data.py         # persistence model, load/save
├── states/
│   ├── main_menu.py         # MainMenuState
│   ├── combat.py            # CombatState  ← what you have now
│   ├── galaxy_map.py        # GalaxyMapState  (stub)
│   ├── station.py           # StationState    (stub)
│   ├── pause.py             # PauseState      (overlay)
│   └── game_over.py         # GameOverState
├── systems/
│   ├── physics.py           # PhysicsSystem — inertia, velocity integration
│   ├── input_handler.py     # DS4Input abstraction layer
│   ├── combat_system.py     # weapons, projectiles, collision, damage
│   ├── enemy_ai.py          # EnemyAI, WaveDirector, behavior state machines
│   ├── hud.py               # HUDSystem — holosphere, targeting computer, pip calc
│   ├── camera.py            # world_to_camera, project, screenshake
│   └── audio.py             # AudioSystem (stub)
├── entities/
│   ├── entity.py            # Entity base — id, pos, vel, components dict
│   ├── player.py            # PlayerShip
│   ├── enemy.py             # EnemyShip base + subtypes
│   ├── projectile.py        # Projectile
│   └── station.py           # Station (stub)
├── data/
│   ├── ships.json           # ship stats, hardpoints, mesh paths
│   ├── weapons.json         # weapon definitions
│   ├── enemies.json         # enemy type definitions
│   └── sectors.json         # sector/system definitions (stub)
├── assets/
│   ├── meshes/              # .obj files (mesh editor output)
│   ├── sounds/
│   └── fonts/
└── tools/
    └── mesh_editor.py       # standalone; not part of the game runtime
```

`tools/` is quarantined. The mesh editor does not import from `core/` or `systems/`. It outputs `.obj` files that the game loads at runtime from `assets/meshes/`.

---

## 2. The game loop

This is the entire main loop. It should stay this thin forever.

```python
# core/game_loop.py

class StateManager:
    def __init__(self, context):
        self.context = context
        self._stack = []          # stack allows overlay states (pause, menus)

    @property
    def current(self):
        return self._stack[-1] if self._stack else None

    def push(self, state: GameState):
        if self.current:
            self.current.on_pause()
        self._stack.append(state)
        state.on_enter(self.context)

    def pop(self):
        if self.current:
            self.current.on_exit()
            self._stack.pop()
        if self.current:
            self.current.on_resume()

    def swap(self, state: GameState):
        if self.current:
            self.current.on_exit()
            self._stack[-1] = state
        else:
            self._stack.append(state)
        state.on_enter(self.context)


def run(context, initial_state):
    clock = pygame.time.Clock()
    manager = StateManager(context)
    manager.push(initial_state)

    while manager.current:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            manager.current.handle_event(event)

        manager.current.update(dt, manager)
        manager.current.draw(context.screen)
        pygame.display.flip()
```

That's it. No combat logic. No HUD rendering. No AI ticks. The loop doesn't know any of that exists.

---

## 3. GameState base class

Every state — menu, combat, galaxy map, station, pause — is a `GameState` subclass.

```python
# core/state.py

class GameState:
    def on_enter(self, context):
        """Called once when this state becomes active."""
        pass

    def on_exit(self):
        """Called once when this state is popped or swapped out."""
        pass

    def on_pause(self):
        """Called when another state is pushed on top (e.g. pause menu)."""
        pass

    def on_resume(self):
        """Called when the state on top is popped and this one is active again."""
        pass

    def handle_event(self, event):
        pass

    def update(self, dt, manager: StateManager):
        """
        Do work. Call manager.push(), manager.pop(), or manager.swap()
        to transition. Never call another state's update() directly.
        """
        pass

    def draw(self, screen):
        pass
```

Transitions happen inside `update()` via the `manager`. A state never reaches into another state.

---

## 4. GameContext — shared services

`GameContext` is passed into every state via `on_enter`. It's the only cross-cutting object. Systems that need to communicate use the event bus it provides.

```python
# core/game_context.py

class GameContext:
    def __init__(self):
        self.screen       = None          # pygame surface, set at init
        self.settings     = Settings()    # resolution, volume, keybinds
        self.save_data    = SaveData()    # persistent player data
        self.asset_manager = AssetManager()
        self.event_bus    = EventBus()
```

Nothing else lives here. If you're tempted to put a system reference in `GameContext`, ask whether you need the event bus instead.

---

## 5. System architecture

Systems are stateless-ish service objects. They do not hold game entity references beyond their current execution frame unless they own that data (e.g. `PhysicsSystem` owns the velocity integration; it doesn't store a reference to the player).

Systems are instantiated by their owning state in `on_enter` and released in `on_exit`.

```python
# states/combat.py

class CombatState(GameState):
    def on_enter(self, context):
        self.context = context
        self.input    = DS4Input()
        self.physics  = PhysicsSystem()
        self.weapons  = CombatSystem()
        self.ai       = EnemyAISystem()
        self.hud      = HUDSystem(context.screen)
        self.camera   = CameraSystem()
        self.wave_dir = WaveDirector()
        self.entities = EntityList()
        self.player   = PlayerShip(...)
        self.entities.add(self.player)
        self.wave_dir.start(self.entities)

    def update(self, dt, manager):
        raw = self.input.poll()
        self.physics.update(self.entities, dt)
        self.weapons.update(self.entities, raw, dt)
        self.ai.update(self.entities, self.player, dt)
        self.wave_dir.update(self.entities, dt)

        if self._player_dead():
            manager.swap(GameOverState(self._build_run_result()))
        if raw.just_pressed('pause'):
            manager.push(PauseState())

    def draw(self, screen):
        self.camera.begin_frame(self.player)
        for entity in self.entities:
            entity.draw(screen, self.camera)
        self.hud.draw(screen, self.player, self.entities)
```

The update order matters and is explicit here. Physics first, then player actions (weapons), then AI reactions, then wave management. HUD draws last — always on top.

---

## 6. Event bus

Systems that need to react to each other's events — without importing each other — use the bus.

```python
# core/event_bus.py

class EventBus:
    def __init__(self):
        self._listeners = defaultdict(list)

    def subscribe(self, event_type, callback):
        self._listeners[event_type].append(callback)

    def emit(self, event_type, **data):
        for cb in self._listeners[event_type]:
            cb(**data)
```

Example usage:

```python
# CombatSystem emits:
context.event_bus.emit('entity_destroyed', entity=enemy, killer=player)

# HUDSystem listens:
context.event_bus.subscribe('entity_destroyed', self.on_kill)
# AudioSystem listens:
context.event_bus.subscribe('entity_destroyed', self.play_explosion)
# WaveDirector listens:
context.event_bus.subscribe('entity_destroyed', self.on_enemy_down)
```

No system imports any other system. The bus is the only wire.

---

## 7. Entity model

Entities are plain data containers. Logic lives in systems. Don't put physics in `PlayerShip.update()` — put it in `PhysicsSystem.update()`.

```python
# entities/entity.py

class Entity:
    _id_counter = 0

    def __init__(self, pos, vel=(0,0)):
        self.id       = Entity._id_counter; Entity._id_counter += 1
        self.pos      = pygame.Vector2(pos)
        self.vel      = pygame.Vector2(vel)
        self.facing   = pygame.Vector2(0, -1)   # unit vector
        self.alive    = True
        self.tags     = set()           # e.g. {'enemy', 'collidable', 'targetable'}
        self.mesh     = None            # loaded OBJ mesh
        self.radius   = 20.0            # for broad-phase collision
```

Tags let systems query entity sets without isinstance checks:

```python
enemies = [e for e in entities if 'enemy' in e.tags]
```

Subclasses (`PlayerShip`, `EnemyShip`, `Projectile`) add only the data fields that are specific to them. No methods that duplicate system logic.

---

## 8. Camera and projection

The canonical two-step you've already established — keep it:

```python
# systems/camera.py

class CameraSystem:
    def world_to_camera(self, world_pos):
        return world_pos - self.origin      # origin tracks player

    def project(self, cam_pos):
        # returns screen-space (x, y)
        return cam_pos + self.screen_center

    def transform(self, world_pos):
        return self.project(self.world_to_camera(world_pos))
```

Every system that needs to draw in world space calls `camera.transform(world_pos)`. The HUD uses screen-space directly — it never calls `transform`. The HUD and world-space renderers never share coordinate logic.

---

## 9. Persistence model

`SaveData` is a dataclass. It gets serialized to JSON. It's the only thing that touches the disk.

```python
# core/save_data.py

@dataclass
class SaveData:
    # identity
    commander_name: str = "CMDR"

    # progression
    credits: int = 1000
    reputation: dict = field(default_factory=dict)   # faction -> float
    unlocked_ships: list = field(default_factory=lambda: ['starter'])
    unlocked_weapons: list = field(default_factory=list)
    visited_systems: set = field(default_factory=set)

    # score mode
    high_scores: list = field(default_factory=list)  # list of RunResult dicts

    # active ship loadout
    ship_id: str = 'starter'
    hardpoints: dict = field(default_factory=dict)   # slot -> weapon_id

    def save(self, path='save.json'):
        with open(path, 'w') as f:
            json.dump(asdict(self), f, default=list)

    @classmethod
    def load(cls, path='save.json'):
        try:
            with open(path) as f:
                return cls(**json.load(f))
        except FileNotFoundError:
            return cls()
```

When the game adds trading, faction standings, discovered jump routes — they're new fields on `SaveData`. No new persistence layer, no second save file.

---

## 10. Game states — full map

### Phase 1 — Combat sandbox (now)

| State | Responsibility |
|---|---|
| `MainMenuState` | new game / load / quit; score display |
| `CombatState` | the current sandbox; all in-flight systems |
| `PauseState` | overlay; no update tick passes through |
| `GameOverState` | score summary; persist `RunResult` to `SaveData.high_scores` |

### Phase 2 — Galaxy layer

| State | Responsibility |
|---|---|
| `GalaxyMapState` | sector selection; travel; faction territory overlay |
| `HyperspaceState` | transition animation between systems |
| `SystemViewState` | local map within a system; nav to station or combat zone |

### Phase 3 — Station layer

| State | Responsibility |
|---|---|
| `StationState` | hub shell; routes to sub-states below |
| `ShipyardState` | buy/sell ships; view loadouts |
| `OutfittingState` | hardpoint management; weapon installation |
| `MarketState` | commodity trading (stub) |
| `MissionBoardState` | mission selection (stub) |

### Overlay states (any phase)

| State | Responsibility |
|---|---|
| `PauseState` | push on top of any state; pop to resume |
| `DialogueState` | NPC conversation (stub) |

The stack model handles overlays cleanly. `PauseState` pushes on top of `CombatState`. When popped, `CombatState.on_resume()` fires and the clock resumes. No special-case pause flags anywhere in the combat code.

---

## 11. Combat system — what you have, properly bounded

`CombatState` owns these systems. None of them exist outside `CombatState`.

```
CombatState
├── PhysicsSystem        — velocity integration, drag, collision broad phase
├── DS4Input             — raw input → named action map
├── CombatSystem         — weapon fire, projectile lifecycle, damage, hit detection
├── EnemyAISystem        — per-enemy FSMs, target selection
├── WaveDirector         — wave scripting, spawn budget, escalation
├── HUDSystem            — holosphere radar, targeting computer, pip lead calc
└── CameraSystem         — world_to_camera → project, screenshake
```

The `HUDSystem` composite — holosphere, targeting, pip calculator — stays as one system unless it gets unwieldy. Split at the seam if drawing and data start fighting for the same update slot.

---

## 12. Enemy roster

Each enemy type is a data definition in `enemies.json` plus a behavior class in `enemy_ai.py`. Adding a new enemy type means: new JSON entry + new behavior class. Nothing else changes.

| Type | Behavior summary | Phase |
|---|---|---|
| `Sniper` | Instant raycast hit, long range, retreats on approach | 1 |
| `Dogfighter` | Orbit randomization, break-off states, knife fights | 1 |
| `StealthInterceptor` | 3-state FSM: stalk / burst / disengage | 1 |
| `Minelayer` | Deploy fields, area denial, avoids own mines | 1 |
| `Corvette` | Sub-systems, multi-hit hull, escort logic | 1 |
| `Carrier` | Spawns fighters, prioritize disabling over killing | 2 |
| `Bounty Hunter` | Tracks player across sessions, persistent grudge | 2 |
| `Patrol` | System law enforcement; responds to faction rep | 3 |
| `Trader (hostile)` | Piracy, flees when losing | 3 |

`WaveDirector` composes these types into encounters. It doesn't know their internals — it just spawns from the roster and passes them to `EnemyAISystem`.

---

## 13. Weapon system

Weapons are data, not classes. A `Projectile` is an entity. `CombatSystem` handles all weapon behavior.

```json
// data/weapons.json (excerpt)
{
  "pulse_laser": {
    "id": "pulse_laser",
    "projectile_speed": 800,
    "damage": 12,
    "fire_rate": 0.15,
    "heat_per_shot": 8,
    "hardpoint_size": "small",
    "projectile_mesh": "bolt_small"
  },
  "railgun": {
    "id": "railgun",
    "hitscan": true,
    "damage": 120,
    "fire_rate": 3.0,
    "heat_per_shot": 60,
    "hardpoint_size": "large",
    "charge_time": 1.5
  }
}
```

`CombatSystem` reads the definition and handles projectile vs hitscan branching internally. Callers just say `combat_system.fire(entity, 'railgun')`.

---

## 14. Refactor roadmap

Work in this order. Each step is a clean checkpoint that leaves the game functional.

### Step 1 — Extract the state machine (do first)
Create `core/state.py`, `core/game_loop.py`. Wrap what you have in a `CombatState`. The game runs exactly as before, but now the loop is clean and every future state has a home.

### Step 2 — Isolate input
Move DS4 logic to `systems/input_handler.py`. `CombatState` calls `self.input.poll()` and gets back a named action dict. Nothing else imports DS4 symbols directly.

### Step 3 — Isolate the camera
Move `world_to_camera` + `project` into `CameraSystem`. Audit every draw call — anything mixing coordinate spaces gets fixed now. The HUD gets its own coordinate path.

### Step 4 — Extract PhysicsSystem
Pull velocity integration, drag, and collision broadphase out of whatever owns them now. `CombatState.update()` calls `self.physics.update(entities, dt)` as a single line.

### Step 5 — Extract CombatSystem
Weapons, projectiles, hit detection, damage. One call in the update loop. Emits `entity_destroyed` events.

### Step 6 — Extract HUDSystem
The holosphere, targeting computer, and pip calculator become one system with one `draw()` call. They read from the entity list and player state — they don't hold references.

### Step 7 — Event bus
Wire up `EventBus`. Port any direct cross-system calls to events. Test that `WaveDirector` responds to `entity_destroyed` correctly.

### Step 8 — SaveData + scores
Implement `SaveData`. `GameOverState` persists the run result. `MainMenuState` reads and displays high scores.

### Step 9 — Asset manager + data files
Move ship/weapon/enemy stats out of constructors and into JSON. `AssetManager` loads meshes by name. Constructors stop hardcoding values.

### Step 10 — Stub remaining states
`GalaxyMapState`, `StationState` — just enough to push/pop from the menu. They can be empty rooms for now. The architecture is done. Everything after this is content.

---

## 15. Adding a new system (the pattern going forward)

When you add trading, exploration, faction reputation, or anything else:

1. New fields on `SaveData` if it needs persistence. Nothing else.
2. New `GameState` subclass in `states/`. It owns its systems.
3. New systems in `systems/` if needed. They talk to each other through `EventBus`.
4. Wire the state into the `StateManager` stack from wherever makes sense.
5. Update `entities/entity.py` only if new entity types or tags are needed.

You don't touch the game loop. You don't touch other states. You don't touch existing systems unless their interface actually needs to change — and if it does, the constructor signature and the one call site in its owning state are the only places that change.

---

## 16. Conventions

- `dt` is always in seconds (float). Never frames.
- All positions are `pygame.Vector2`. Never bare tuples in physics or camera math.
- World coordinates are unbounded. Screen coordinates are 0..width, 0..height. Never mix them.
- JSON data files are read-only at runtime. Game code never writes to them.
- `entity.alive = False` marks for removal. Systems call `entities.purge_dead()` at the end of the update tick, not mid-loop.
- State transitions happen at the end of `update()`, never inside `draw()`.
- No global state. No module-level singletons. Everything flows through `GameContext`.

---

*v0.1 — combat sandbox scope. Expand sections 10, 12, 13 as phases are built out.*