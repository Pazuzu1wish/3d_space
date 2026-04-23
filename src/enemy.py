import math
import random
import pygame

from .math_engine import (
    world_to_camera,
    project_to_screen,
    basis_from_forward,  # ← you added this
)

# ──────────────────────────────────────────────
#  BASE ENEMY
# ──────────────────────────────────────────────

class Enemy:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.hp = 1

    def update(self, dt, player_pos, player_orientation):
        pass

    def draw(self, surf, ppos, prot):
        pass

    def _camera_z(self, player_pos, player_orientation):
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


# ──────────────────────────────────────────────
#  SUICIDE DRONE
# ──────────────────────────────────────────────

class SuicideDrone(Enemy):

    SPEED = 520
    COLLISION_RADIUS = 90
    BEHIND_THRESHOLD = -400

    def __init__(self, x, y, z):
        super().__init__(x, y, z)
        self.hp = 3

        self.vx = self.vy = self.vz = 0.0

        self.pattern_fn = random.choice(PATTERNS)
        self.pattern_phase = random.uniform(0, math.tau)
        self.t = 0.0

        # ── ORIENTATION (NEW) ──
        self.forward = (0, 0, 1)
        self.right   = (1, 0, 0)
        self.up      = (0, 1, 0)

        # ── GEOMETRY ──
        self.verts = [
            (0, 0, 40),
            (-20, 0, -20),
            (20, 0, -20),
            (0, -15, -20),
            (0, 10, -15),
        ]

        self.faces = [
            (0,1,2),
            (0,1,3),
            (0,2,3),
            (1,2,4),
        ]

        self._flicker = 0.0

    # ──────────────────────────────────────────
    # UPDATE
    # ──────────────────────────────────────────

    def update(self, dt, player_pos, player_orientation):
        self.t += dt

        px, py, pz = player_pos
        dx = px - self.x
        dy = py - self.y
        dz = pz - self.z
        dist = math.sqrt(dx*dx + dy*dy + dz*dz) or 1.0

        nx, ny, nz = dx/dist, dy/dist, dz/dist

        cz = self._camera_z(player_pos, player_orientation)

        if cz < self.BEHIND_THRESHOLD:
            home_speed = self.SPEED * 1.6
            evade = (0, 0, 0)
        else:
            home_speed = self.SPEED

            ex, ey, _ = self.pattern_fn(self.t, self.pattern_phase, self.SPEED)

            world_up = (0,1,0)
            rx = ny*world_up[2] - nz*world_up[1]
            ry = nz*world_up[0] - nx*world_up[2]
            rz = nx*world_up[1] - ny*world_up[0]
            rlen = math.sqrt(rx*rx + ry*ry + rz*rz) or 1.0
            rx, ry, rz = rx/rlen, ry/rlen, rz/rlen

            ux = ry*nz - rz*ny
            uy = rz*nx - rx*nz
            uz = rx*ny - ry*nx

            evade = (
                ex*rx + ey*ux,
                ex*ry + ey*uy,
                ex*rz + ey*uz
            )

        target_vx = nx * home_speed + evade[0]
        target_vy = ny * home_speed + evade[1]
        target_vz = nz * home_speed + evade[2]

        blend = min(1.0, dt * 6.0)
        self.vx += (target_vx - self.vx) * blend
        self.vy += (target_vy - self.vy) * blend
        self.vz += (target_vz - self.vz) * blend

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt

        # ── ORIENTATION UPDATE (NEW) ──
        speed = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2)
        if speed > 1e-3:
            self.forward, self.right, self.up = basis_from_forward(
                (self.vx, self.vy, self.vz)
            )

        if self._flicker > 0:
            self._flicker = max(0.0, self._flicker - dt * 8.0)

    def on_hit(self):
        self.hp -= 1
        self._flicker = 1.0

    # ──────────────────────────────────────────
    # DRAW (SOLID RENDERING)
    # ──────────────────────────────────────────

    def draw(self, surf, ppos, prot):
        world_verts = []

        # Transform verts into world space using orientation
        for vx, vy, vz in self.verts:
            wx = self.x + vx*self.right[0] + vy*self.up[0] + vz*self.forward[0]
            wy = self.y + vx*self.right[1] + vy*self.up[1] + vz*self.forward[1]
            wz = self.z + vx*self.right[2] + vy*self.up[2] + vz*self.forward[2]
            world_verts.append((wx, wy, wz))

        projected = []
        cam_verts = []

        for wx, wy, wz in world_verts:
            cx, cy, cz = world_to_camera(wx, wy, wz, *ppos, prot)
            cam_verts.append((cx, cy, cz))
            proj = project_to_screen(cx, cy, cz)
            projected.append(proj)

        faces_to_draw = []

        for f in self.faces:
            i1, i2, i3 = f
            v1, v2, v3 = cam_verts[i1], cam_verts[i2], cam_verts[i3]

            # Backface culling
            ux, uy, uz = v2[0]-v1[0], v2[1]-v1[1], v2[2]-v1[2]
            vx, vy, vz = v3[0]-v1[0], v3[1]-v1[1], v3[2]-v1[2]

            nx = uy*vz - uz*vy
            ny = uz*vx - ux*vz
            nz = ux*vy - uy*vx

            if nz >= 0:
                continue

            p1, p2, p3 = projected[i1], projected[i2], projected[i3]
            if not (p1 and p2 and p3):
                continue

            # Simple lighting
            light = max(0.2, -nz * 0.002)
            shade = max(0, min(255, int(255 * light)))

            if self._flicker > 0.5:
                color = (255,255,255)
            elif self.hp <= 1:
                color = (shade, int(shade*0.6), 80)
            else:
                color = (shade, 60, 60)

            avg_z = (v1[2] + v2[2] + v3[2]) / 3
            faces_to_draw.append((avg_z, (p1, p2, p3), color))

        faces_to_draw.sort(reverse=True)

        for _, pts, color in faces_to_draw:
            pygame.draw.polygon(surf, color, [
                (pts[0][0], pts[0][1]),
                (pts[1][0], pts[1][1]),
                (pts[2][0], pts[2][1]),
            ])