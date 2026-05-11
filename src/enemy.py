import math
import random
import pygame

from src.math_engine import (
    world_to_camera,
    project_to_screen,
    basis_from_forward,
    get_forward_from_quat,
)
from src.constants import (
    MG_COOLDOWN, WEAPON_SPREAD, TRAIL_LIFE_DIVISOR,
    DRONE_DETONATION_RANGE, DRONE_EXPLOSION_RADIUS, DRONE_MAX_DAMAGE
)
from src.projectile import (
    MachineGunBolt, HomingBolt, SniperBeam,
    CorvetteTurret, Mine, StealthShotgun
)


# ──────────────────────────────────────────────
#  BASE ENEMY
# ──────────────────────────────────────────────

class Enemy:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.hp = 1

        self.vx = self.vy = self.vz = 0.0

        self.forward = (0, 0, 1)
        self.right = (1, 0, 0)
        self.up = (0, 1, 0)

        # --- ADD THIS: Default hit radius for small enemies ---
        self.hit_radius = 50.0

        # Enhanced visual properties
        self.base_color = (255, 255, 255)
        self.engine_trail = []

        # Engine customization (override in subclasses)
        self.engine_offsets = [(0, 0, -35)]  # Local (x, y, z) offsets for thrusters
        self.engine_color = (200, 200, 255)
        self.engine_size = 4.0
        self.trail_life = 0.5
        self.engine_pulse_rate = 8.0
        self.engine_time = random.uniform(0, 100)
        self._last_dist = 0.0
        self.trail_drift = 50.0

        # ── Newtonian physics (override per subclass) ──────────────
        self.max_speed      = 1500.0   # terminal velocity cap (u/s)
        self.thrust         = 5000.0   # main engine force (u/s²)
        self.lateral_thrust = 0.35     # fraction of thrust for lateral/retro burns
        self.turn_rate      = 3.0      # max heading rotation (rad/s)
        self.drag           = 0.3      # linear drag coefficient

    def get_mesh(self):
        return self.verts, self.faces

    def _camera_z(self, player_pos, player_orientation):
        px, py, pz = player_pos
        _, _, cz = world_to_camera(
            self.x, self.y, self.z,
            px, py, pz,
            player_orientation
        )
        return cz

    def _apply_banking(self, target_v, dt):
        ax = target_v[0] - self.vx
        ay = target_v[1] - self.vy
        az = target_v[2] - self.vz

        roll_signal = (
                ax * self.right[0] +
                ay * self.right[1] +
                az * self.right[2]
        )

        roll = max(-1.5, min(1.5, roll_signal * 0.002))

        ux, uy, uz = self.up
        rx, ry, rz = self.right

        ux += rx * roll
        uy += ry * roll
        uz += rz * roll

        ulen = math.sqrt(ux * ux + uy * uy + uz * uz) or 1.0
        ux, uy, uz = ux / ulen, uy / ulen, uz / ulen

        fx, fy, fz = self.forward
        rx = fy * uz - fz * uy
        ry = fz * ux - fx * uz
        rz = fx * uy - fy * ux

        self.up = (ux, uy, uz)
        self.right = (rx, ry, rz)

    # ── NEWTONIAN PHYSICS ──────────────────────────────────────────

    def _apply_newtonian(self, desired_heading, dt, lateral_force=None):
        """Rotate nose toward desired_heading at turn_rate, fire main thrust,
        apply optional world-space lateral_force, drag, speed cap, integrate."""
        hx, hy, hz = desired_heading
        fx, fy, fz = self.forward

        # 1. Rotate forward toward desired heading (limited by turn_rate)
        dot = max(-1.0, min(1.0, hx*fx + hy*fy + hz*fz))
        angle = math.acos(dot)
        max_turn = self.turn_rate * dt
        if angle > 1e-4:
            t = min(1.0, max_turn / angle)
            nx = fx + (hx - fx) * t
            ny = fy + (hy - fy) * t
            nz = fz + (hz - fz) * t
            n = math.sqrt(nx*nx + ny*ny + nz*nz) or 1.0
            fx, fy, fz = nx/n, ny/n, nz/n
        self.forward = (fx, fy, fz)

        # 2. Rebuild right / up from new forward
        temp_up = (0, 1, 0) if abs(fy) < 0.99 else (1, 0, 0)
        rx = fy * temp_up[2] - fz * temp_up[1]
        ry = fz * temp_up[0] - fx * temp_up[2]
        rz = fx * temp_up[1] - fy * temp_up[0]
        rlen = math.sqrt(rx*rx + ry*ry + rz*rz) or 1.0
        self.right = (rx/rlen, ry/rlen, rz/rlen)
        self.up = (
            self.right[1]*fz - self.right[2]*fy,
            self.right[2]*fx - self.right[0]*fz,
            self.right[0]*fy - self.right[1]*fx,
        )

        # 3. Main thrust along current (rotated) forward
        accel = self.thrust * dt
        self.vx += fx * accel
        self.vy += fy * accel
        self.vz += fz * accel

        # 4. Optional world-space lateral force (e.g. pattern impulses, circling)
        if lateral_force is not None:
            self.vx += lateral_force[0] * dt
            self.vy += lateral_force[1] * dt
            self.vz += lateral_force[2] * dt

        # 5. Drag
        d = max(0.0, 1.0 - self.drag * dt)
        self.vx *= d
        self.vy *= d
        self.vz *= d

        # 6. Speed cap
        spd_sq = self.vx**2 + self.vy**2 + self.vz**2
        if spd_sq > self.max_speed**2:
            s = self.max_speed / math.sqrt(spd_sq)
            self.vx *= s
            self.vy *= s
            self.vz *= s

        # 7. Integrate position
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt

    def _approaching_too_fast(self, target_pos, brake_threshold=600.0):
        """True when close to target and still closing fast — signal to flip and brake."""
        dx = target_pos[0] - self.x
        dy = target_pos[1] - self.y
        dz = target_pos[2] - self.z
        dist = math.sqrt(dx*dx + dy*dy + dz*dz) or 1.0
        approach_rate = (self.vx*dx + self.vy*dy + self.vz*dz) / dist
        return dist < brake_threshold and approach_rate > 60.0

    def _update_orientation(self):
        spd = math.sqrt(self.vx ** 2 + self.vy ** 2 + self.vz ** 2)
        if spd > 1e-3:
            self.forward, self.right, self.up = basis_from_forward(
                (self.vx, self.vy, self.vz)
            )

    # Max trail particles per engine hardpoint
    _TRAIL_CAP_PER_ENGINE = 20

    def _spawn_engine_trail(self):
        # Cull particles if too far
        if self._last_dist > 15000:
            return

        # Cap trail length for headroom
        max_trail = self._TRAIL_CAP_PER_ENGINE * len(self.engine_offsets)
        if len(self.engine_trail) >= max_trail:
            return

        # Spawn a trail particle for every engine hardpoint
        for ox, oy, oz in self.engine_offsets:
            ex = self.x + self.right[0] * ox + self.up[0] * oy + self.forward[0] * oz
            ey = self.y + self.right[1] * ox + self.up[1] * oy + self.forward[1] * oz
            ez = self.z + self.right[2] * ox + self.up[2] * oy + self.forward[2] * oz

            # Add slight random drift velocity
            dvx = (random.random() - 0.5) * self.trail_drift
            dvy = (random.random() - 0.5) * self.trail_drift
            dvz = (random.random() - 0.5) * self.trail_drift

            self.engine_trail.append([ex, ey, ez, dvx, dvy, dvz, self.trail_life, self.engine_color, self.engine_size])

    def _update_engine_trail(self, dt):
        for p in self.engine_trail:
            p[0] += p[3] * dt # drift x
            p[1] += p[4] * dt # drift y
            p[2] += p[5] * dt # drift z
            p[6] -= dt        # life
        self.engine_trail = [p for p in self.engine_trail if p[6] > 0]

    def _submit_engine_trail(self, renderer):
        for x, y, z, vx, vy, vz, life, color, base_size in self.engine_trail:
            ratio = max(0.0, life / (self.trail_life or TRAIL_LIFE_DIVISOR))
            # Fade color out as it dies
            r = min(255, max(0, int(color[0] * ratio)))
            g = min(255, max(0, int(color[1] * ratio)))
            b = min(255, max(0, int(color[2] * ratio)))

            renderer.submit_sprite(x, y, z, (r, g, b), base_size * 4 * ratio, layer='alpha')

    def _submit_engine_glow(self, renderer):
        pulse = (math.sin(self.engine_time * self.engine_pulse_rate) + 1.0) * 0.5
        
        for ox, oy, oz in self.engine_offsets:
            ex = self.x + self.right[0] * ox + self.up[0] * oy + self.forward[0] * oz
            ey = self.y + self.right[1] * ox + self.up[1] * oy + self.forward[1] * oz
            ez = self.z + self.right[2] * ox + self.up[2] * oy + self.forward[2] * oz

            if self._last_dist > 5000:
                # Beacon mode (far away) — single sprite instead of 3
                renderer.submit_sprite(ex, ey, ez, self.engine_color, self.engine_size * 4, is_glow=True, layer='alpha')
            else:
                # Multi-layer bloom (close up)
                core_size = self.engine_size * (1.0 + 0.5 * pulse)
                mid_size = self.engine_size * 2.5 * (1.0 + 0.3 * pulse)
                outer_size = self.engine_size * 5.0 * (1.0 + 0.1 * pulse)

                # Outer soft halo
                r, g, b = self.engine_color
                renderer.submit_sprite(ex, ey, ez, (int(r*0.4), int(g*0.4), int(b*0.4)), outer_size, is_glow=True, layer='alpha')
                # Mid colored layer
                renderer.submit_sprite(ex, ey, ez, self.engine_color, mid_size, is_glow=True, layer='alpha')
                # Bright white core
                renderer.submit_sprite(ex, ey, ez, (255, 255, 255), core_size, is_glow=True, layer='alpha')

    def dist_to_player(self, player_pos):
        dx = self.x - player_pos[0]
        dy = self.y - player_pos[1]
        dz = self.z - player_pos[2]
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    # --- ADD THIS: Default spherical hit detection ---
    def is_hit(self, px, py, pz):
        """Check if a projectile at (px, py, pz) hits this enemy using spherical collision."""
        dx, dy, dz = self.x - px, self.y - py, self.z - pz
        return (dx * dx + dy * dy + dz * dz) < (self.hit_radius ** 2)

    def submit_to_renderer(self, renderer):
        self._submit_engine_trail(renderer)
        self._submit_engine_glow(renderer)
        renderer.submit_mesh((self.x, self.y, self.z), self.right, self.up, self.forward, self.verts, self.faces, radius=self.hit_radius * 1.5)


