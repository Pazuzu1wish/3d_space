import math
import random
import pygame

from src.math_engine import (
    world_to_camera,
    project_to_screen,
    basis_from_forward,
    get_forward_from_quat,
)
from src.constants import MG_COOLDOWN, WEAPON_SPREAD, TRAIL_LIFE_DIVISOR
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

    def _update_orientation(self):
        spd = math.sqrt(self.vx ** 2 + self.vy ** 2 + self.vz ** 2)
        if spd > 1e-3:
            self.forward, self.right, self.up = basis_from_forward(
                (self.vx, self.vy, self.vz)
            )

    def _spawn_engine_trail(self):
        # Spawn a trail particle for every engine hardpoint
        for ox, oy, oz in self.engine_offsets:
            ex = self.x + self.right[0] * ox + self.up[0] * oy + self.forward[0] * oz
            ey = self.y + self.right[1] * ox + self.up[1] * oy + self.forward[1] * oz
            ez = self.z + self.right[2] * ox + self.up[2] * oy + self.forward[2] * oz

            self.engine_trail.append([ex, ey, ez, self.trail_life, self.engine_color, self.engine_size])

    def _update_engine_trail(self, dt):
        for p in self.engine_trail:
            p[3] -= dt
        self.engine_trail = [p for p in self.engine_trail if p[3] > 0]

    def _submit_engine_trail(self, renderer):
        for x, y, z, life, color, base_size in self.engine_trail:
            ratio = max(0.0, life / (self.trail_life or TRAIL_LIFE_DIVISOR))
            # Fade color out as it dies
            r = min(255, max(0, int(color[0] * ratio)))
            g = min(255, max(0, int(color[1] * ratio)))
            b = min(255, max(0, int(color[2] * ratio)))

            renderer.submit_sprite(x, y, z, (r, g, b), base_size * 4 * ratio)

    def _submit_engine_glow(self, renderer):
        for ox, oy, oz in self.engine_offsets:
            ex = self.x + self.right[0] * ox + self.up[0] * oy + self.forward[0] * oz
            ey = self.y + self.right[1] * ox + self.up[1] * oy + self.forward[1] * oz
            ez = self.z + self.right[2] * ox + self.up[2] * oy + self.forward[2] * oz

            renderer.submit_sprite(ex, ey, ez, (255, 255, 255), self.engine_size * 2, is_glow=True)

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

        world_verts = {}
        for v_id, (vx, vy, vz) in self.verts.items():
            wx = self.x + vx * self.right[0] + vy * self.up[0] + vz * self.forward[0]
            wy = self.y + vx * self.right[1] + vy * self.up[1] + vz * self.forward[1]
            wz = self.z + vx * self.right[2] + vy * self.up[2] + vz * self.forward[2]
            world_verts[v_id] = (wx, wy, wz)

        for f in self.faces:
            pts = tuple(world_verts[vid] for vid in f['v'])
            renderer.submit_polygon(pts, f.get('color', self.base_color))


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
    SPEED = 1400

    def __init__(self, x, y, z):
        super().__init__(x, y, z)
        self.hp = 1
        self.max_hp = 1
        self.base_color = (255, 30, 30)

        # Single bright red thruster
        self.engine_offsets = [(0, 0, -20)]
        self.engine_color = (255, 100, 50)
        self.engine_size = 5.0
        self.trail_life = 0.4

        self.t = 0
        self.pattern = _pattern_weave
        self.pattern_phase = random.uniform(0, math.pi * 2)
        self._pattern_cache = None
        self._pattern_check_timer = 0.0
        self._flicker = 0

        # Jagged, aggressive spike shape
        self.verts = {
                    'v0': (0, 0, 50),  # 0: Nose
                    'v1': (-15, -10, -20),  # 1: Bottom left
                    'v2': (15, -10, -20),  # 2: Bottom right
                    'v3': (0, 20, -20),  # 3: Top fin
                    'v4': (0, 0, -30),  # 4: Engine block
                }
        self.faces = [
                    {'v': ['v0', 'v3', 'v1']}, {'v': ['v0', 'v2', 'v3']}, {'v': ['v0', 'v1', 'v2']},  # Front spikes
                    {'v': ['v1', 'v3', 'v4']}, {'v': ['v3', 'v2', 'v4']}, {'v': ['v2', 'v1', 'v4']},  # Back tapers
                ]

    def set_pattern(self, pattern_name):
        if pattern_name in PATTERN_MAP:
            self.pattern = PATTERN_MAP[pattern_name]

    def update(self, dt, player_pos, player_orientation, global_projectiles=None, global_enemies=None):
        self.t += dt
        self._pattern_check_timer += dt

        px, py, pz = player_pos
        dx, dy, dz = px - self.x, py - self.y, pz - self.z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1
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

        offset = active_pattern(self.t, self.pattern_phase, self.SPEED)
        target_v = (
            nx * self.SPEED + offset[0],
            ny * self.SPEED + offset[1],
            nz * self.SPEED + offset[2],
        )

        self._apply_banking(target_v, dt)

        blend = min(1, dt * 6)
        self.vx += (target_v[0] - self.vx) * blend
        self.vy += (target_v[1] - self.vy) * blend
        self.vz += (target_v[2] - self.vz) * blend

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt

        self._update_orientation()
        self._spawn_engine_trail()
        self._update_engine_trail(dt)

        if self._flicker > 0:
            self._flicker -= dt * 8

    def on_hit(self):
        self.hp -= 1
        self._flicker = 1
        if self._pattern_cache is _pattern_direct:
            self._pattern_cache = random.choice(PATTERNS[1:])


