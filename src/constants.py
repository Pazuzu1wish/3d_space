# ──────────────────────────────────────────────
# GAME BALANCE CONSTANTS
# ──────────────────────────────────────────────

MAX_SUICIDE_DRONES = 0
MAX_DOGFIGHTERS    = 0
SPAWNS_PER_SECOND  = 1.2             # Expected number of spawns per second
SPAWN_DIST_MIN    = 4000
SPAWN_DIST_MAX    = 5000
SPAWN_HEIGHT_RANGE = 2000            # vertical spread around spawn point
SPAWN_YAW_SPREAD  = 3.55            # radians either side of yaw-forward (≈ ±31°)

PLAYER_COLLISION_RADIUS = 60        # world units — drone kills at this range
PLAYER_MAX_HP     = 100

HIT_FLASH_DURATION = 0.25          # seconds screen flashes red on hit

MAX_THRUST = 500
MAX_RETRO_THRUST = 250
DRAG = 0.01
MAX_SPEED = 1500.0

# ──────────────────────────────────────────────
# UI CONSTANTS
# ──────────────────────────────────────────────

HUD_GREEN = (0, 255, 140, 80)    # Main glowing lines/text
HUD_DIM = (0, 160, 90, 80)       # Dimmed elements
HUD_AMBER = (255, 180, 30, 160)  # Warnings / not ready
HUD_RED = (255, 60, 60, 160)     # Critical / close enemies