# ──────────────────────────────────────────────
#  MOVEMENT PATTERNS
# ──────────────────────────────────────────────

def _pattern_direct(t, phase, speed):
    return (0.0, 0.0, 0.0)


def _pattern_weave(t, phase, speed):
    amp = speed * 0.55
    return (math.sin(t * 1.8 + phase) * amp, 0.0, 0.0)


def _pattern_wobble(t, phase, speed):
    amp = speed * 0.4
    return (
        math.sin(t * 2.5 + phase) * amp,
        math.cos(t * 2.8 + phase) * amp,
        0.0,
    )


def _pattern_spiral(t, phase, speed):
    amp = speed * 0.65
    return (
        math.sin(t * 1.4 + phase) * amp,
        math.cos(t * 1.4 + phase) * amp,
        0.0,
    )


def _pattern_zigzag(t, phase, speed):
    amp = speed * 0.8
    sign = 1.0 if math.sin(t * 1.1 + phase) >= 0 else -1.0
    return (sign * amp, 0.0, 0.0)


def _pattern_corkscrew(t, phase, speed):
    amp = speed * 0.5
    return (
        math.sin(t * 2.2 + phase) * amp,
        math.cos(t * 2.0 + phase) * amp * 0.6,
        0.0,
    )


PATTERNS = [
    _pattern_direct,
    _pattern_weave,
    _pattern_wobble,
    _pattern_spiral,
    _pattern_zigzag,
    _pattern_corkscrew,
]

PATTERN_MAP = {
    'direct': _pattern_direct,
    'weave': _pattern_weave,
    'wobble': _pattern_wobble,
    'spiral': _pattern_spiral,
    'zigzag': _pattern_zigzag,
    'corkscrew': _pattern_corkscrew,
}


# ──────────────────────────────────────────────
#  SUICIDE DRONE
# ──────────────────────────────────────────────

class SuicideDrone(Enemy):
    SPEED = 2500

    def __init__(self, x, y, z):
        super().__init__(x, y, z)
        self.hp = 1
        self.max_hp = 1
        self.base_color = (255, 30, 30)

        # Single bright red thruster
        self.engine_offsets = [(0, 0, -20)]
        self.engine_color = (255, 120, 80)
        self.engine_size = 5.0
        self.engine_pulse_rate = 15.0
        self.trail_life = 0.4
        self.trail_drift = 120.0

        self.t = 0
        self.pattern = _pattern_weave
        self.pattern_phase = random.uniform(0, math.pi * 2)
        self._pattern_cache = None
        self._pattern_check_timer = 0.0
        self._flicker = 0

        # ── Newtonian physics ──
        self.max_speed      = 2600.0
        self.thrust         = 9000.0
        self.lateral_thrust = 0.5
        self.turn_rate      = 1.5
        self.drag           = 0.2

        self.hit_radius = 200
        self.did_detonate = False

        # Colors
        C_RED = (255, 30, 30)
        C_ORANGE = (255, 140, 0)
        C_DARK = (40, 40, 45)

        # Jagged, aggressive spike shape
        self.verts = {
            'v0': (0, 0, 50),        # 0: Nose
            'v1': (-15, -10, -20),   # 1: Bottom left
            'v2': (15, -10, -20),    # 2: Bottom right
            'v3': (0, 20, -20),      # 3: Top fin
            'v4': (0, 0, -30),       # 4: Engine block
        }
        self.faces = [
            # Front spikes (Red/Orange)
            {'v': ['v0', 'v3', 'v1'], 'color': C_RED},
            {'v': ['v0', 'v2', 'v3'], 'color': C_RED},
            {'v': ['v0', 'v1', 'v2'], 'color': C_ORANGE},
            # Back tapers (Dark Grey)
            {'v': ['v1', 'v3', 'v4'], 'color': C_DARK},
            {'v': ['v3', 'v2', 'v4'], 'color': C_DARK},
            {'v': ['v2', 'v1', 'v4'], 'color': C_DARK},
        ]

    def set_pattern(self, pattern_name):
        if pattern_name in PATTERN_MAP:
            self.pattern = PATTERN_MAP[pattern_name]

    def update(self, dt, player_pos, player_orientation, global_projectiles=None, global_enemies=None, player=None):
        self.t += dt
        self.engine_time += dt
        self._pattern_check_timer += dt

        px, py, pz = player_pos
        dx, dy, dz = px - self.x, py - self.y, pz - self.z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1
        self._last_dist = dist
        nx, ny, nz = dx / dist, dy / dist, dz / dist

        if self.pattern is not None:
            active_pattern = self.pattern
        elif self._pattern_check_timer >= 0.5:
            self._pattern_check_timer = 0.0
            fwd = get_forward_from_quat(player_orientation)

            dot = nx * fwd[0] + ny * fwd[1] + nz * fwd[2]

            if dot < -0.82:
                self._pattern_cache = _pattern_direct
            else:
                if self._pattern_cache is _pattern_direct:
                    self._pattern_cache = random.choice(PATTERNS[1:])
                elif self._pattern_cache is None:
                    self._pattern_cache = random.choice(PATTERNS[1:])

            active_pattern = self._pattern_cache
        else:
            active_pattern = self._pattern_cache or _pattern_weave

        # Pattern offset becomes a lateral force impulse
        offset = active_pattern(self.t, self.pattern_phase, 1.0)
        lat_force = (
            offset[0] * self.thrust * 0.55,
            offset[1] * self.thrust * 0.55,
            offset[2] * self.thrust * 0.55,
        )

        # Proximity detonation (Ballistic Missile behavior)
        if dist < DRONE_DETONATION_RANGE:
            self.detonate(player)
            return

        # Proximity visual cue: pulse faster as it gets closer
        if dist < 1500:
            proximity_factor = 1.0 - (dist / 1500.0)
            self.engine_pulse_rate = 15.0 + proximity_factor * 30.0

        desired_heading = (nx, ny, nz)
        self._apply_newtonian(desired_heading, dt, lateral_force=lat_force)
        self._spawn_engine_trail()
        self._update_engine_trail(dt)

        if self._flicker > 0:
            self._flicker -= dt * 8

    def detonate(self, player=None):
        """Triggers proximity explosion and deals radial damage to player."""
        if player:
            dist = self.dist_to_player(player.pos)
            # Radial damage falloff: full damage at center, 0 at EXPLOSION_RADIUS
            falloff = max(0.0, 1.0 - (dist / DRONE_EXPLOSION_RADIUS))
            damage = DRONE_MAX_DAMAGE * falloff
            player.take_damage(damage)
        
        self.did_detonate = True
        self.hp = 0

    def on_hit(self, damage=1):
        self.hp -= damage
        self._flicker = 1
        if self._pattern_cache is _pattern_direct:
            self._pattern_cache = random.choice(PATTERNS[1:])


# ──────────────────────────────────────────────
#  DOGFIGHTER
# ──────────────────────────────────────────────