# ──────────────────────────────────────────────
#  DOGFIGHTER
# ──────────────────────────────────────────────

class Dogfighter(Enemy):
    SPEED = 1400
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
        self.engine_color = (100, 200, 255)
        self.engine_size = 4.5
        self.trail_life = 0.6
        self.hit_radius = 70

        self.mg_timer = 0.0
        self.bolt_timer = random.uniform(2.0, 5.0)

        self.mode = 'positioning'
        self.mode_timer = random.uniform(2.0, 4.0)
        self.phase = random.uniform(0, math.pi * 2)
        self._flicker = 0

        self.verts = {
                    'v0': (0, 8, 105),  # 0: nose top
                    'v1': (0, -8, 105),  # 1: nose bot
                    'v2': (-30, 12, 30),  # 2: mid top L
                    'v3': (30, 12, 30),  # 3: mid top R
                    'v4': (-30, -12, 30),  # 4: mid bot L
                    'v5': (30, -12, 30),  # 5: mid bot R
                    'v6': (-120, -8, -30),  # 6: tip L
                    'v7': (120, -8, -30),  # 7: tip R
                    'v8': (-22, 10, -60),  # 8: tail top L
                    'v9': (22, 10, -60),  # 9: tail top R
                    'v10': (-22, -10, -60),  # 10: tail bot L
                    'v11': (22, -10, -60),  # 11: tail bot R
                    'v12': (0, 18, 60),  # 12: cockpit ridge
                    'v13': (-65, -6, -55),  # 13: inner trail L
                    'v14': (65, -6, -55),  # 14: inner trail R
                }
        self.faces = [
                    {'v': ['v0', 'v12', 'v2']},  # 0  nose→ridge→mid-top-L
                    {'v': ['v0', 'v3', 'v12']},  # 1  nose→mid-top-R→ridge
                    {'v': ['v1', 'v0', 'v4']},  # 2  belly: nose-bot→nose-top→mid-bot-L
                    {'v': ['v1', 'v5', 'v0']},  # 3  belly: nose-bot→mid-bot-R→nose-top
                    {'v': ['v1', 'v4', 'v5']},  # 4  belly cap
                    {'v': ['v12', 'v8', 'v2']},  # 5  ridge→tail-top-L→mid-top-L
                    {'v': ['v12', 'v9', 'v8']},  # 6  ridge→tail-top-R→tail-top-L
                    {'v': ['v12', 'v3', 'v9']},  # 7  ridge→mid-top-R→tail-top-R
                    {'v': ['v2', 'v8', 'v13']},  # 8  mid-top-L→tail-top-L→inner-trail-L
                    {'v': ['v3', 'v14', 'v9']},  # 9  mid-top-R→inner-trail-R→tail-top-R
                    {'v': ['v4', 'v13', 'v10']},  # 10 mid-bot-L→inner-trail-L→tail-bot-L
                    {'v': ['v5', 'v11', 'v14']},  # 11 mid-bot-R→tail-bot-R→inner-trail-R
                    {'v': ['v4', 'v10', 'v5']},  # 12 belly: mid-bot-L→tail-bot-L→mid-bot-R
                    {'v': ['v5', 'v10', 'v11']},  # 13 belly: mid-bot-R→tail-bot-L→tail-bot-R
                    {'v': ['v2', 'v13', 'v6']},  # 14 wing upper L
                    {'v': ['v3', 'v7', 'v14']},  # 15 wing upper R
                    {'v': ['v4', 'v6', 'v13']},  # 16 wing lower L
                    {'v': ['v5', 'v14', 'v7']},  # 17 wing lower R
                    {'v': ['v0', 'v2', 'v6']},  # 18 leading edge upper L
                    {'v': ['v0', 'v7', 'v3']},  # 19 leading edge upper R
                    {'v': ['v0', 'v6', 'v4']},  # 20 leading edge lower L
                    {'v': ['v0', 'v5', 'v7']},  # 21 leading edge lower R
                    {'v': ['v8', 'v11', 'v10']},  # 22 tail cap
                    {'v': ['v8', 'v9', 'v11']},  # 23 tail cap
                    {'v': ['v13', 'v8', 'v10']},  # 24 inner-trail-L→tail
                    {'v': ['v14', 'v11', 'v9']},  # 25 inner-trail-R→tail
                ]



    def _player_forward(self, orientation):
        return get_forward_from_quat(orientation)

    def update(self, dt, player_pos, player_orientation, global_projectiles=None, global_enemies=None):
        self.t += dt
        self.mg_timer -= dt
        self.bolt_timer -= dt
        self.mode_timer -= dt

        px, py, pz = player_pos

        if self.mode_timer <= 0:
            if self.mode == 'positioning':
                self.mode = 'attack_run'
                self.mode_timer = random.uniform(2.0, 4.0)
            else:
                self.mode = 'positioning'
                self.mode_timer = random.uniform(3.0, 5.0)
                self.phase = random.uniform(0, math.pi * 2)

        if self.mode == 'positioning':
            pfw = self._player_forward(player_orientation)
            behind_x = px - pfw[0] * self.IDEAL_RANGE
            behind_y = py - pfw[1] * self.IDEAL_RANGE
            behind_z = pz - pfw[2] * self.IDEAL_RANGE

            offset_x = math.sin(self.t * 0.8 + self.phase) * self.CIRCLE_RADIUS
            offset_y = math.cos(self.t * 0.6 + self.phase) * self.CIRCLE_RADIUS * 0.4
            offset_z = math.sin(self.t * 0.5 + self.phase) * self.CIRCLE_RADIUS * 0.3

            target_x = behind_x + offset_x
            target_y = behind_y + offset_y
            target_z = behind_z + offset_z
        else:
            target_x, target_y, target_z = px, py, pz

        dx = target_x - self.x
        dy = target_y - self.y
        dz = target_z - self.z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0

        nx, ny, nz = dx / dist, dy / dist, dz / dist
        target_v = (nx * self.SPEED, ny * self.SPEED, nz * self.SPEED)

        self._apply_banking(target_v, dt)
        blend = min(1.0, dt * 4.0)
        self.vx += (target_v[0] - self.vx) * blend
        self.vy += (target_v[1] - self.vy) * blend
        self.vz += (target_v[2] - self.vz) * blend

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt

        self._update_orientation()

        to_px, to_py, to_pz = px - self.x, py - self.y, pz - self.z
        dist_to_player = math.sqrt(to_px ** 2 + to_py ** 2 + to_pz ** 2) or 1.0

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

    def on_hit(self):
        self.hp -= 1
        self._flicker = 1
        self.mode = 'attack_run'
        self.mode_timer = 3.0


