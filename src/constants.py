# ──────────────────────────────────────────────
# GAME BALANCE CONSTANTS
# ──────────────────────────────────────────────

MAX_SUICIDE_DRONES = 0
MAX_DOGFIGHTERS    = 0
SPAWNS_PER_SECOND  = 1.2             # Expected number of spawns per second
SPAWN_DIST_MIN    = 7000
SPAWN_DIST_MAX    = 10000
SPAWN_HEIGHT_RANGE = 2000            # vertical spread around spawn point
SPAWN_YAW_SPREAD  = 10.55            # radians either side of yaw-forward (≈ ±31°)

PLAYER_COLLISION_RADIUS = 60        # world units — drone kills at this range
PLAYER_MAX_HP     = 100

HIT_FLASH_DURATION = 0.25          # seconds screen flashes red on hit

MAX_THRUST = 500
MAX_RETRO_THRUST = 250
DRAG = 0.01
MAX_SPEED = 2500.0
DODGE_COOLDOWN = 1.20
DODGE_IMPULSE = 2000
DODGE_THRESHOLD = 0.20

# ──────────────────────────────────────────────
# COMBAT & COLLISION CONSTANTS
# ──────────────────────────────────────────────

ENEMY_HIT_RADIUS_SQ = 6400          # squared radius for laser-enemy collision (80^2)
ENEMY_CULL_DISTANCE = -30000         # enemies behind this are culled
HOMING_TURN_RATE = 1.4              # homing projectile turn rate per second
PARTICLES_ON_HIT = 12                # particles spawned when enemy hit
PARTICLES_ON_DESTROY = 25           # particles spawned when enemy destroyed
PARTICLES_ON_PLAYER_HIT = 10        # particles spawned when player hit
COLLISION_DAMAGE = 20               # damage taken from enemy collision

# ──────────────────────────────────────────────
# CONTROLLER CONSTANTS
# ──────────────────────────────────────────────

DEADZONE_DEFAULT = 0.20             # radial deadzone for analog sticks
CONTROLLER_LOG_THRESHOLD = 0.15     # threshold for logging controller input
TRIGGER_LOG_THRESHOLD = 0.1         # threshold for logging trigger movement

# ──────────────────────────────────────────────
# UI & VISUAL CONSTANTS
# ──────────────────────────────────────────────

DODGE_FLASH_DURATION = 0.12         # seconds for dodge flash effect
HIT_FLASH_NORMALIZE = 0.12          # normalize factor for hit flash
CAMERA_CLIP_NEAR = 0.1              # near clipping plane for camera
SNIPER_CHARGE_TIME = 1.5            # seconds for sniper charge phase
SNIPER_CHARGE_JITTER = 7.0          # jitter multiplier for sniper beam
SNIPER_CHARGE_CORE_THRESHOLD = 0.8  # intensity threshold for white core
SNIPER_GLARE_MULTIPLIER = 45        # multiplier for sniper glare size
MG_COOLDOWN = 0.15                  # machine gun cooldown in seconds
WEAPON_SPREAD = 0.05                # weapon spread in radians
TRAIL_LIFE_DIVISOR = 0.1            # divisor for trail life ratio calculation
TARGETING_FOV = 100.0               # field of view for target lock in degrees

SCREEN_SHAKE_DECAY = 30.0           # shake intensity decay per second
SCREEN_SHAKE_MAX = 45.0             # maximum pixels of displacement

PLAYER_LASER_HEAT_PER_SHOT = 0.06    # heat added per dual-shot (0.0 to 1.0 scale)
PLAYER_LASER_COOL_RATE = 0.25       # heat dissipated per second
PLAYER_LASER_FIRE_SHAKE = 3.8    # screen shake intensity when firing

# ──────────────────────────────────────────────
# UI CONSTANTS
# ──────────────────────────────────────────────

HUD_GREEN = (0, 255, 140, 80)    # Main glowing lines/text
HUD_DIM = (0, 160, 90, 80)       # Dimmed elements
HUD_AMBER = (255, 180, 30, 160)  # Warnings / not ready
HUD_RED = (255, 60, 60, 160)     # Critical / close enemies

# ──────────────────────────────────────────────
# SUICIDE DRONE MECHANICS
# ──────────────────────────────────────────────

DRONE_DETONATION_RANGE = 450.0
DRONE_EXPLOSION_RADIUS = 900.0
DRONE_MAX_DAMAGE = 40.0

# ──────────────────────────────────────────────
# ASTEROID MECHANICS
# ──────────────────────────────────────────────

ASTEROID_MIN_HP = 5
ASTEROID_MAX_HP = 20
ASTEROID_DAMAGE = 35.0
ASTEROID_MIN_SCALE = 80.0
ASTEROID_MAX_SCALE = 1000.0
ASTEROID_SPAWN_RADIUS = 8500.0
ASTEROID_ROTATION_SPEED_MAX = 1.5
ASTEROID_DRIFT_SPEED_MAX = 700.0
ASTEROID_PARTICLES_ON_DESTROY = 40

# ──────────────────────────────────────────────
# AIM MODE / MAGNIFICATION
# ──────────────────────────────────────────────

AIM_MODE_THRESHOLD = 0.5            # L2 trigger threshold to activate
AIM_MAGNIFICATION_MIN = 1.25         # Minimum magnification (light trigger pull)
AIM_MAGNIFICATION_MAX = 8.0         # Maximum magnification (full trigger pull)
AIM_MAGNIFICATION = 5.0             # Default magnification for keyboard (LShift)
AIM_WINDOW_SIZE = 420               # Size of the zoom window (increased 1.5x)
AIM_WINDOW_POS = (1280 // 2 - 210, 760 // 2 - 210) # Position on screen
AIM_WINDOW_BORDER_COLOR = (0, 200, 255, 180)
AIM_WINDOW_CROSSHAIR_COLOR = (255, 50, 50, 200)

PLAYER_LASER_SPEED = 16000.0        # Projectile speed for lead calculation

# ──────────────────────────────────────────────
# DISPLAY CONSTANTS
# ──────────────────────────────────────────────

FULLSCREEN = True
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 760