class Dogfighter(Enemy):
    SPEED = 2000
    FIRE_RANGE = 4500
    IDEAL_RANGE = 1000
    CIRCLE_RADIUS = 1500

    def __init__(self, x, y, z):
        super().__init__(x, y, z)

        self.hp = 5
        self.max_hp = 5
        self.t = 0
        self.base_color = (50, 0, 255)

        # Twin Blue Thrusters – repositioned to tail top
        self.engine_offsets = [(-32, -10, -45), (32, -10, -45)]
        self.engine_color = (60, 150, 255)
        self.engine_size = 4.5
        self.engine_pulse_rate = 8.0
        self.trail_life = 0.6
        self.trail_drift = 60.0
        self.hit_radius = 70

        self.mg_timer = 0.0
        self.bolt_timer = random.uniform(2.0, 5.0)

        self.mode = 'positioning'
        self.mode_timer = random.uniform(2.0, 4.0)
        self.phase = random.uniform(0, math.pi * 2)
        
        # Pattern and randomization settings
        self.pattern = random.choice(PATTERNS[1:])  # Skip 'direct'
        self.circle_sign = random.choice([1.0, -1.0])
        self.ideal_range = random.uniform(800, 1200)
        self.circle_radius = random.uniform(1200, 1800)
        self.pattern_scale = 2.5  # Dogfighters need larger sweeps than drones

        # ── Newtonian physics ──
        self.max_speed      = 2500.0
        self.thrust         = 5000.0
        self.lateral_thrust = 0.35
        self.turn_rate      = 2.0
        self.drag           = 0.01
        
        self._flicker = 0

        self.hit_radius = 200

        # Colors
        C_BLUE = (50, 80, 255)
        C_SILVER = (180, 180, 190)
        C_TEAL = (0, 180, 180)

        self.verts = {
            'v0': (0, 8, 105),       # 0: nose top
            'v1': (0, -8, 105),      # 1: nose bot
            'v2': (-30, 12, 30),     # 2: mid top L
            'v3': (30, 12, 30),      # 3: mid top R
            'v4': (-30, -12, 30),    # 4: mid bot L
            'v5': (30, -12, 30),     # 5: mid bot R
            'v6': (-120, -8, -30),   # 6: tip L
            'v7': (120, -8, -30),    # 7: tip R
            'v8': (-22, 10, -60),    # 8: tail top L
            'v9': (22, 10, -60),     # 9: tail top R
            'v10': (-22, -10, -60),  # 10: tail bot L
            'v11': (22, -10, -60),   # 11: tail bot R
            'v12': (0, 18, 60),      # 12: cockpit ridge
            'v13': (-65, -6, -55),   # 13: inner trail L
            'v14': (65, -6, -55),    # 14: inner trail R
        }
        self.faces = [
            {'v': ['v0', 'v12', 'v2'], 'color': C_SILVER},  # 0  nose→ridge→mid-top-L
            {'v': ['v0', 'v3', 'v12'], 'color': C_SILVER},  # 1  nose→mid-top-R→ridge
            {'v': ['v1', 'v0', 'v4'], 'color': C_BLUE},    # 2  belly: nose-bot→nose-top→mid-bot-L
            {'v': ['v1', 'v5', 'v0'], 'color': C_BLUE},    # 3  belly: nose-bot→mid-bot-R→nose-top
            {'v': ['v1', 'v4', 'v5'], 'color': C_BLUE},    # 4  belly cap
            {'v': ['v12', 'v8', 'v2'], 'color': C_BLUE},   # 5  ridge→tail-top-L→mid-top-L
            {'v': ['v12', 'v9', 'v8'], 'color': C_SILVER}, # 6  ridge→tail-top-R→tail-top-L
            {'v': ['v12', 'v3', 'v9'], 'color': C_BLUE},   # 7  ridge→mid-top-R→tail-top-R
            {'v': ['v2', 'v8', 'v13'], 'color': C_TEAL},   # 8  mid-top-L→tail-top-L→inner-trail-L
            {'v': ['v3', 'v14', 'v9'], 'color': C_TEAL},   # 9  mid-top-R→inner-trail-R→tail-top-R
            {'v': ['v4', 'v13', 'v10'], 'color': C_BLUE},  # 10 mid-bot-L→inner-trail-L→tail-bot-L
            {'v': ['v5', 'v11', 'v14'], 'color': C_BLUE},  # 11 mid-bot-R→tail-bot-R→inner-trail-R
            {'v': ['v4', 'v10', 'v5'], 'color': C_BLUE},   # 12 belly: mid-bot-L→tail-bot-L→mid-bot-R
            {'v': ['v5', 'v10', 'v11'], 'color': C_BLUE},  # 13 belly: mid-bot-R→tail-bot-L→tail-bot-R
            {'v': ['v2', 'v13', 'v6'], 'color': C_TEAL},   # 14 wing upper L
            {'v': ['v3', 'v7', 'v14'], 'color': C_TEAL},   # 15 wing upper R
            {'v': ['v4', 'v6', 'v13'], 'color': C_BLUE},   # 16 wing lower L
            {'v': ['v5', 'v14', 'v7'], 'color': C_BLUE},   # 17 wing lower R
            {'v': ['v0', 'v2', 'v6'], 'color': C_SILVER},  # 18 leading edge upper L
            {'v': ['v0', 'v7', 'v3'], 'color': C_SILVER},  # 19 leading edge upper R
            {'v': ['v0', 'v6', 'v4'], 'color': C_BLUE},    # 20 leading edge lower L
            {'v': ['v0', 'v5', 'v7'], 'color': C_BLUE},    # 21 leading edge lower R
            {'v': ['v8', 'v11', 'v10'], 'color': C_SILVER}, # 22 tail cap
            {'v': ['v8', 'v9', 'v11'], 'color': C_SILVER},  # 23 tail cap
            {'v': ['v13', 'v8', 'v10'], 'color': C_TEAL},   # 24 inner-trail-L→tail
            {'v': ['v14', 'v11', 'v9'], 'color': C_TEAL},   # 25 inner-trail-R→tail
        ]



    def _player_forward(self, orientation):
        return get_forward_from_quat(orientation)

    def update(self, dt, player_pos, player_orientation, global_projectiles=None, global_enemies=None, player=None):
        self.t += dt
        self.engine_time += dt
        self.mg_timer -= dt
        self.bolt_timer -= dt
        self.mode_timer -= dt

        px, py, pz = player_pos
        dist_to_player = self.dist_to_player(player_pos)
        self._last_dist = dist_to_player

        # --- COLLISION AVOIDANCE (LATERAL PEEL-OFF) ---
        if dist_to_player < 800:
            # Force a positioning break with a lateral peel-off
            self.mode = 'positioning'
            self.mode_timer = random.uniform(1.5, 3.0)
            
            # Target a point laterally offset to peel away
            target_x = self.x + self.right[0] * 1000 * self.circle_sign
            target_y = self.y + self.right[1] * 1000 * self.circle_sign
            target_z = self.z + self.right[2] * 1000 * self.circle_sign
        
        elif self.mode_timer <= 0:
            if self.mode == 'positioning':
                self.mode = 'attack_run'
                self.mode_timer = random.uniform(2.0, 4.0)
            else:
                self.mode = 'positioning'
                self.mode_timer = random.uniform(3.0, 5.0)
                self.phase = random.uniform(0, math.pi * 2)
                # Pick a new pattern for the next orbit
                self.pattern = random.choice(PATTERNS[1:])

        # Determine target point based on mode (if not already peeling off)
        if dist_to_player >= 800:
            if self.mode == 'positioning':
                pfw = self._player_forward(player_orientation)
                behind_x = px - pfw[0] * self.ideal_range
                behind_y = py - pfw[1] * self.ideal_range
                behind_z = pz - pfw[2] * self.ideal_range

                # Use selected pattern with amplitude scaling and circle sign
                offset = self.pattern(self.t, self.phase, self.SPEED)
                target_x = behind_x + offset[0] * self.pattern_scale * self.circle_sign
                target_y = behind_y + offset[1] * self.pattern_scale
                target_z = behind_z + offset[2] * self.pattern_scale
            else:
                # ATTACK RUN: Aim with a human-like lead
                if player is not None:
                    p_vx, p_vy, p_vz = player.vel
                    target_x = px + p_vx * 0.2
                    target_y = py + p_vy * 0.2
                    target_z = pz + p_vz * 0.2
                else:
                    target_x, target_y, target_z = px, py, pz

        dx = target_x - self.x
        dy = target_y - self.y
        dz = target_z - self.z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        desired_heading = (dx/dist, dy/dist, dz/dist)

        # Brake when closing on target point too fast
        if self._approaching_too_fast((target_x, target_y, target_z), brake_threshold=500.0):
            spd = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2) or 1.0
            desired_heading = (-self.vx/spd, -self.vy/spd, -self.vz/spd)

        # During positioning orbit, add a persistent lateral force to curve the path
        if self.mode == 'positioning':
            lat_force = (
                self.right[0] * self.circle_sign * self.thrust * 0.45,
                self.right[1] * self.circle_sign * self.thrust * 0.45,
                self.right[2] * self.circle_sign * self.thrust * 0.45,
            )
        else:
            lat_force = None

        self._apply_newtonian(desired_heading, dt, lateral_force=lat_force)

        # Re-check distance for firing logic
        dist_to_player = self.dist_to_player(player_pos)
        to_px, to_py, to_pz = px - self.x, py - self.y, pz - self.z

        if self.mode == 'attack_run' and dist_to_player < self.FIRE_RANGE:
            to_player_norm = (to_px / dist_to_player, to_py / dist_to_player, to_pz / dist_to_player)
            dot = (self.forward[0] * to_player_norm[0] +
                   self.forward[1] * to_player_norm[1] +
                   self.forward[2] * to_player_norm[2])

            if dot > 0.85:
                if self.mg_timer <= 0:
                    self.mg_timer = MG_COOLDOWN
                    self._fire_projectile(to_player_norm, global_projectiles, w_type='mg')

                if self.bolt_timer <= 0:
                    self.bolt_timer = random.uniform(5.0, 8.0)
                    self._fire_projectile(to_player_norm, global_projectiles, w_type='bolt')

        self._spawn_engine_trail()
        self._update_engine_trail(dt)
        if self._flicker > 0:
            self._flicker -= dt * 8

    def _fire_projectile(self, aim_dir, global_projectiles, w_type='mg'):
        if global_projectiles is None: return

        if w_type == 'mg':
            proj_speed = 15000
            spread = 0.13
            ax = aim_dir[0] + random.uniform(-spread, spread)
            ay = aim_dir[1] + random.uniform(-spread, spread)
            az = aim_dir[2] + random.uniform(-spread, spread)
            n = math.sqrt(ax * ax + ay * ay + az * az) or 1
            ax, ay, az = ax / n, ay / n, az / n

            vx = ax * proj_speed + self.vx * 0.3
            vy = ay * proj_speed + self.vy * 0.3
            vz = az * proj_speed + self.vz * 0.3

            global_projectiles.append(MachineGunBolt(
                self.x, self.y, self.z, vx, vy, vz
            ))

        elif w_type == 'bolt':
            proj_speed = 2200
            vx = aim_dir[0] * proj_speed + self.vx * 0.5
            vy = aim_dir[1] * proj_speed + self.vy * 0.5
            vz = aim_dir[2] * proj_speed + self.vz * 0.5

            global_projectiles.append(HomingBolt(
                self.x, self.y, self.z, vx, vy, vz
            ))

    def on_hit(self, damage=1):
        self.hp -= damage
        self._flicker = 1
        self.mode = 'attack_run'
        self.mode_timer = 3.0