# ===========================================================
# Sniper
# ===========================================================

class Sniper(Enemy):
    SPEED = 1200
    FIRE_RANGE = 7000
    FLEE_RANGE = 3500

    def __init__(self, x, y, z):
        super().__init__(x, y, z)

        self.hp = 2
        self.max_hp = 2
        self.base_color = (150, 255, 100)

        # Single deep green thruster at back of long barrel
        self.engine_offsets = [(0, 0, -90)]
        self.engine_color = (255, 0, 50)
        self.engine_size = 6.0
        self.trail_life = 0.8

        self.hit_radius = 70

        self.state = 'aiming'
        self.timer = random.uniform(2.0, 4.0)
        self._flicker = 0

        # Symmetrical, needle-like railgun ship
        self.verts = {
                    'v0': (0, 0, 150),  # 0: nose tip
                    'v1': (-8, 0, 40),  # 1: barrel L
                    'v2': (8, 0, 40),  # 2: barrel R
                    'v3': (0, 8, 40),  # 3: barrel top
                    'v4': (0, -8, 40),  # 4: barrel bot
                    'v5': (-18, 12, 0),  # 5: shoulder TL
                    'v6': (18, 12, 0),  # 6: shoulder TR
                    'v7': (-18, -12, 0),  # 7: shoulder BL
                    'v8': (18, -12, 0),  # 8: shoulder BR
                    'v9': (-22, 16, -60),  # 9: rear TL
                    'v10': (22, 16, -60),  # 10: rear TR
                    'v11': (-22, -16, -60),  # 11: rear BL
                    'v12': (22, -16, -60),  # 12: rear BR
                    'v13': (-10, 8, -90),  # 13: tail TL
                    'v14': (10, 8, -90),  # 14: tail TR
                    'v15': (-10, -8, -90),  # 15: tail BL
                    'v16': (10, -8, -90),  # 16: tail BR
                }
        self.faces = [
                    {'v': ['v0', 'v2', 'v3']},  # 0  needle right
                    {'v': ['v0', 'v4', 'v2']},  # 1  needle right-bot
                    {'v': ['v0', 'v3', 'v1']},  # 2  needle left
                    {'v': ['v0', 'v1', 'v4']},  # 3  needle left-bot
                    {'v': ['v3', 'v6', 'v5']},  # 4  barrel→shoulder top
                    {'v': ['v3', 'v5', 'v1']},  # 5  barrel→shoulder top-L
                    {'v': ['v1', 'v5', 'v7']},  # 6  barrel→shoulder left
                    {'v': ['v1', 'v7', 'v4']},  # 7  barrel→shoulder left-bot
                    {'v': ['v4', 'v7', 'v8']},  # 8  barrel→shoulder bot
                    {'v': ['v4', 'v8', 'v2']},  # 9  barrel→shoulder bot-R
                    {'v': ['v2', 'v8', 'v6']},  # 10  barrel→shoulder right
                    {'v': ['v2', 'v6', 'v3']},  # 11  barrel→shoulder right-top
                    {'v': ['v5', 'v10', 'v9']},  # 12  shoulder→rear top
                    {'v': ['v5', 'v6', 'v10']},  # 13  shoulder→rear top-R
                    {'v': ['v5', 'v9', 'v11']},  # 14  shoulder→rear left
                    {'v': ['v5', 'v11', 'v7']},  # 15  shoulder→rear left-bot
                    {'v': ['v6', 'v12', 'v10']},  # 16  shoulder→rear right
                    {'v': ['v6', 'v8', 'v12']},  # 17  shoulder→rear right-bot
                    {'v': ['v7', 'v11', 'v12']},  # 18  shoulder→rear bot
                    {'v': ['v7', 'v12', 'v8']},  # 19  shoulder→rear bot-R
                    {'v': ['v9', 'v14', 'v13']},  # 20  rear→tail top
                    {'v': ['v9', 'v10', 'v14']},  # 21  rear→tail top-R
                    {'v': ['v9', 'v13', 'v15']},  # 22  rear→tail left
                    {'v': ['v9', 'v15', 'v11']},  # 23  rear→tail left-bot
                    {'v': ['v10', 'v16', 'v14']},  # 24  rear→tail right
                    {'v': ['v10', 'v12', 'v16']},  # 25  rear→tail right-bot
                    {'v': ['v11', 'v15', 'v16']},  # 26  rear→tail bot
                    {'v': ['v11', 'v16', 'v12']},  # 27  rear→tail bot-R
                    {'v': ['v13', 'v16', 'v15']},  # 28  tail cap
                    {'v': ['v13', 'v14', 'v16']},  # 29  tail cap
                ]

    def update(self, dt, player_pos, player_orientation, global_projectiles=None, global_enemies=None):
        self.timer -= dt
        px, py, pz = player_pos

        dx, dy, dz = px - self.x, py - self.y, pz - self.z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        nx, ny, nz = dx / dist, dy / dist, dz / dist

        if dist < self.FLEE_RANGE:
            self.state = 'fleeing'
            self.base_color = (255, 255, 255)
        elif self.state == 'fleeing' and dist > self.FLEE_RANGE + 1000:
            self.state = 'aiming'
            self.timer = 2.0

        if self.state == 'aiming' and self.timer <= 0:
            self.state = 'charging'
            self.timer = 1.5

        if self.state == 'charging':
            flash = int((math.sin(self.timer * 20) + 1) * 127)
            self.base_color = (255, flash, flash)

            if self.timer <= 0:
                if global_projectiles is not None:
                    global_projectiles.append(SniperBeam(
                        self.x, self.y, self.z,
                        nx * 32000, ny * 32000, nz * 32000
                    ))
                self.state = 'aiming'
                self.timer = random.uniform(4.0, 6.0)
                self.base_color = (150, 255, 100)

        if self.state == 'fleeing':
            target_v = (-nx * self.SPEED, -ny * self.SPEED, -nz * self.SPEED)
        elif self.state == 'aiming':
            target_v = (self.right[0] * 300, self.right[1] * 300, self.right[2] * 300)
        elif self.state == 'charging':
            target_v = (0, 0, 0)

        self.forward = (nx, ny, nz)
        temp_up = (0, 1, 0) if abs(ny) < 0.99 else (1, 0, 0)
        rx = ny * temp_up[2] - nz * temp_up[1]
        ry = nz * temp_up[0] - nx * temp_up[2]
        rz = nx * temp_up[1] - ny * temp_up[0]
        rlen = math.sqrt(rx * rx + ry * ry + rz * rz) or 1
        self.right = (rx / rlen, ry / rlen, rz / rlen)

        self.up = (
            self.right[1] * nz - self.right[2] * ny,
            self.right[2] * nx - self.right[0] * nz,
            self.right[0] * ny - self.right[1] * nx
        )

        blend = min(1.0, dt * 3.0)
        self.vx += (target_v[0] - self.vx) * blend
        self.vy += (target_v[1] - self.vy) * blend
        self.vz += (target_v[2] - self.vz) * blend

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt

        self._spawn_engine_trail()
        self._update_engine_trail(dt)

    def on_hit(self):
        self.hp -= 1


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
        self.engine_color = (255, 120, 40)
        self.engine_size = 12.0
        self.trail_life = 1.0

        self.turret_timer = 0.0
        self._flicker = 0
        self.t = random.uniform(0, 100)

        self.verts = {
                    # --- Forward pod ---
                    'v0': (0, 20, 250),  # 0  nose top      (windshield top edge, set back)
                    'v1': (0, -25, 270),  # 1  nose chin     (windshield bot edge, juts forward+down)
                    'v2': (-40, 20, 180),  # 2  pod top-left
                    'v3': (40, 20, 180),  # 3  pod top-right
                    'v4': (-40, -15, 180),  # 4  pod bot-left
                    'v5': (40, -15, 180),  # 5  pod bot-right
                    # --- Central spine ---
                    'v6': (-15, 8, 80),  # 6  spine front top-left
                    'v7': (15, 8, 80),  # 7  spine front top-right
                    'v8': (-15, -8, 80),  # 8  spine front bot-left
                    'v9': (15, -8, 80),  # 9  spine front bot-right
                    'v10': (-15, 8, -200),  # 10 spine rear top-left
                    'v11': (15, 8, -200),  # 11 spine rear top-right
                    'v12': (-15, -8, -200),  # 12 spine rear bot-left
                    'v13': (15, -8, -200),  # 13 spine rear bot-right
                    # --- Left nacelle (sits below spine, offset -x) ---
                    'v14': (-40, -5, 80),  # 14 nacelle-L front top-inner
                    'v15': (-90, -5, 80),  # 15 nacelle-L front top-outer
                    'v16': (-40, -20, 80),  # 16 nacelle-L front bot-inner
                    'v17': (-90, -20, 80),  # 17 nacelle-L front bot-outer
                    'v18': (-40, -5, -180),  # 18 nacelle-L rear top-inner
                    'v19': (-90, -5, -180),  # 19 nacelle-L rear top-outer
                    'v20': (-40, -20, -180),  # 20 nacelle-L rear bot-inner
                    'v21': (-90, -20, -180),  # 21 nacelle-L rear bot-outer
                    # --- Right nacelle (mirror of left) ---
                    'v22': (40, -5, 80),  # 22 nacelle-R front top-inner
                    'v23': (90, -5, 80),  # 23 nacelle-R front top-outer
                    'v24': (40, -20, 80),  # 24 nacelle-R front bot-inner
                    'v25': (90, -20, 80),  # 25 nacelle-R front bot-outer
                    'v26': (40, -5, -180),  # 26 nacelle-R rear top-inner
                    'v27': (90, -5, -180),  # 27 nacelle-R rear top-outer
                    'v28': (40, -20, -180),  # 28 nacelle-R rear bot-inner
                    'v29': (90, -20, -180),  # 29 nacelle-R rear bot-outer
                }
        self.faces = [
                    {'v': ['v0', 'v1', 'v5']},  # 0 OK
                    {'v': ['v0', 'v4', 'v1']},  # 1 OK
                    {'v': ['v0', 'v3', 'v2']},  # 2 OK
                    {'v': ['v0', 'v2', 'v4']},  # 3 OK
                    {'v': ['v0', 'v5', 'v3']},  # 4 OK
                    {'v': ['v1', 'v5', 'v4']},  # 5 OK
                    {'v': ['v2', 'v5', 'v3']},  # 6 OK
                    {'v': ['v2', 'v4', 'v5']},  # 7 OK
                    {'v': ['v2', 'v7', 'v6']},  # 8 OK
                    {'v': ['v2', 'v3', 'v7']},  # 9 OK
                    {'v': ['v4', 'v9', 'v8']},  # 10 OK
                    {'v': ['v4', 'v5', 'v9']},  # 11 OK
                    {'v': ['v6', 'v7', 'v11']},  # 12 OK
                    {'v': ['v6', 'v11', 'v10']},  # 13 OK
                    {'v': ['v8', 'v13', 'v9']},  # 14 OK
                    {'v': ['v8', 'v12', 'v13']},  # 15 OK
                    {'v': ['v6', 'v10', 'v12']},  # 16 OK
                    {'v': ['v6', 'v12', 'v8']},  # 17 OK
                    {'v': ['v7', 'v9', 'v13']},  # 18 OK
                    {'v': ['v7', 'v13', 'v11']},  # 19 OK
                    {'v': ['v10', 'v11', 'v13']},  # 20 OK
                    {'v': ['v10', 'v13', 'v12']},  # 21 OK
                    {'v': ['v14', 'v15', 'v17']},  # 22 OK
                    {'v': ['v14', 'v17', 'v16']},  # 23 OK
                    {'v': ['v18', 'v20', 'v21']},  # 24 OK
                    {'v': ['v18', 'v21', 'v19']},  # 25 OK
                    {'v': ['v15', 'v19', 'v21']},  # 26 OK
                    {'v': ['v15', 'v21', 'v17']},  # 27 OK
                    {'v': ['v14', 'v20', 'v16']},  # 28 OK
                    {'v': ['v14', 'v18', 'v20']},  # 29 OK
                    {'v': ['v14', 'v19', 'v15']},  # 30 OK
                    {'v': ['v14', 'v18', 'v19']},  # 31 OK
                    {'v': ['v16', 'v17', 'v21']},  # 32 OK
                    {'v': ['v16', 'v21', 'v20']},  # 33 OK
                    {'v': ['v22', 'v25', 'v23']},  # 34 OK
                    {'v': ['v22', 'v24', 'v25']},  # 35 OK
                    {'v': ['v26', 'v29', 'v28']},  # 36 OK
                    {'v': ['v26', 'v27', 'v29']},  # 37 OK
                    {'v': ['v23', 'v25', 'v29']},  # 38 OK
                    {'v': ['v23', 'v29', 'v27']},  # 39 OK
                    {'v': ['v22', 'v28', 'v26']},  # 40 OK
                    {'v': ['v22', 'v24', 'v28']},  # 41 OK
                    {'v': ['v22', 'v23', 'v27']},  # 42 OK
                    {'v': ['v22', 'v27', 'v26']},  # 43 OK
                    {'v': ['v24', 'v29', 'v25']},  # 44 OK
                    {'v': ['v24', 'v28', 'v29']},  # 45 OK
                ]
    def update(self, dt, player_pos, player_orientation, global_projectiles=None, global_enemies=None):
        self.t += dt
        self.turret_timer -= dt

        px, py, pz = player_pos
        dx, dy, dz = px - self.x, py - self.y, pz - self.z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        nx, ny, nz = dx / dist, dy / dist, dz / dist

        target_v = (nx * self.SPEED, ny * self.SPEED, nz * self.SPEED)

        self._apply_banking(target_v, dt)
        blend = min(1.0, dt * 1.5)
        self.vx += (target_v[0] - self.vx) * blend
        self.vy += (target_v[1] - self.vy) * blend
        self.vz += (target_v[2] - self.vz) * blend

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self._update_orientation()

        if dist < self.FIRE_RANGE and self.turret_timer <= 0:
            self.turret_timer = 0.3
            if global_projectiles is not None:
                spread = 0.05
                ax = nx + random.uniform(-spread, spread)
                ay = ny + random.uniform(-spread, spread)
                az = nz + random.uniform(-spread, spread)
                n = math.sqrt(ax * ax + ay * ay + az * az) or 1
                ax, ay, az = ax / n, ay / n, az / n

                global_projectiles.append(CorvetteTurret(
                    self.x, self.y, self.z,
                    ax * 4000 + self.vx * 0.5,
                    ay * 4000 + self.vy * 0.5,
                    az * 4000 + self.vz * 0.5
                ))

        self._spawn_engine_trail()
        self._update_engine_trail(dt)
        if self._flicker > 0: self._flicker -= dt * 8

    def on_hit(self):
        self.hp -= 1
        self._flicker = 1


