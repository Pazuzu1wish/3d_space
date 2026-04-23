import math
import random
from .math_engine import (
    world_to_camera, project_to_screen,
    quat_rotate_vec, quat_conjugate,
)
import pygame


# ──────────────────────────────────────────────
#  BASE ENEMY
# ──────────────────────────────────────────────

class Enemy:
    """Abstract base for all enemy types."""

    def __init__(self, x, y, z):
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.hp = 1

    # Override in subclasses
    def update(self, dt, player_pos, player_orientation):
        pass

    def draw(self, surf, ppos, prot):
        pass

    # ── Shared helpers ─────────────────────────

    def _camera_z(self, player_pos, player_orientation):
        """Signed camera-space Z of this enemy (positive = in front of player)."""
        _, _, cz = world_to_camera(
            self.x, self.y, self.z,
            player_pos[0], player_pos[1], player_pos[2],
            player_orientation,
        )
        return cz

    def dist_to_player(self, player_pos):
        dx = self.x - player_pos[0]
        dy = self.y - player_pos[1]
        dz = self.z - player_pos[2]
        return math.sqrt(dx*dx + dy*dy + dz*dz)


# ──────────────────────────────────────────────
#  MOVEMENT PATTERNS  (pure functions)
#  Each returns a velocity 3-tuple (vx, vy, vz)
#  that will be ADDED to the base homing vector.
# ──────────────────────────────────────────────

def _pattern_direct(t, phase, speed):
    """No evasion — straight rush."""
    return (0.0, 0.0, 0.0)


def _pattern_weave(t, phase, speed):
    """Horizontal sine weave — harder to lead."""
    amp   = speed * 0.55
    freq  = 1.8
    val   = math.sin(t * freq + phase) * amp
    return (val, 0.0, 0.0)


def _pattern_wobble(t, phase, speed):
    """Full 3-D wobble — chaotic small movements."""
    amp  = speed * 0.40
    freq = 2.5
    vx   = math.sin(t * freq        + phase) * amp
    vy   = math.cos(t * freq * 1.13 + phase) * amp
    return (vx, vy, 0.0)


def _pattern_spiral(t, phase, speed):
    """Barrel-roll spiral around the approach vector."""
    amp  = speed * 0.65
    freq = 1.4
    vx   = math.sin(t * freq + phase) * amp
    vy   = math.cos(t * freq + phase) * amp
    return (vx, vy, 0.0)


def _pattern_zigzag(t, phase, speed):
    """Hard direction reversals — very hard to track."""
    amp   = speed * 0.80
    freq  = 1.1
    # Square-wave approximation
    sign  = 1.0 if math.sin(t * freq + phase) >= 0 else -1.0
    return (sign * amp, 0.0, 0.0)


def _pattern_corkscrew(t, phase, speed):
    """Tighter spiral with vertical component — difficult at range."""
    amp  = speed * 0.50
    freq = 2.2
    vx   = math.sin(t * freq + phase) * amp
    vy   = math.cos(t * freq * 0.9 + phase) * amp * 0.6
    return (vx, vy, 0.0)


PATTERNS = [
    _pattern_direct,
    _pattern_weave,
    _pattern_wobble,
    _pattern_spiral,
    _pattern_zigzag,
    _pattern_corkscrew,
]

PATTERN_NAMES = [
    "direct", "weave", "wobble", "spiral", "zigzag", "corkscrew",
]


# ──────────────────────────────────────────────
#  SUICIDE DRONE
# ──────────────────────────────────────────────