# ===========================================================
# Sniper
# ===========================================================

class Sniper(Enemy):
    SPEED = 800          # was 1200, stays far but catchable now
    FIRE_RANGE = 7000
    FLEE_RANGE = 3500

    def __init__(self, x, y, z):
        super().__init__(x, y, z)

        self.hp = 1
        self.max_hp = 1
        self.hit_radius = 120       # was 70
        self.base_color = (210, 165, 45)

        # Single deep green thruster at back of long barrel
        self.engine_offsets = [(0, 0, -90)]
        self.engine_color = (255, 50, 50)
        self.engine_size = 6.0
        self.engine_pulse_rate = 2.0
        self.trail_life = 1.2
        self.trail_drift = 10.0

        self.hit_radius = 120

        self.state = 'aiming'
        self.timer = random.uniform(2.0, 4.0)
        self._flicker = 0

        # ── Newtonian physics ──
        self.max_speed      = 1100.0
        self.thrust         = 3000.0
        self.lateral_thrust = 0.2
        self.turn_rate      = 2.0
        self.drag           = 0.35

        # Colors
        C_GOLD = (210, 165, 45)
        C_SILVER = (180, 180, 190)
        C_RED = (220, 30, 30)

        # Symmetrical, needle-like railgun ship
        self.verts = {
            'v0': (0, 0, 150),       # 0: nose tip
            'v1': (-8, 0, 40),       # 1: barrel L
            'v2': (8, 0, 40),        # 2: barrel R
            'v3': (0, 8, 40),        # 3: barrel top
            'v4': (0, -8, 40),       # 4: barrel bot
            'v5': (-18, 12, 0),      # 5: shoulder TL
            'v6': (18, 12, 0),       # 6: shoulder TR
            'v7': (-18, -12, 0),     # 7: shoulder BL
            'v8': (18, -12, 0),      # 8: shoulder BR
            'v9': (-22, 16, -60),    # 9: rear TL
            'v10': (22, 16, -60),    # 10: rear TR
            'v11': (-22, -16, -60),  # 11: rear BL
            'v12': (22, -16, -60),   # 12: rear BR
            'v13': (-10, 8, -90),    # 13: tail TL
            'v14': (10, 8, -90),     # 14: tail TR
            'v15': (-10, -8, -90),   # 15: tail BL
            'v16': (10, -8, -90),    # 16: tail BR
        }
        self.faces = [
            {'v': ['v0', 'v2', 'v3'], 'color': C_RED},    # 0  needle right
            {'v': ['v0', 'v4', 'v2'], 'color': C_RED},    # 1  needle right-bot
            {'v': ['v0', 'v3', 'v1'], 'color': C_RED},    # 2  needle left
            {'v': ['v0', 'v1', 'v4'], 'color': C_RED},    # 3  needle left-bot
            {'v': ['v3', 'v6', 'v5'], 'color': C_GOLD},   # 4  barrel→shoulder top
            {'v': ['v3', 'v5', 'v1'], 'color': C_GOLD},   # 5  barrel→shoulder top-L
            {'v': ['v1', 'v5', 'v7'], 'color': C_GOLD},   # 6  barrel→shoulder left
            {'v': ['v1', 'v7', 'v4'], 'color': C_GOLD},   # 7  barrel→shoulder left-bot
            {'v': ['v4', 'v7', 'v8'], 'color': C_GOLD},   # 8  barrel→shoulder bot
            {'v': ['v4', 'v8', 'v2'], 'color': C_GOLD},   # 9  barrel→shoulder bot-R
            {'v': ['v2', 'v8', 'v6'], 'color': C_GOLD},   # 10 barrel→shoulder right
            {'v': ['v2', 'v6', 'v3'], 'color': C_GOLD},   # 11 barrel→shoulder right-top
            {'v': ['v5', 'v10', 'v9'], 'color': C_SILVER},# 12 shoulder→rear top
            {'v': ['v5', 'v6', 'v10'], 'color': C_SILVER},# 13 shoulder→rear top-R
            {'v': ['v5', 'v9', 'v11'], 'color': C_SILVER},# 14 shoulder→rear left
            {'v': ['v5', 'v11', 'v7'], 'color': C_SILVER},# 15 shoulder→rear left-bot
            {'v': ['v6', 'v12', 'v10'], 'color': C_SILVER},# 16 shoulder→rear right
            {'v': ['v6', 'v8', 'v12'], 'color': C_SILVER}, # 17 shoulder→rear right-bot
            {'v': ['v7', 'v11', 'v12'], 'color': C_SILVER},# 18 shoulder→rear bot
            {'v': ['v7', 'v12', 'v8'], 'color': C_SILVER}, # 19 shoulder→rear bot-R
            {'v': ['v9', 'v14', 'v13'], 'color': C_SILVER},# 20 rear→tail top
            {'v': ['v9', 'v10', 'v14'], 'color': C_SILVER},# 21 rear→tail top-R
            {'v': ['v9', 'v13', 'v15'], 'color': C_SILVER},# 22 rear→tail left
            {'v': ['v9', 'v15', 'v11'], 'color': C_SILVER},# 23 rear→tail left-bot
            {'v': ['v10', 'v16', 'v14'], 'color': C_SILVER},# 24 rear→tail right
            {'v': ['v10', 'v12', 'v16'], 'color': C_SILVER},# 25 rear→tail right-bot
            {'v': ['v11', 'v15', 'v16'], 'color': C_SILVER},# 26 rear→tail bot
            {'v': ['v11', 'v16', 'v12'], 'color': C_SILVER},# 27 rear→tail bot-R
            {'v': ['v13', 'v16', 'v15'], 'color': C_GOLD},  # 28 tail cap
            {'v': ['v13', 'v14', 'v16'], 'color': C_GOLD},  # 29 tail cap
        ]

    
    def update(self, dt, player_pos, player_orientation, global_projectiles=None, global_enemies=None, player=None):
        self.timer -= dt
        self.engine_time += dt
        px, py, pz = player_pos

        dx, dy, dz = px - self.x, py - self.y, pz - self.z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        self._last_dist = dist
        nx, ny, nz = dx / dist, dy / dist, dz / dist

        if dist < self.FLEE_RANGE:
            self.state = 'fleeing'
            self.base_color = (20, 20, 30)      # was (255, 255, 255)
            self.engine_size = 0.0              # kill trail while cloaked
        elif self.state == 'fleeing' and dist > self.FLEE_RANGE + 1000:
            self.state = 'aiming'
            self.timer = 2.0
            self.base_color = (210, 165, 45)   # uncloak on re-engage
            self.engine_size = 6.0

        if self.state == 'aiming' and self.timer <= 0:
            self.state = 'charging'
            self.timer = 1.5

        if self.state == 'charging':
            flash = int((math.sin(self.timer * 20) + 1) * 127)
            self.base_color = (255, flash, flash)

            if self.timer <= 0:
                # --- LIGHT-SPEED RAYCAST HIT CHECK ---
                from src.constants import PLAYER_COLLISION_RADIUS
                
                dx_p, dy_p, dz_p = px - self.x, py - self.y, pz - self.z
                dist_f = math.sqrt(dx_p*dx_p + dy_p*dy_p + dz_p*dz_p) or 1.0
                
                # closest approach of beam line to player center
                # cross product magnitude gives perpendicular distance
                cx = (dy_p/dist_f)*self.forward[2] - (dz_p/dist_f)*self.forward[1]
                cy = (dz_p/dist_f)*self.forward[0] - (dx_p/dist_f)*self.forward[2]
                cz = (dx_p/dist_f)*self.forward[1] - (dy_p/dist_f)*self.forward[0]
                perp_dist = math.sqrt(cx*cx + cy*cy + cz*cz) * dist_f
                
                dot = (dx_p/dist_f)*self.forward[0] + (dy_p/dist_f)*self.forward[1] + (dz_p/dist_f)*self.forward[2]
                
                if player is not None and dot > 0 and perp_dist < PLAYER_COLLISION_RADIUS:
                    player.take_damage(50)
                
                # spawn visual beam regardless of hit
                if global_projectiles is not None:
                    global_projectiles.append(SniperBeam(
                        self.x, self.y, self.z,
                        self.forward[0] * 32000,
                        self.forward[1] * 32000,
                        self.forward[2] * 32000
                    ))
                
                self.state = 'aiming'
                self.timer = random.uniform(4.0, 6.0)
                self.base_color = (210, 165, 45)

        if self.state == 'fleeing':
            # Rotate away from player and thrust
            desired_heading = (-nx, -ny, -nz)
            self._apply_newtonian(desired_heading, dt)
        elif self.state == 'aiming':
            # Face player (for accurate raycast), drift laterally
            desired_heading = (nx, ny, nz)
            lat_force = (
                self.right[0] * self.thrust * 0.18,
                self.right[1] * self.thrust * 0.18,
                self.right[2] * self.thrust * 0.18,
            )
            self._apply_newtonian(desired_heading, dt, lateral_force=lat_force)
        elif self.state == 'charging':
            # Hold position: face player for raycast but no thrust (drag bleeds speed)
            desired_heading = (nx, ny, nz)
            saved = self.thrust
            self.thrust = 0.0
            self._apply_newtonian(desired_heading, dt)
            self.thrust = saved

        self._spawn_engine_trail()
        self._update_engine_trail(dt)

    def on_hit(self, damage=1):
        self.hp -= damage
        self._flicker = 1