# =============================================================
# Minelayer
# =============================================================

class Minelayer(Enemy):
    SPEED = 1400

    def __init__(self, x, y, z):
        super().__init__(x, y, z)
        self.hp = 6
        self.max_hp = 6
        self.base_color = (255, 140, 0)

        self.hit_radius = 200

        # 4 spaced out thrusters
        self.engine_offsets = [
            (-60, 0, -30), (-20, 0, -30),
            (20, 0, -30), (60, 0, -30)
        ]
        self.engine_color = (255, 140, 0)
        self.engine_size = 5.0
        self.trail_life = 0.5

        self.mine_timer = 3.0
        self._flicker = 0

        # Wide, flat wing shape
        self.verts = {
                    'v0': (0, 0, 40),  # 0: Center Nose
                    'v1': (-80, -5, -10),  # 1: Far Left
                    'v2': (80, -5, -10),  # 2: Far Right
                    'v3': (-30, 15, -20),  # 3: Mid Left Bulk
                    'v4': (30, 15, -20),  # 4: Mid Right Bulk
                    'v5': (0, -15, -30),  # 5: Underbelly
                }
        self.faces = [
                    {'v': ['v0', 'v3', 'v1']}, {'v': ['v0', 'v2', 'v4']}, {'v': ['v0', 'v4', 'v3']},  # Top layer
                    {'v': ['v0', 'v1', 'v5']}, {'v': ['v0', 'v5', 'v2']}, {'v': ['v1', 'v3', 'v5']}, {'v': ['v2', 'v5', 'v4']},  # Bottom/Side bulk
                    {'v': ['v3', 'v4', 'v5']},  # Back seal
                ]

        self.cross_vector = (random.choice([-1, 1]), random.uniform(-0.5, 0.5), 0)

    def update(self, dt, player_pos, player_orientation, global_projectiles=None, global_enemies=None):
        self.mine_timer -= dt

        px, py, pz = player_pos
        dx, dy, dz = px - self.x, py - self.y, pz - self.z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0

        target_v = (
            self.cross_vector[0] * self.SPEED,
            self.cross_vector[1] * self.SPEED,
            (dz / dist) * self.SPEED * 0.5
        )

        self._apply_banking(target_v, dt)
        blend = min(1.0, dt * 2.0)
        self.vx += (target_v[0] - self.vx) * blend
        self.vy += (target_v[1] - self.vy) * blend
        self.vz += (target_v[2] - self.vz) * blend

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self._update_orientation()

        if self.mine_timer <= 0 and dist < 6000:
            self.mine_timer = 2.0
            if global_projectiles is not None:
                global_projectiles.append(Mine(
                    self.x, self.y, self.z, 0, 0, 0
                ))

        self._spawn_engine_trail()
        self._update_engine_trail(dt)
        if self._flicker > 0: self._flicker -= dt * 8

    def on_hit(self):
        self.hp -= 1
        self._flicker = 1
        self.cross_vector = (random.choice([-1, 1]), random.uniform(-1, 1), 0)