class SuicideDrone(Enemy):
    """
    Aggressive kamikaze that homes on the player.

    Behaviour:
      • Picks a random movement pattern at spawn
      • Flies toward the player at constant speed
      • If it gets behind the player (camera-Z < BEHIND_THRESHOLD)
        it turns around aggressively to re-engage
      • On reaching COLLISION_RADIUS it deals damage and dies
    """

    SPEED             = 520          # world-units / second toward player
    COLLISION_RADIUS  = 90           # damage + kill distance
    BEHIND_THRESHOLD  = -400         # cz below this → drone is "behind" player
    TURN_RATE         = 3.5          # how fast it turns when behind (rad/s blend)

    def __init__(self, x, y, z):
        super().__init__(x, y, z)
        self.hp = 3

        # Velocity accumulator
        self.vx = self.vy = self.vz = 0.0

        # Movement pattern
        self.pattern_fn   = random.choice(PATTERNS)
        self.pattern_phase = random.uniform(0, math.tau)  # random starting phase
        self.t = 0.0                          # local time counter

        # Geometry (same triangular "fighter" shape as original)
        self.verts = [
            ( 0,   0,  40),   # 0 Nose
            (-20,  0, -20),   # 1 Left Wing
            ( 20,  0, -20),   # 2 Right Wing
            (  0, -15,-20),   # 3 Top Fin
            (  0,  10,-15),   # 4 Belly
        ]
        self.edges = [
            (0,1),(0,2),(0,3),(0,4),
            (1,2),(1,3),(2,3),(1,4),(2,4),
        ]

        # Visual flicker on low HP
        self._flicker = 0.0

    # ── Update ─────────────────────────────────

    def update(self, dt, player_pos, player_orientation):
        self.t += dt

        px, py, pz = player_pos
        dx = px - self.x
        dy = py - self.y
        dz = pz - self.z
        dist = math.sqrt(dx*dx + dy*dy + dz*dz) or 1.0

        # Normalised direction to player
        nx, ny, nz = dx/dist, dy/dist, dz/dist

        cz = self._camera_z(player_pos, player_orientation)

        if cz < self.BEHIND_THRESHOLD:
            # Drone slipped behind the player — pull a hard turn
            # Boost the homing component and suppress evasion while turning
            home_speed = self.SPEED * 1.6
            evade_x, evade_y, evade_z = 0.0, 0.0, 0.0
        else:
            home_speed = self.SPEED
            # Evasion manoeuvre in LOCAL space:
            # the pattern vector is computed in drone-centric space then
            # rotated so it's perpendicular to the approach axis.
            evade_x, evade_y, evade_z = self.pattern_fn(
                self.t, self.pattern_phase, self.SPEED
            )
            # Build a simple frame around the approach axis so evasion
            # always looks like side-stepping relative to the drone's path
            # (avoids evasion accidentally pointing toward player).
            # right = cross(approach, world_up) — fallback to world_x if parallel
            world_up = (0.0, 1.0, 0.0)
            right_x = ny * world_up[2] - nz * world_up[1]
            right_y = nz * world_up[0] - nx * world_up[2]
            right_z = nx * world_up[1] - ny * world_up[0]
            r_len = math.sqrt(right_x**2 + right_y**2 + right_z**2) or 1.0
            right_x /= r_len; right_y /= r_len; right_z /= r_len

            up_x = right_y * nz - right_z * ny
            up_y = right_z * nx - right_x * nz
            up_z = right_x * ny - right_y * nx

            # Remap evade (x=right, y=up, z=forward≈0)
            evade_x = evade_x * right_x + evade_y * up_x
            evade_y = evade_x * right_y + evade_y * up_y  # note: intentional overwrite order fixed below
            # (redo cleanly)
            ex_raw, ey_raw, _ = self.pattern_fn(self.t, self.pattern_phase, self.SPEED)
            evade_x = ex_raw * right_x + ey_raw * up_x
            evade_y = ex_raw * right_y + ey_raw * up_y
            evade_z = ex_raw * right_z + ey_raw * up_z

        # Composite velocity
        target_vx = nx * home_speed + evade_x
        target_vy = ny * home_speed + evade_y
        target_vz = nz * home_speed + evade_z

        # Smooth blend (feels more organic than instant snap)
        blend = min(1.0, dt * 6.0)
        self.vx += (target_vx - self.vx) * blend
        self.vy += (target_vy - self.vy) * blend
        self.vz += (target_vz - self.vz) * blend

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt

        # Flicker counter for damage visuals
        if self._flicker > 0:
            self._flicker = max(0.0, self._flicker - dt * 8.0)

    def on_hit(self):
        """Call when a laser connects."""
        self.hp -= 1
        self._flicker = 1.0

    # ── Draw ───────────────────────────────────

    def draw(self, surf, ppos, prot):
        projected = {}
        for i, (vx, vy, vz) in enumerate(self.verts):
            cx, cy, cz = world_to_camera(
                self.x + vx, self.y + vy, self.z + vz,
                *ppos, prot,
            )
            proj = project_to_screen(cx, cy, cz)
            if proj:
                projected[i] = proj

        if len(projected) < len(self.verts):
            return

        # Colour shifts with HP and flicker
        if self._flicker > 0.5:
            color = (255, 255, 255)                      # white flash on hit
        elif self.hp <= 1:
            color = (255, int(200 * (1 - self._flicker)), 80)  # amber / dying
        else:
            color = (255, 80, 80)                        # healthy red

        for p1, p2 in self.edges:
            if p1 in projected and p2 in projected:
                sx1, sy1, _ = projected[p1]
                sx2, sy2, _ = projected[p2]
                pygame.draw.line(surf, color, (sx1, sy1), (sx2, sy2), 2)