# =============================================================
# Corvette
# =============================================================

class Corvette(Enemy):
    SPEED = 500
    FIRE_RANGE = 4000

    def __init__(self, x, y, z):
        super().__init__(x, y, z)

        self.hp = 30
        self.max_hp = 30
        self.base_color = (180, 180, 200)

        self.hit_radius = 400

        # Huge thruster block for a massive ship
        self.engine_offsets = [
            (-50, -10, -200), (50, -10, -200),
            (-20, 20, -200), (20, 20, -200)
        ]
        self.engine_color = (255, 140, 0)
        self.engine_size = 12.0
        self.engine_pulse_rate = 3.0
        self.trail_life = 1.0
        self.trail_drift = 30.0

        self.turret_timer = 0.0
        self.spawn_timer = random.uniform(5.0, 10.0)
        self._flicker = 0
        self.t = random.uniform(0, 100)

        # ── Newtonian physics ──
        self.max_speed      = 600.0
        self.thrust         = 2000.0
        self.lateral_thrust = 0.2
        self.turn_rate      = 1.2
        self.drag           = 0.15

        # Colors
        C_STEEL = (70, 75, 85)
        C_GOLD = (210, 170, 50)
        C_CRIMSON = (160, 20, 30)

        self.verts = {
            # --- Forward pod ---
            'v0': (0, 20, 250),      # 0  nose top      (windshield top edge, set back)
            'v1': (0, -25, 270),     # 1  nose chin     (windshield bot edge, juts forward+down)
            'v2': (-40, 20, 180),    # 2  pod top-left
            'v3': (40, 20, 180),     # 3  pod top-right
            'v4': (-40, -15, 180),   # 4  pod bot-left
            'v5': (40, -15, 180),    # 5  pod bot-right
            # --- Central spine ---
            'v6': (-15, 8, 80),      # 6  spine front top-left
            'v7': (15, 8, 80),       # 7  spine front top-right
            'v8': (-15, -8, 80),     # 8  spine front bot-left
            'v9': (15, -8, 80),      # 9  spine front bot-right
            'v10': (-15, 8, -200),   # 10 spine rear top-left
            'v11': (15, 8, -200),    # 11 spine rear top-right
            'v12': (-15, -8, -200),  # 12 spine rear bot-left
            'v13': (15, -8, -200),   # 13 spine rear bot-right
            # --- Left nacelle ---
            'v14': (-40, -5, 80),    # 14 nacelle-L front top-inner
            'v15': (-90, -5, 80),    # 15 nacelle-L front top-outer
            'v16': (-40, -20, 80),   # 16 nacelle-L front bot-inner
            'v17': (-90, -20, 80),   # 17 nacelle-L front bot-outer
            'v18': (-40, -5, -180),  # 18 nacelle-L rear top-inner
            'v19': (-90, -5, -180),  # 19 nacelle-L rear top-outer
            'v20': (-40, -20, -180), # 20 nacelle-L rear bot-inner
            'v21': (-90, -20, -180), # 21 nacelle-L rear bot-outer
            # --- Right nacelle ---
            'v22': (40, -5, 80),     # 22 nacelle-R front top-inner
            'v23': (90, -5, 80),     # 23 nacelle-R front top-outer
            'v24': (40, -20, 80),    # 24 nacelle-R front bot-inner
            'v25': (90, -20, 80),    # 25 nacelle-R front bot-outer
            'v26': (40, -5, -180),   # 26 nacelle-R rear top-inner
            'v27': (90, -5, -180),   # 27 nacelle-R rear top-outer
            'v28': (40, -20, -180),  # 28 nacelle-R rear bot-inner
            'v29': (90, -20, -180),  # 29 nacelle-R rear bot-outer
        }
        self.faces = [
            {'v': ['v0', 'v1', 'v5'], 'color': C_GOLD},    # 0 pod front top
            {'v': ['v0', 'v4', 'v1'], 'color': C_GOLD},    # 1 pod front top
            {'v': ['v0', 'v3', 'v2'], 'color': C_GOLD},    # 2 pod top
            {'v': ['v0', 'v2', 'v4'], 'color': C_GOLD},    # 3 pod side L
            {'v': ['v0', 'v5', 'v3'], 'color': C_GOLD},    # 4 pod side R
            {'v': ['v1', 'v5', 'v4'], 'color': C_STEEL},   # 5 pod bot
            {'v': ['v2', 'v5', 'v3'], 'color': C_STEEL},   # 6 pod back
            {'v': ['v2', 'v4', 'v5'], 'color': C_STEEL},   # 7 pod back
            {'v': ['v2', 'v7', 'v6'], 'color': C_STEEL},   # 8 spine join top
            {'v': ['v2', 'v3', 'v7'], 'color': C_STEEL},   # 9 spine join top
            {'v': ['v4', 'v9', 'v8'], 'color': C_STEEL},   # 10 spine join bot
            {'v': ['v4', 'v5', 'v9'], 'color': C_STEEL},   # 11 spine join bot
            {'v': ['v6', 'v7', 'v11'], 'color': C_STEEL},  # 12 spine top
            {'v': ['v6', 'v11', 'v10'], 'color': C_STEEL}, # 13 spine top
            {'v': ['v8', 'v13', 'v9'], 'color': C_STEEL},  # 14 spine bot
            {'v': ['v8', 'v12', 'v13'], 'color': C_STEEL}, # 15 spine bot
            {'v': ['v6', 'v10', 'v12'], 'color': C_STEEL}, # 16 spine side L
            {'v': ['v6', 'v12', 'v8'], 'color': C_STEEL},  # 17 spine side L
            {'v': ['v7', 'v9', 'v13'], 'color': C_STEEL},  # 18 spine side R
            {'v': ['v7', 'v13', 'v11'], 'color': C_STEEL}, # 19 spine side R
            {'v': ['v10', 'v11', 'v13'], 'color': C_STEEL},# 20 spine back
            {'v': ['v10', 'v13', 'v12'], 'color': C_STEEL},# 21 spine back
            {'v': ['v14', 'v15', 'v17'], 'color': C_CRIMSON}, # 22 nacelle L front
            {'v': ['v14', 'v17', 'v16'], 'color': C_CRIMSON}, # 23 nacelle L front
            {'v': ['v18', 'v20', 'v21'], 'color': C_STEEL}, # 24 nacelle L back
            {'v': ['v18', 'v21', 'v19'], 'color': C_STEEL}, # 25 nacelle L back
            {'v': ['v15', 'v19', 'v21'], 'color': C_CRIMSON}, # 26 nacelle L outer
            {'v': ['v15', 'v21', 'v17'], 'color': C_CRIMSON}, # 27 nacelle L outer
            {'v': ['v14', 'v20', 'v16'], 'color': C_STEEL}, # 28 nacelle L inner
            {'v': ['v14', 'v18', 'v20'], 'color': C_STEEL}, # 29 nacelle L inner
            {'v': ['v14', 'v19', 'v15'], 'color': C_CRIMSON}, # 30 nacelle L top
            {'v': ['v14', 'v18', 'v19'], 'color': C_CRIMSON}, # 31 nacelle L top
            {'v': ['v16', 'v17', 'v21'], 'color': C_STEEL}, # 32 nacelle L bot
            {'v': ['v16', 'v21', 'v20'], 'color': C_STEEL}, # 33 nacelle L bot
            {'v': ['v22', 'v25', 'v23'], 'color': C_CRIMSON}, # 34 nacelle R front
            {'v': ['v22', 'v24', 'v25'], 'color': C_CRIMSON}, # 35 nacelle R front
            {'v': ['v26', 'v29', 'v28'], 'color': C_STEEL}, # 36 nacelle R back
            {'v': ['v26', 'v27', 'v29'], 'color': C_STEEL}, # 37 nacelle R back
            {'v': ['v23', 'v25', 'v29'], 'color': C_CRIMSON}, # 38 nacelle R outer
            {'v': ['v23', 'v29', 'v27'], 'color': C_CRIMSON}, # 39 nacelle R outer
            {'v': ['v22', 'v28', 'v26'], 'color': C_STEEL}, # 40 nacelle R inner
            {'v': ['v22', 'v24', 'v28'], 'color': C_STEEL}, # 41 nacelle R inner
            {'v': ['v22', 'v23', 'v27'], 'color': C_CRIMSON}, # 42 nacelle R top
            {'v': ['v22', 'v27', 'v26'], 'color': C_CRIMSON}, # 43 nacelle R top
            {'v': ['v24', 'v29', 'v25'], 'color': C_STEEL}, # 44 nacelle R bot
            {'v': ['v24', 'v28', 'v29'], 'color': C_STEEL}, # 45 nacelle R bot
        ]
    def update(self, dt, player_pos, player_orientation, global_projectiles=None, global_enemies=None, player=None):
        self.t += dt
        self.engine_time += dt
        self.turret_timer -= dt
        self.spawn_timer -= dt

        px, py, pz = player_pos
        dx, dy, dz = px - self.x, py - self.y, pz - self.z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        self._last_dist = dist
        nx, ny, nz = dx / dist, dy / dist, dz / dist

        self._apply_newtonian((nx, ny, nz), dt)

        # Weaponry
        if dist < self.FIRE_RANGE and self.turret_timer <= 0:
            self.turret_timer = 0.3
            if global_projectiles is not None:
                spread = 0.05
                ax, ay, az = nx + random.uniform(-spread, spread), ny + random.uniform(-spread, spread), nz + random.uniform(-spread, spread)
                n = math.sqrt(ax * ax + ay * ay + az * az) or 1
                ax, ay, az = ax / n, ay / n, az / n

                global_projectiles.append(CorvetteTurret(
                    self.x, self.y, self.z,
                    ax * 4000 + self.vx * 0.5,
                    ay * 4000 + self.vy * 0.5,
                    az * 4000 + self.vz * 0.5
                ))

        # Drone Spawning
        if self.spawn_timer <= 0 and dist < 12000:
            self.spawn_timer = 8.0
            if global_enemies is not None:
                drone = SuicideDrone(self.x, self.y - 40, self.z)
                drone.vx, drone.vy, drone.vz = self.vx, self.vy - 300, self.vz
                drone.set_pattern(random.choice(['weave', 'wobble', 'spiral', 'zigzag', 'corkscrew']))
                global_enemies.append(drone)

        self._spawn_engine_trail()
        self._update_engine_trail(dt)
        if self._flicker > 0: self._flicker -= dt * 8

    def on_hit(self, damage=1):
        self.hp -= damage
        self._flicker = 1