# =============================================================
# Stealth Interceptor
# =============================================================

class StealthInterceptor(Enemy):
    SPEED = 2500
    DECLOAK_RANGE = 1800

    def __init__(self, x, y, z):
        super().__init__(x, y, z)
        self.hp = 2
        self.max_hp = 2
        self.base_color = (20, 20, 30)

        # Twin thin thrusters
        self.engine_offsets = [(-10, 2, -30), (10, 2, -30)]
        self.engine_color = (100, 100, 255)
        self.engine_size = 4.0
        self.trail_life = 0.3

        self.stealthed = True
        self.state = 'flanking'
        self.shotgun_timer = 0.5
        self._flicker = 0

        # Extremely thin, planar dart
        self.verts = {
                    'v0': (0, 0, 60),  # 0: Needle point
                    'v1': (-25, 0, -30),  # 1: Left Wing
                    'v2': (25, 0, -30),  # 2: Right Wing
                    'v3': (0, 5, -20),  # 3: Top ridge
                    'v4': (0, -5, -20),  # 4: Bottom ridge
                }
        self.faces = [
                    {'v': ['v0', 'v3', 'v1']},  # 0 OK
                    {'v': ['v0', 'v2', 'v3']},  # 1 OK
                    {'v': ['v0', 'v1', 'v4']},  # 2 OK
                    {'v': ['v0', 'v4', 'v2']},  # 3 OK
                    {'v': ['v1', 'v3', 'v2']},  # 4 OK
                    {'v': ['v1', 'v2', 'v4']},  # 5 OK
                ]

    def update(self, dt, player_pos, player_orientation, global_projectiles=None, global_enemies=None):
        px, py, pz = player_pos
        dx, dy, dz = px - self.x, py - self.y, pz - self.z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        nx, ny, nz = dx / dist, dy / dist, dz / dist

        if self.state == 'flanking':
            self.stealthed = True
            self.base_color = (20, 20, 30)

            pfw = get_forward_from_quat(player_orientation)
            target_x = px + pfw[2] * 1000
            target_y = py + 500
            target_z = pz - pfw[0] * 1000

            if dist < self.DECLOAK_RANGE:
                self.state = 'attacking'
                self.stealthed = False
                self.base_color = (100, 100, 255)
                self.shotgun_timer = 0.5

        elif self.state == 'attacking':
            target_x, target_y, target_z = px, py, pz
            self.shotgun_timer -= dt

            if self.shotgun_timer <= 0:
                if global_projectiles is not None:
                    for _ in range(7):
                        spread = WEAPON_SPREAD
                        ax, ay, az = nx + random.uniform(-spread, spread), ny + random.uniform(-spread,
                                                                                               spread), nz + random.uniform(
                            -spread, spread)
                        global_projectiles.append(StealthShotgun(
                            self.x, self.y, self.z,
                            ax * 3000, ay * 3000, az * 3000
                        ))
                self.state = 'fleeing'

        elif self.state == 'fleeing':
            target_x, target_y, target_z = px - nx * 4000, py - ny * 4000, pz - nz * 4000
            if dist > 3500:
                self.state = 'flanking'

        tdx, tdy, tdz = target_x - self.x, target_y - self.y, target_z - self.z
        tdist = math.sqrt(tdx * tdx + tdy * tdy + tdz * tdz) or 1
        target_v = ((tdx / tdist) * self.SPEED, (tdy / tdist) * self.SPEED, (tdz / tdist) * self.SPEED)

        self._apply_banking(target_v, dt)
        blend = min(1.0, dt * 5.0)
        self.vx += (target_v[0] - self.vx) * blend
        self.vy += (target_v[1] - self.vy) * blend
        self.vz += (target_v[2] - self.vz) * blend

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self._update_orientation()

        # Engine trails only drawn when uncloaked
        if not self.stealthed:
            self.engine_size = 6.0
            self._spawn_engine_trail()
        else:
            self.engine_size = 0.0

        self._update_engine_trail(dt)
        if self._flicker > 0: self._flicker -= dt * 8

    def on_hit(self):
        self.hp -= 1
        self._flicker = 1


