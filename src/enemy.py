import math
import random
import pygame

from .math_engine import (
    world_to_camera,
    project_to_screen,
    basis_from_forward,
    get_forward_from_quat,
)
from .constants import MG_COOLDOWN, WEAPON_SPREAD, TRAIL_LIFE_DIVISOR


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

        # Enhanced visual properties
        self.base_color = (255, 255, 255)
        self.engine_trail = []

        # Engine customization (override in subclasses)
        self.engine_offsets = [(0, 0, -35)]  # Local (x, y, z) offsets for thrusters
        self.engine_color = (200, 200, 255)
        self.engine_size = 4.0
        self.trail_life = 0.5

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

    def _draw_engine_trail(self, surf, ppos, prot):
        for x, y, z, life, color, base_size in self.engine_trail:
            cx, cy, cz = world_to_camera(x, y, z, *ppos, prot)
            proj = project_to_screen(cx, cy, cz)
            if proj:
                sx, sy, scale = proj
                ratio = max(0.0, life / (self.trail_life or TRAIL_LIFE_DIVISOR))
                size = max(1, int(scale * base_size * 4 * ratio))

                # Fade color out as it dies
                r = min(255, max(0, int(color[0] * ratio)))
                g = min(255, max(0, int(color[1] * ratio)))
                b = min(255, max(0, int(color[2] * ratio)))

                pygame.draw.circle(surf, (r, g, b), (sx, sy), size)

    def _draw_engine_glow(self, surf, ppos, prot):
        for ox, oy, oz in self.engine_offsets:
            ex = self.x + self.right[0] * ox + self.up[0] * oy + self.forward[0] * oz
            ey = self.y + self.right[1] * ox + self.up[1] * oy + self.forward[1] * oz
            ez = self.z + self.right[2] * ox + self.up[2] * oy + self.forward[2] * oz

            cx, cy, cz = world_to_camera(ex, ey, ez, *ppos, prot)
            proj = project_to_screen(cx, cy, cz)
            if proj:
                sx, sy, scale = proj
                size = max(2, int(scale * self.engine_size * 2))
                pygame.draw.circle(surf, (255, 255, 255), (sx, sy), size)

    def dist_to_player(self, player_pos):
        dx = self.x - player_pos[0]
        dy = self.y - player_pos[1]
        dz = self.z - player_pos[2]
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def draw(self, surf, ppos, prot):
        self._draw_engine_trail(surf, ppos, prot)
        self._draw_engine_glow(surf, ppos, prot)

        world_verts = []
        for vx, vy, vz in self.verts:
            wx = self.x + vx * self.right[0] + vy * self.up[0] + vz * self.forward[0]
            wy = self.y + vx * self.right[1] + vy * self.up[1] + vz * self.forward[1]
            wz = self.z + vx * self.right[2] + vy * self.up[2] + vz * self.forward[2]
            world_verts.append((wx, wy, wz))

        projected = []
        cam_verts = []
        for wx, wy, wz in world_verts:
            cx, cy, cz = world_to_camera(wx, wy, wz, *ppos, prot)
            cam_verts.append((cx, cy, cz))
            projected.append(project_to_screen(cx, cy, cz))

        faces = []
        for f in self.faces:
            i1, i2, i3 = f
            v1, v2, v3 = cam_verts[i1], cam_verts[i2], cam_verts[i3]

            ux, uy, uz = v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2]
            vx2, vy2, vz2 = v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2]

            fnz = ux * vy2 - uy * vx2
            #if fnz >= 0: continue # backface culling uncomment to turn on

            p1, p2, p3 = projected[i1], projected[i2], projected[i3]
            if not (p1 and p2 and p3): continue

            length = math.sqrt(fnz ** 2)
            if length > 0.0001:
                normalized_z = fnz / length
            else:
                normalized_z = 0

            shade = max(0, min(255, int(255 * max(0.2, -normalized_z))))
            color = (
                int(self.base_color[0] * (shade / 255)),
                int(self.base_color[1] * (shade / 255)),
                int(self.base_color[2] * (shade / 255))
            )

            faces.append(((v1[2] + v2[2] + v3[2]) / 3, (p1, p2, p3), color))

        faces.sort(reverse=True)
        for _, pts, color in faces:
            pygame.draw.polygon(surf, color, [(p[0], p[1]) for p in pts])


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
        self.verts = [
            (0, 0, 50),  # 0: Nose
            (-15, -10, -20),  # 1: Bottom left
            (15, -10, -20),  # 2: Bottom right
            (0, 20, -20),  # 3: Top fin
            (0, 0, -30)  # 4: Engine block
        ]
        self.faces = [
            (0, 3, 1), (0, 2, 3), (0, 1, 2),  # Front spikes
            (1, 3, 4), (3, 2, 4), (2, 1, 4)  # Back tapers
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
        self.base_color = (30, 200, 255)

        # Twin Blue Thrusters
        self.engine_offsets = [(-15, 0, -40), (15, 0, -40)]
        self.engine_color = (100, 200, 255)
        self.engine_size = 4.5
        self.trail_life = 0.6

        self.mg_timer = 0.0
        self.bolt_timer = random.uniform(2.0, 5.0)

        self.mode = 'positioning'
        self.mode_timer = random.uniform(2.0, 4.0)
        self.phase = random.uniform(0, math.pi * 2)
        self._flicker = 0

        # Swept-forward fighter wing shape
        self.verts = [
            (0, 0, 70),  # 0: Nose
            (-20, -5, -10),  # 1: Left Body
            (20, -5, -10),  # 2: Right Body
            (0, 15, -20),  # 3: Top Cockpit
            (-50, 0, 30),  # 4: Left Wingtip (swept forward)
            (50, 0, 30),  # 5: Right Wingtip (swept forward)
            (0, -10, -40)  # 6: Tail Block
        ]
        self.faces = [
            (0, 3, 1), (0, 2, 3), (0, 1, 6), (0, 6, 2),  # Main body
            (1, 3, 4), (1, 4, 6),  # Left Wing
            (3, 2, 5), (2, 6, 5)  # Right Wing
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
            proj_speed = 5000
            spread = 0.03
            ax = aim_dir[0] + random.uniform(-spread, spread)
            ay = aim_dir[1] + random.uniform(-spread, spread)
            az = aim_dir[2] + random.uniform(-spread, spread)
            n = math.sqrt(ax * ax + ay * ay + az * az) or 1
            ax, ay, az = ax / n, ay / n, az / n

            vx = ax * proj_speed + self.vx * 0.3
            vy = ay * proj_speed + self.vy * 0.3
            vz = az * proj_speed + self.vz * 0.3

            global_projectiles.append({
                'x': self.x, 'y': self.y, 'z': self.z,
                'vx': vx, 'vy': vy, 'vz': vz,
                'life': 3.0, 'damage': 2, 'homing': False,
                'color': (255, 200, 50), 'size_mult': 1.0
            })

        elif w_type == 'bolt':
            proj_speed = 2200
            vx = aim_dir[0] * proj_speed + self.vx * 0.5
            vy = aim_dir[1] * proj_speed + self.vy * 0.5
            vz = aim_dir[2] * proj_speed + self.vz * 0.5

            global_projectiles.append({
                'x': self.x, 'y': self.y, 'z': self.z,
                'vx': vx, 'vy': vy, 'vz': vz,
                'life': 6.0, 'damage': 15, 'homing': True,
                'color': (200, 50, 255), 'size_mult': 2.5
            })

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
        self.engine_offsets = [(0, 0, -100)]
        self.engine_color = (100, 255, 50)
        self.engine_size = 6.0
        self.trail_life = 0.8

        self.state = 'aiming'
        self.timer = random.uniform(2.0, 4.0)
        self._flicker = 0

        # Asymmetrical, needle-like railgun ship
        self.verts = [
            (0, 0, 150),  # 0: Extreme Nose tip (barrel)
            (-10, -10, -60),  # 1: Body Base L
            (10, -10, -60),  # 2: Body Base R
            (0, 15, -60),  # 3: Top Battery
            (25, -5, -40),  # 4: Asymmetric Side Pod R
            (-5, -5, 50)  # 5: Barrel Support
        ]
        self.faces = [
            (0, 3, 1), (0, 2, 3), (0, 1, 2),  # Main needle
            (2, 4, 3), (1, 3, 4),  # Pod integration
            (5, 2, 4), (5, 4, 3)  # Barrel support
        ]

    def update(self, dt, player_pos, player_orientation, global_projectiles=None, global_enemies=None):
        self.timer -= dt
        px, py, pz = player_pos

        dx, dy, dz = px - self.x, py - self.y, pz - self.z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        nx, ny, nz = dx / dist, dy / dist, dz / dist

        if dist < self.FLEE_RANGE:
            self.state = 'fleeing'
            self.base_color = (150, 255, 100)
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
                    global_projectiles.append({
                        'x': self.x, 'y': self.y, 'z': self.z,
                        'vx': nx * 12000,
                        'vy': ny * 12000,
                        'vz': nz * 12000,
                        'life': 2.0, 'damage': 40, 'homing': False,
                        'color': (255, 255, 255), 'size_mult': 4.0
                    })
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

        # Massive, blocky gunboat geometry
        self.verts = [
            (0, -20, 250),  # 0: Nose Bot
            (0, 20, 250),  # 1: Nose Top
            (-60, -30, 100),  # 2: Mid Hull Bot L
            (60, -30, 100),  # 3: Mid Hull Bot R
            (-60, 30, 100),  # 4: Mid Hull Top L
            (60, 30, 100),  # 5: Mid Hull Top R
            (-80, -30, -200),  # 6: Back Hull Bot L
            (80, -30, -200),  # 7: Back Hull Bot R
            (-80, 30, -200),  # 8: Back Hull Top L
            (80, 30, -200),  # 9: Back Hull Top R
            (0, 80, -80),  # 10: Command Tower Top
            (0, 30, -150)  # 11: Tower slope base
        ]
        self.faces = [
            # Front wedge
            (0, 1, 4), (0, 2, 4), (0, 3, 1), (0, 5, 3), (1, 5, 4),
            # Mid hull to Back Hull
            (2, 6, 8), (2, 8, 4), (3, 5, 9), (3, 9, 7),
            (4, 8, 9), (4, 9, 5), (2, 7, 6), (2, 3, 7),
            # Command Tower
            (4, 5, 10), (4, 10, 8), (5, 9, 10), (8, 10, 11), (9, 11, 10)
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

                global_projectiles.append({
                    'x': self.x, 'y': self.y, 'z': self.z,
                    'vx': ax * 4000 + self.vx * 0.5,
                    'vy': ay * 4000 + self.vy * 0.5,
                    'vz': az * 4000 + self.vz * 0.5,
                    'life': 4.0, 'damage': 5, 'homing': False,
                    'color': (50, 255, 50), 'size_mult': 1.5
                })

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
        self.verts = [
            (0, 0, 40),  # 0: Center Nose
            (-80, -5, -10),  # 1: Far Left
            (80, -5, -10),  # 2: Far Right
            (-30, 15, -20),  # 3: Mid Left Bulk
            (30, 15, -20),  # 4: Mid Right Bulk
            (0, -15, -30)  # 5: Underbelly
        ]
        self.faces = [
            (0, 3, 1), (0, 2, 4), (0, 4, 3),  # Top layer
            (0, 1, 5), (0, 5, 2), (1, 3, 5), (2, 5, 4),  # Bottom/Side bulk
            (3, 4, 5)  # Back seal
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
                global_projectiles.append({
                    'x': self.x, 'y': self.y, 'z': self.z,
                    'vx': 0, 'vy': 0, 'vz': 0,
                    'life': 25.0, 'damage': 25, 'homing': False,
                    'color': (255, 30, 30), 'size_mult': 6.0
                })

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
        self.verts = [
            (0, 0, 60),  # 0: Needle point
            (-25, 0, -30),  # 1: Left Wing
            (25, 0, -30),  # 2: Right Wing
            (0, 5, -20),  # 3: Top ridge
            (0, -5, -20)  # 4: Bottom ridge
        ]
        self.faces = [
            (0, 1, 3), (0, 3, 2),  # Top
            (0, 4, 1), (0, 2, 4),  # Bottom
            (1, 2, 3), (1, 4, 2)  # Back
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
                        global_projectiles.append({
                            'x': self.x, 'y': self.y, 'z': self.z,
                            'vx': ax * 3000, 'vy': ay * 3000, 'vz': az * 3000,
                            'life': 1.5, 'damage': 8, 'homing': False,
                            'color': (100, 100, 255), 'size_mult': 1.2
                        })
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
        self.verts = [
            (0, -20, 800),  # 0: Ultimate Nose
            (0, 80, -200),  # 1: Command Ridge Top Front
            (0, 180, -450),  # 2: Command Tower High
            (-400, -20, -500),  # 3: Far Wingtip L
            (400, -20, -500),  # 4: Far Wingtip R
            (-150, 60, -500),  # 5: Back Top L
            (150, 60, -500),  # 6: Back Top R
            (-150, -80, -500),  # 7: Back Bot L
            (150, -80, -500),  # 8: Back Bot R
            (0, -120, -100)  # 9: Deep Belly
        ]
        self.faces = [
            # Top Deck
            (0, 3, 5), (0, 5, 1), (0, 1, 6), (0, 6, 4),
            # Command Tower
            (1, 5, 2), (1, 2, 6), (5, 6, 2),
            # Belly
            (0, 7, 3), (0, 9, 7), (0, 8, 9), (0, 4, 8),
            # Thruster plate (Back)
            (5, 3, 7), (6, 8, 4), (5, 7, 8), (5, 8, 6)
        ]

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