# =============================================================
# Minelayer
# =============================================================

class Minelayer(Enemy):
    SPEED = 1400

    def __init__(self, x, y, z):
        super().__init__(x, y, z)
        self.hp = 12
        self.max_hp = 12
        self.visible_color = (255, 140, 0)
        self.stealth_color = (20, 20, 30)
        self.base_color = self.stealth_color

        self.hit_radius = 200.0
        self.stealthed = True

        # 4 spaced out thrusters
        self.engine_offsets = [
            (-60, 0, -30), (-20, 0, -30),
            (20, 0, -30), (60, 0, -30)
        ]
        self.engine_color = (255, 210, 0)
        self.engine_size = 5.0
        self.engine_pulse_rate = 4.0
        self.trail_life = 0.5
        self.trail_drift = 80.0

        self.state = 'traveling'
        self.flank_offset = None
        self.bombing_timer = 0.0
        self.heavy_mg_timer = 0.0
        self._flicker = 0

        # ── Newtonian physics ──
        self.max_speed      = 1500.0
        self.thrust         = 4000.0
        self.lateral_thrust = 0.3
        self.turn_rate      = 2.5
        self.drag           = 0.35

        # Colors
        C_YELLOW = (255, 210, 0)
        C_BLACK = (30, 30, 35)
        C_RUST = (180, 70, 20)

        # Wide, flat wing shape
        self.verts = {
            'v0': (0, 0, 40),        # 0: Center Nose
            'v1': (-80, -5, -10),    # 1: Far Left
            'v2': (80, -5, -10),     # 2: Far Right
            'v3': (-30, 15, -20),    # 3: Mid Left Bulk
            'v4': (30, 15, -20),     # 4: Mid Right Bulk
            'v5': (0, -15, -30),     # 5: Underbelly
        }
        self.faces = [
            {'v': ['v0', 'v3', 'v1'], 'color': C_YELLOW},
            {'v': ['v0', 'v2', 'v4'], 'color': C_YELLOW},
            {'v': ['v0', 'v4', 'v3'], 'color': C_BLACK},
            {'v': ['v0', 'v1', 'v5'], 'color': C_RUST},
            {'v': ['v0', 'v5', 'v2'], 'color': C_RUST},
            {'v': ['v1', 'v3', 'v5'], 'color': C_BLACK},
            {'v': ['v2', 'v5', 'v4'], 'color': C_BLACK},
            {'v': ['v3', 'v4', 'v5'], 'color': C_BLACK},
        ]

    def _pick_flank_offset(self, p_fwd):
        dist = random.uniform(3500, 5000)
        phi = random.uniform(0, 2 * math.pi)
        costheta = random.uniform(-0.5, 0.5)
        theta = math.acos(costheta)
        rx = math.sin(theta) * math.cos(phi)
        ry = math.sin(theta) * math.sin(phi)
        rz = math.cos(theta)
        
        # bias away from player forward
        dot = rx * p_fwd[0] + ry * p_fwd[1] + rz * p_fwd[2]
        if dot > 0:
            rx, ry, rz = -rx, -ry, -rz
            
        self.flank_offset = (rx * dist, ry * dist, rz * dist)

    def update(self, dt, player_pos, player_orientation, global_projectiles=None, global_enemies=None, player=None):
        self.engine_time += dt
        px, py, pz = player_pos
        dx, dy, dz = px - self.x, py - self.y, pz - self.z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        self._last_dist = dist
        nx, ny, nz = dx / dist, dy / dist, dz / dist
        p_fwd = get_forward_from_quat(player_orientation)

        # State transition: Defensive check
        if dist < 3000:
            self.state = 'defensive'
        elif self.state == 'defensive' and dist > 4500:
            self.state = 'traveling'
            self.flank_offset = None

        if self.state == 'traveling':
            self.stealthed = True
            self.base_color = self.stealth_color
            self.hit_radius = 200.0
            
            if self.flank_offset is None:
                self._pick_flank_offset(p_fwd)
                
            tx, ty, tz = px + self.flank_offset[0], py + self.flank_offset[1], pz + self.flank_offset[2]
            tdx, tdy, tdz = tx - self.x, ty - self.y, tz - self.z
            tdist = math.sqrt(tdx*tdx + tdy*tdy + tdz*tdz)
            
            if tdist < 500:
                self.state = 'bombing'
                self.bombing_timer = 4.0
                
            target_x, target_y, target_z = tx, ty, tz

        elif self.state == 'bombing':
            self.stealthed = False
            self.base_color = self.visible_color
            self.hit_radius = 100.0
            
            # Fly across
            target_x, target_y, target_z = px - p_fwd[0] * 3000, py - p_fwd[1] * 3000, pz - p_fwd[2] * 3000
            
            self.bombing_timer -= dt
            if int(self.bombing_timer * 8) % 8 == 0 and random.random() < 0.3:
                if global_projectiles is not None:
                    global_projectiles.append(Mine(self.x, self.y, self.z, 0, 0, 0))
            
            if self.bombing_timer <= 0:
                self.state = 'traveling'
                self.flank_offset = None

        elif self.state == 'defensive':
            self.stealthed = False
            self.base_color = self.visible_color
            self.hit_radius = 100.0
            
            # Close in somewhat aggressively if still far, then back away
            if dist > 2000:
                target_x, target_y, target_z = px, py, pz
            else:
                target_x, target_y, target_z = self.x - nx * 1000, self.y - ny * 1000, self.z - nz * 1000
            
            self.heavy_mg_timer -= dt
            if self.heavy_mg_timer <= 0:
                self.heavy_mg_timer = 0.15 # Faster refire
                if global_projectiles is not None:
                    proj_speed = 12000
                    spread = 0.08
                    ax, ay, az = nx + random.uniform(-spread, spread), ny + random.uniform(-spread, spread), nz + random.uniform(-spread, spread)
                    bolt = MachineGunBolt(self.x, self.y, self.z, ax * proj_speed, ay * proj_speed, az * proj_speed)
                    bolt.damage = 4.0  # Even heavier damage
                    bolt.color = (255, 100, 0)
                    global_projectiles.append(bolt)

        tdx, tdy, tdz = target_x - self.x, target_y - self.y, target_z - self.z
        tdist = math.sqrt(tdx * tdx + tdy * tdy + tdz * tdz) or 1
        desired_heading = (tdx/tdist, tdy/tdist, tdz/tdist)

        # Brake if closing too fast on target
        if self._approaching_too_fast((target_x, target_y, target_z), brake_threshold=450.0):
            spd = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2) or 1.0
            desired_heading = (-self.vx/spd, -self.vy/spd, -self.vz/spd)

        self._apply_newtonian(desired_heading, dt)

        if not self.stealthed:
            self.engine_size = 6.0
            self._spawn_engine_trail()
        else:
            self.engine_size = 0.0

        self._update_engine_trail(dt)
        if self._flicker > 0: self._flicker -= dt * 8

    def on_hit(self, damage=1):
        self.hp -= damage
        self._flicker = 1
        if self.state == 'traveling' and random.random() < 0.3:
            self.flank_offset = None