# =============================================================
# Carrier
# =============================================================

class Carrier(Enemy):
    SPEED = 200

    def __init__(self, x, y, z):
        super().__init__(x, y, z)
        self.hp = 50
        self.max_hp = 50
        self.base_color = (120, 100, 150)

        # --- ADD THIS: Tell the spatial partition this enemy is HUGE ---
        self.hit_radius = 800.0

        # Massive thruster bank (1 Huge center, 4 large satellites)
        self.engine_offsets = [
            (0, -30, -500),  # Center Main Drive
            (-120, 0, -500), (120, 0, -500),  # Outer Drives
            (-60, -40, -500), (60, -40, -500)  # Lower Drives
        ]
        self.engine_color = (200, 100, 255)
        self.engine_size = 25.0
        self.trail_life = 1.2

        self.spawn_timer = 4.0
        self._flicker = 0

        # Gigantic Dreadnought/Carrier Wedge shape
        self.verts = {
                    'v0': (0, -20, 800),  # 0: Ultimate Nose
                    'v1': (0, 80, -200),  # 1: Command Ridge Top Front
                    'v2': (0, 180, -450),  # 2: Command Tower High
                    'v3': (-400, -20, -500),  # 3: Far Wingtip L
                    'v4': (400, -20, -500),  # 4: Far Wingtip R
                    'v5': (-150, 60, -500),  # 5: Back Top L
                    'v6': (150, 60, -500),  # 6: Back Top R
                    'v7': (-150, -80, -500),  # 7: Back Bot L
                    'v8': (150, -80, -500),  # 8: Back Bot R
                    'v9': (0, -120, -100),  # 9: Deep Belly
                }
        self.faces = [
                    {'v': ['v0', 'v5', 'v3']},  # 0 OK
                    {'v': ['v0', 'v1', 'v5']},  # 1 OK
                    {'v': ['v0', 'v6', 'v1']},  # 2 OK
                    {'v': ['v0', 'v4', 'v6']},  # 3 OK
                    {'v': ['v1', 'v2', 'v5']},  # 4 OK
                    {'v': ['v1', 'v6', 'v2']},  # 5 OK
                    {'v': ['v5', 'v2', 'v6']},  # 6 OK
                    {'v': ['v0', 'v3', 'v7']},  # 7 OK
                    {'v': ['v0', 'v7', 'v9']},  # 8 OK
                    {'v': ['v0', 'v9', 'v8']},  # 9 OK
                    {'v': ['v0', 'v8', 'v4']},  # 10 OK
                    {'v': ['v5', 'v7', 'v3']},  # 11 OK
                    {'v': ['v6', 'v4', 'v8']},  # 12 OK
                    {'v': ['v5', 'v8', 'v7']},  # 13 OK
                    {'v': ['v5', 'v6', 'v8']},  # 14 OK
                ]
    # --- ADD THIS: Perfect Box Collision for the giant wedge ---
    def is_hit(self, px, py, pz):
        """Check if a projectile at (px, py, pz) hits the Carrier using a perfect 3D bounding box."""
        # Distance vector from center of Carrier to the projectile
        dx, dy, dz = px - self.x, py - self.y, pz - self.z

        # Project the projectile into the Carrier's LOCAL rotation space
        local_x = dx * self.right[0]   + dy * self.right[1]   + dz * self.right[2]
        local_y = dx * self.up[0]      + dy * self.up[1]      + dz * self.up[2]
        local_z = dx * self.forward[0] + dy * self.forward[1] + dz * self.forward[2]

        # Check if the local coordinates fall inside a box matching self.verts
        hit_x = -400 <= local_x <= 400   # Wingtips
        hit_y = -120 <= local_y <= 180   # Belly to Tower
        hit_z = -500 <= local_z <= 800   # Engine to Nose

        return hit_x and hit_y and hit_z

    def update(self, dt, player_pos, player_orientation, global_projectiles=None, global_enemies=None):
        self.spawn_timer -= dt

        px, py, pz = player_pos
        dx, dy, dz = px - self.x, py - self.y, pz - self.z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        nx, ny, nz = dx / dist, dy / dist, dz / dist

        if dist < 7000:
            target_v = (-nx * self.SPEED, -ny * self.SPEED, -nz * self.SPEED)
        elif dist > 9000:
            target_v = (nx * self.SPEED, ny * self.SPEED, nz * self.SPEED)
        else:
            target_v = (0, 0, 0)

        self._apply_banking(target_v, dt)
        blend = min(1.0, dt * 0.5)
        self.vx += (target_v[0] - self.vx) * blend
        self.vy += (target_v[1] - self.vy) * blend
        self.vz += (target_v[2] - self.vz) * blend

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self._update_orientation()

        if self.spawn_timer <= 0 and dist < 12000:
            self.spawn_timer = 5.0

            if global_enemies is not None:
                drone = SuicideDrone(
                    self.x - self.up[0] * 150,  # Drop out of bottom belly
                    self.y - self.up[1] * 150,
                    self.z - self.up[2] * 150
                )
                drone.vx = self.vx
                drone.vy = self.vy - 500
                drone.vz = self.vz
                global_enemies.append(drone)

        self._spawn_engine_trail()
        self._update_engine_trail(dt)
        if self._flicker > 0: self._flicker -= dt * 8

    def on_hit(self):
        self.hp -= 1
        self._flicker = 1