# =============================================================
# Stealth Interceptor
# =============================================================

class StealthInterceptor(Enemy):
    SPEED = 2500

    def __init__(self, x, y, z):
        super().__init__(x, y, z)
        self.hp = 2
        self.max_hp = 2
        self.base_color = (20, 20, 30)

        # Twin thin thrusters
        self.engine_offsets = [(-10, 2, -30), (10, 2, -30)]
        self.engine_color = (180, 0, 255)
        self.engine_size = 4.0
        self.engine_pulse_rate = 12.0
        self.trail_life = 0.3
        self.trail_drift = 20.0

        self.stealthed = True
        self.state = 'traveling'
        self._flicker = 0
        
        self.flank_offset = None
        self.reached_flank = False
        self.hit_radius = 200.0

        # ── Newtonian physics ──
        self.max_speed      = 2800.0
        self.thrust         = 12000.0
        self.lateral_thrust = 0.15
        self.turn_rate      = 5.0
        self.drag           = 0.5

        # Colors
        C_VOID = (15, 15, 20)
        C_PURPLE = (80, 0, 120)
        C_CYAN = (0, 255, 255)

        # Extremely thin, planar dart
        self.verts = {
            'v0': (0, 0, 60),        # 0: Needle point
            'v1': (-25, 0, -30),     # 1: Left Wing
            'v2': (25, 0, -30),      # 2: Right Wing
            'v3': (0, 5, -20),       # 3: Top ridge
            'v4': (0, -5, -20),      # 4: Bottom ridge
        }
        self.faces = [
            {'v': ['v0', 'v3', 'v1'], 'color': C_PURPLE},
            {'v': ['v0', 'v2', 'v3'], 'color': C_PURPLE},
            {'v': ['v0', 'v1', 'v4'], 'color': C_VOID},
            {'v': ['v0', 'v4', 'v2'], 'color': C_VOID},
            {'v': ['v1', 'v3', 'v2'], 'color': C_CYAN},
            {'v': ['v1', 'v2', 'v4'], 'color': C_VOID},
        ]

    def _pick_flank_offset(self, p_fwd):
        dist = random.uniform(2500, 3500)
        for _ in range(10):
            phi = random.uniform(0, 2 * math.pi)
            costheta = random.uniform(-1, 1)
            theta = math.acos(costheta)
            rx = math.sin(theta) * math.cos(phi)
            ry = math.sin(theta) * math.sin(phi)
            rz = math.cos(theta)
            
            dot = rx * p_fwd[0] + ry * p_fwd[1] + rz * p_fwd[2]
            if dot < 0.2: # Bias away from frontal approach
                self.flank_offset = (rx * dist, ry * dist, rz * dist)
                break
        else:
            self.flank_offset = (-p_fwd[0] * dist, -p_fwd[1] * dist, -p_fwd[2] * dist)
        self.reached_flank = False

    def update(self, dt, player_pos, player_orientation, global_projectiles=None, global_enemies=None, player=None):
        self.engine_time += dt
        px, py, pz = player_pos
        dx, dy, dz = px - self.x, py - self.y, pz - self.z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        self._last_dist = dist
        nx, ny, nz = dx / dist, dy / dist, dz / dist
        p_fwd = get_forward_from_quat(player_orientation)

        if self.flank_offset is None:
            self._pick_flank_offset(p_fwd)

        if self.state == 'traveling':
            self.stealthed = True
            self.base_color = (20, 20, 30)
            self.hit_radius = 200.0
            
            if not self.reached_flank:
                tx, ty, tz = px + self.flank_offset[0], py + self.flank_offset[1], pz + self.flank_offset[2]
                tdx, tdy, tdz = tx - self.x, ty - self.y, tz - self.z
                tdist = math.sqrt(tdx*tdx + tdy*tdy + tdz*tdz)
                if tdist < 200:
                    self.reached_flank = True
                target_x, target_y, target_z = tx, ty, tz
            else:
                target_x, target_y, target_z = px, py, pz
                if dist < 1200:
                    self.state = 'attacking'
                    self.stealthed = False
                    self.base_color = (100, 100, 255)
                    self.hit_radius = 100.0

        elif self.state == 'attacking':
            target_x, target_y, target_z = px, py, pz
            if global_projectiles is not None:
                for _ in range(7):
                    spread = WEAPON_SPREAD
                    ax, ay, az = nx + random.uniform(-spread, spread), ny + random.uniform(-spread, spread), nz + random.uniform(-spread, spread)
                    global_projectiles.append(StealthShotgun(
                        self.x, self.y, self.z,
                        ax * 3000, ay * 3000, az * 3000
                    ))
            self.state = 'fleeing'
            self.stealthed = True
            self.base_color = (20, 20, 30)
            self.hit_radius = 200.0

        elif self.state == 'fleeing':
            self.stealthed = True
            self.base_color = (20, 20, 30)
            self.hit_radius = 200.0
            target_x, target_y, target_z = self.x - nx * 1000, self.y - ny * 1000, self.z - nz * 1000
            if dist > 4000:
                self._pick_flank_offset(p_fwd)
                self.state = 'traveling'

        tdx, tdy, tdz = target_x - self.x, target_y - self.y, target_z - self.z
        tdist = math.sqrt(tdx * tdx + tdy * tdy + tdz * tdz) or 1
        desired_heading = (tdx/tdist, tdy/tdist, tdz/tdist)

        # Brake when closing on target to prevent overshoot
        if self._approaching_too_fast((target_x, target_y, target_z), brake_threshold=600.0):
            spd = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2) or 1.0
            desired_heading = (-self.vx/spd, -self.vy/spd, -self.vz/spd)

        self._apply_newtonian(desired_heading, dt)

        if not self.stealthed:
            self.engine_size = 6.0
            self._spawn_engine_trail()
        else:
            self.engine_size = 0.0

        self._update_engine_trail(dt)
        if self._flicker > 0: self._flicker -= dt * 8

    def on_hit(self, damage=1):
        self.hp -= damage
        self._flicker = 1



# =============================================================
# Carrier
# =============================================================

class Carrier(Enemy):
    SPEED = 200

    def __init__(self, x, y, z):
        super().__init__(x, y, z)
        self.hp = 100
        self.max_hp = 100
        self.base_color = (120, 100, 150)

        self.hit_radius = 800.0

        # Massive thruster bank
        self.engine_offsets = [
            (0, -30, -500),  # Center Main Drive
            (-120, 0, -500), (120, 0, -500),  # Outer Drives
            (-60, -40, -500), (60, -40, -500)  # Lower Drives
        ]
        self.engine_color = (200, 100, 255)
        self.engine_size = 25.0
        self.engine_pulse_rate = 1.5
        self.trail_life = 1.5
        self.trail_drift = 20.0

        self.spawn_timer = 5.0
        self.sniper_timer = random.uniform(6.0, 12.0)
        self.bolt_timer = 4.0
        self.mg_timer = 0.1
        self.state = 'idle' # For sniper charge visual
        self._flicker = 0

        # ── Newtonian physics ──
        self.max_speed      = 250.0
        self.thrust         = 800.0
        self.lateral_thrust = 0.1
        self.turn_rate      = 0.6
        self.drag           = 0.08

        # Colors
        C_ROYAL = (90, 45, 130)
        C_GOLD = (210, 165, 45)
        C_WHITE = (235, 235, 240)

        self.verts = {
            'v0': (0, -20, 800),     # 0: Ultimate Nose
            'v1': (0, 80, -200),     # 1: Command Ridge Top Front
            'v2': (0, 180, -450),    # 2: Command Tower High
            'v3': (-400, -20, -500), # 3: Far Wingtip L
            'v4': (400, -20, -500),  # 4: Far Wingtip R
            'v5': (-150, 60, -500),  # 5: Back Top L
            'v6': (150, 60, -500),   # 6: Back Top R
            'v7': (-150, -80, -500), # 7: Back Bot L
            'v8': (150, -80, -500),  # 8: Back Bot R
            'v9': (0, -120, -100),   # 9: Deep Belly
        }
        self.faces = [
            {'v': ['v0', 'v5', 'v3'], 'color': C_ROYAL},
            {'v': ['v0', 'v1', 'v5'], 'color': C_WHITE},
            {'v': ['v0', 'v6', 'v1'], 'color': C_WHITE},
            {'v': ['v0', 'v4', 'v6'], 'color': C_ROYAL},
            {'v': ['v1', 'v2', 'v5'], 'color': C_GOLD},
            {'v': ['v1', 'v6', 'v2'], 'color': C_GOLD},
            {'v': ['v5', 'v2', 'v6'], 'color': C_GOLD},
            {'v': ['v0', 'v3', 'v7'], 'color': C_ROYAL},
            {'v': ['v0', 'v7', 'v9'], 'color': C_ROYAL},
            {'v': ['v0', 'v9', 'v8'], 'color': C_ROYAL},
            {'v': ['v0', 'v8', 'v4'], 'color': C_ROYAL},
            {'v': ['v5', 'v7', 'v3'], 'color': C_ROYAL},
            {'v': ['v6', 'v4', 'v8'], 'color': C_ROYAL},
            {'v': ['v5', 'v8', 'v7'], 'color': C_ROYAL},
            {'v': ['v5', 'v6', 'v8'], 'color': C_ROYAL},
        ]

    def is_hit(self, px, py, pz):
        dx, dy, dz = px - self.x, py - self.y, pz - self.z
        local_x = dx * self.right[0]   + dy * self.right[1]   + dz * self.right[2]
        local_y = dx * self.up[0]      + dy * self.up[1]      + dz * self.up[2]
        local_z = dx * self.forward[0] + dy * self.forward[1] + dz * self.forward[2]
        hit_x = -400 <= local_x <= 400
        hit_y = -120 <= local_y <= 180
        hit_z = -500 <= local_z <= 800
        return hit_x and hit_y and hit_z

    def update(self, dt, player_pos, player_orientation, global_projectiles=None, global_enemies=None, player=None):
        self.spawn_timer -= dt
        self.sniper_timer -= dt
        self.bolt_timer -= dt
        self.mg_timer -= dt
        self.engine_time += dt

        px, py, pz = player_pos
        dx, dy, dz = px - self.x, py - self.y, pz - self.z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        self._last_dist = dist
        nx, ny, nz = dx / dist, dy / dist, dz / dist

        # Movement: orbit at range using Newtonian thrust
        if dist < 7000:
            desired_heading = (-nx, -ny, -nz)  # back away
        elif dist > 9000:
            desired_heading = (nx, ny, nz)     # close in
        else:
            # Hold at distance — thrust laterally to avoid hovering dead still
            desired_heading = (self.right[0], self.right[1], self.right[2])

        self._apply_newtonian(desired_heading, dt)

        # --- ARSENAL ---
        
        # 1. Sniper Raycast
        if self.state == 'charging':
            if self.sniper_timer <= 0:
                # Fire Raycast
                from src.constants import PLAYER_COLLISION_RADIUS
                dx_p, dy_p, dz_p = px - self.x, py - self.y, pz - self.z
                dist_f = math.sqrt(dx_p*dx_p + dy_p*dy_p + dz_p*dz_p) or 1.0
                # closest approach
                cx = (dy_p/dist_f)*self.forward[2] - (dz_p/dist_f)*self.forward[1]
                cy = (dz_p/dist_f)*self.forward[0] - (dx_p/dist_f)*self.forward[2]
                cz = (dx_p/dist_f)*self.forward[1] - (dy_p/dist_f)*self.forward[0]
                perp_dist = math.sqrt(cx*cx + cy*cy + cz*cz) * dist_f
                dot = (dx_p/dist_f)*self.forward[0] + (dy_p/dist_f)*self.forward[1] + (dz_p/dist_f)*self.forward[2]
                
                if player is not None and dot > 0 and perp_dist < PLAYER_COLLISION_RADIUS:
                    player.take_damage(20)
                
                if global_projectiles is not None:
                    global_projectiles.append(SniperBeam(self.x, self.y, self.z, self.forward[0]*32000, self.forward[1]*32000, self.forward[2]*32000))
                
                self.state = 'idle'
                self.sniper_timer = random.uniform(8.0, 12.0)
        elif self.sniper_timer <= 0 and dist < 12000:
            self.state = 'charging'
            self.sniper_timer = 1.5 # Charge duration

        # 2. Homing Bolts
        if self.bolt_timer <= 0 and dist < 8000:
            self.bolt_timer = 4.0
            if global_projectiles is not None:
                for _ in range(3):
                    spread = 0.3
                    bx, by, bz = nx + random.uniform(-spread, spread), ny + random.uniform(-spread, spread), nz + random.uniform(-spread, spread)
                    global_projectiles.append(HomingBolt(self.x, self.y, self.z, bx * 2000, by * 2000, bz * 2000))

        # 3. Point Defense MG
        if self.mg_timer <= 0 and dist < 4000:
            self.mg_timer = 0.1
            if global_projectiles is not None:
                spread = 0.1
                mx, my, mz = nx + random.uniform(-spread, spread), ny + random.uniform(-spread, spread), nz + random.uniform(-spread, spread)
                global_projectiles.append(MachineGunBolt(self.x, self.y, self.z, mx * 8000, my * 8000, mz * 8000))

        # --- SPAWNING ---
        if self.spawn_timer <= 0 and dist < 15000:
            self.spawn_timer = 6.0
            if global_enemies is not None:
                # 70% Drone, 30% Dogfighter
                if random.random() < 0.7:
                    new_e = SuicideDrone(self.x - self.up[0]*150, self.y - self.up[1]*150, self.z - self.up[2]*150)
                    new_e.vx, new_e.vy, new_e.vz = self.vx, self.vy - 500, self.vz
                    new_e.set_pattern(random.choice(['spiral', 'corkscrew', 'zigzag']))
                else:
                    new_e = Dogfighter(self.x + self.right[0]*150, self.y + self.right[1]*150, self.z + self.right[2]*150)
                    new_e.vx, new_e.vy, new_e.vz = self.vx + 200, self.vy, self.vz
                global_enemies.append(new_e)

        self._spawn_engine_trail()
        self._update_engine_trail(dt)
        if self._flicker > 0: self._flicker -= dt * 8

    def on_hit(self, damage=1):
        self.hp -= damage
        self._flicker = 1


