import math
import random
import pygame

from .math_engine import (
    world_to_camera,
    project_to_screen,
    basis_from_forward,
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
#  MOVEMENT PATTERNS  (shared by both types)
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
    amp  = speed * 0.8
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
#  SHARED: project evasion into approach frame
# ──────────────────────────────────────────────

def _apply_evasion(nx, ny, nz, ex, ey):
    """
    Rotate raw pattern output (ex, ey) into the plane perpendicular to
    the approach vector (nx, ny, nz).  Returns (evade_x, evade_y, evade_z).
    """
    world_up = (0.0, 1.0, 0.0)
    rx = ny * world_up[2] - nz * world_up[1]
    ry = nz * world_up[0] - nx * world_up[2]
    rz = nx * world_up[1] - ny * world_up[0]
    rlen = math.sqrt(rx*rx + ry*ry + rz*rz) or 1.0
    rx /= rlen; ry /= rlen; rz /= rlen

    ux = ry*nz - rz*ny
    uy = rz*nx - rx*nz
    uz = rx*ny - ry*nx

    return (
        ex*rx + ey*ux,
        ex*ry + ey*uy,
        ex*rz + ey*uz,
    )


# ──────────────────────────────────────────────
#  SUICIDE DRONE
# ──────────────────────────────────────────────

class SuicideDrone(Enemy):

    SPEED            = 520
    COLLISION_RADIUS = 90
    BEHIND_THRESHOLD = -400

    def __init__(self, x, y, z):
        super().__init__(x, y, z)
        self.hp = 3

        self.vx = self.vy = self.vz = 0.0

        self.pattern_fn    = random.choice(PATTERNS)
        self.pattern_phase = random.uniform(0, math.tau)
        self.t             = 0.0

        self.forward = (0, 0, 1)
        self.right   = (1, 0, 0)
        self.up      = (0, 1, 0)

        self.verts = [
            ( 0,   0,  40),
            (-20,  0, -20),
            ( 20,  0, -20),
            (  0, -15, -20),
            (  0,  10, -15),
        ]
        self.faces = [
            (0, 1, 2),
            (0, 1, 3),
            (0, 2, 3),
            (1, 2, 4),
        ]

        self._flicker = 0.0

    def update(self, dt, player_pos, player_orientation):
        self.t += dt

        px, py, pz = player_pos
        dx = px - self.x;  dy = py - self.y;  dz = pz - self.z
        dist = math.sqrt(dx*dx + dy*dy + dz*dz) or 1.0
        nx, ny, nz = dx/dist, dy/dist, dz/dist

        cz = self._camera_z(player_pos, player_orientation)

        if cz < self.BEHIND_THRESHOLD:
            home_speed = self.SPEED * 1.6
            evade = (0.0, 0.0, 0.0)
        else:
            home_speed = self.SPEED
            ex, ey, _ = self.pattern_fn(self.t, self.pattern_phase, self.SPEED)
            evade = _apply_evasion(nx, ny, nz, ex, ey)

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

        spd = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2)
        if spd > 1e-3:
            self.forward, self.right, self.up = basis_from_forward(
                (self.vx, self.vy, self.vz)
            )

        if self._flicker > 0:
            self._flicker = max(0.0, self._flicker - dt * 8.0)

    def on_hit(self):
        self.hp -= 1
        self._flicker = 1.0

    def draw(self, surf, ppos, prot):
        world_verts = []
        for vx, vy, vz in self.verts:
            wx = self.x + vx*self.right[0] + vy*self.up[0] + vz*self.forward[0]
            wy = self.y + vx*self.right[1] + vy*self.up[1] + vz*self.forward[1]
            wz = self.z + vx*self.right[2] + vy*self.up[2] + vz*self.forward[2]
            world_verts.append((wx, wy, wz))

        projected = []
        cam_verts  = []
        for wx, wy, wz in world_verts:
            cx, cy, cz = world_to_camera(wx, wy, wz, *ppos, prot)
            cam_verts.append((cx, cy, cz))
            projected.append(project_to_screen(cx, cy, cz))

        faces_to_draw = []
        for f in self.faces:
            i1, i2, i3 = f
            v1, v2, v3 = cam_verts[i1], cam_verts[i2], cam_verts[i3]
            ux, uy, uz = v2[0]-v1[0], v2[1]-v1[1], v2[2]-v1[2]
            vx2, vy2, vz2 = v3[0]-v1[0], v3[1]-v1[1], v3[2]-v1[2]
            fnx = uy*vz2 - uz*vy2
            fny = uz*vx2 - ux*vz2
            fnz = ux*vy2 - uy*vx2
            if fnz >= 0:
                continue
            p1, p2, p3 = projected[i1], projected[i2], projected[i3]
            if not (p1 and p2 and p3):
                continue
            light = max(0.2, -fnz * 0.002)
            shade = max(0, min(255, int(255 * light)))
            if self._flicker > 0.5:
                color = (255, 255, 255)
            elif self.hp <= 1:
                color = (shade, int(shade * 0.6), 80)
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


# ──────────────────────────────────────────────
#  ENEMY LASER  (fired by Dogfighter)
# ──────────────────────────────────────────────

class EnemyLaser:
    """
    Slow orange plasma bolt — dodgeable with a hard turn.
    """
    SPEED      = 1200
    LIFETIME   = 3.5
    HIT_RADIUS = 75

    COLOR_CORE = (255, 140, 40)
    COLOR_GLOW = (180,  60,  0)

    def __init__(self, x, y, z, forward):
        self.x, self.y, self.z = float(x), float(y), float(z)
        fx, fy, fz = forward
        self.vx = fx * self.SPEED
        self.vy = fy * self.SPEED
        self.vz = fz * self.SPEED
        self.life = self.LIFETIME

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self.life -= dt

    def hits_player(self, player_pos):
        dx = self.x - player_pos[0]
        dy = self.y - player_pos[1]
        dz = self.z - player_pos[2]
        return math.sqrt(dx*dx + dy*dy + dz*dz) < self.HIT_RADIUS

    def draw(self, surf, ppos, prot):
        cx, cy, cz = world_to_camera(self.x, self.y, self.z, *ppos, prot)
        proj = project_to_screen(cx, cy, cz)
        if not proj:
            return
        sx, sy, scale = proj

        spd = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2) or 1.0
        tnx, tny, tnz = self.vx/spd, self.vy/spd, self.vz/spd
        tail_dist = 28.0
        tx = self.x - tnx * tail_dist
        ty = self.y - tny * tail_dist
        tz = self.z - tnz * tail_dist
        tcx, tcy, tcz = world_to_camera(tx, ty, tz, *ppos, prot)
        tproj = project_to_screen(tcx, tcy, tcz)

        if tproj:
            pygame.draw.line(surf, self.COLOR_GLOW,
                             (sx, sy), (tproj[0], tproj[1]), 3)
            pygame.draw.line(surf, self.COLOR_CORE,
                             (sx, sy), (tproj[0], tproj[1]), 1)
        pygame.draw.circle(surf, self.COLOR_CORE, (sx, sy), max(2, int(scale * 3)))


# ──────────────────────────────────────────────
#  DOGFIGHTER
# ──────────────────────────────────────────────

_DF_APPROACH = 'approach'
_DF_STRAFE   = 'strafe'
_DF_TAIL     = 'tail'
_DF_EVADE    = 'evade'


class Dogfighter(Enemy):
    """
    Armed fighter.  Tries to get on the player's six and gun them down.

    States:
      APPROACH  — close the gap, mild weave
      STRAFE    — orbit at engagement range, hunting for a rear angle
      TAIL      — behind the player, pressing the attack
      EVADE     — took a hit, hard break before re-engaging
    """

    SPEED            = 440
    STRAFE_DIST      = 1400
    TAIL_DIST        = 900
    FIRE_RANGE       = 1800
    FIRE_RATE        = 1.6
    COLLISION_RADIUS = 120
    HP_MAX           = 8
    TAIL_THRESHOLD   = -600   # dogfighter's own camera-Z must be < this
    EVADE_DURATION   = 1.8

    def __init__(self, x, y, z):
        super().__init__(x, y, z)
        self.hp = self.HP_MAX

        self.vx = self.vy = self.vz = 0.0

        self.state         = _DF_APPROACH
        self.evade_timer   = 0.0
        self.fire_timer    = random.uniform(0, self.FIRE_RATE)
        self.t             = 0.0

        self.pattern_fn    = random.choice(PATTERNS[1:])   # never direct
        self.pattern_phase = random.uniform(0, math.tau)
        self.orbit_side    = random.choice((-1, 1))

        self.forward = (0, 0, 1)
        self.right   = (1, 0, 0)
        self.up      = (0, 1, 0)

        self._flicker    = 0.0
        self.projectiles = []

        # Geometry: larger angular fighter, ~1.6× drone scale
        self.verts = [
            (  0,   0,  60),   # 0  Nose
            (-40,   5, -10),   # 1  Left wing tip
            ( 40,   5, -10),   # 2  Right wing tip
            (-15,   0, -30),   # 3  Left tail
            ( 15,   0, -30),   # 4  Right tail
            (  0, -20, -20),   # 5  Dorsal fin
            (  0,  12, -25),   # 6  Ventral keel
            ( -8,   0,  10),   # 7  Left cockpit edge
            (  8,   0,  10),   # 8  Right cockpit edge
        ]
        self.faces = [
            (0, 7, 5),
            (0, 8, 5),
            (7, 8, 5),
            (0, 1, 3),
            (0, 3, 7),
            (0, 2, 4),
            (0, 4, 8),
            (3, 4, 5),
            (3, 4, 6),
            (0, 7, 6),
            (0, 8, 6),
        ]

    # ── State machine ──────────────────────────

    def update(self, dt, player_pos, player_orientation):
        self.t += dt
        self.fire_timer = max(0.0, self.fire_timer - dt)

        px, py, pz = player_pos
        dx = px - self.x;  dy = py - self.y;  dz = pz - self.z
        dist = math.sqrt(dx*dx + dy*dy + dz*dz) or 1.0
        nx, ny, nz = dx/dist, dy/dist, dz/dist

        # Camera-space Z of this fighter from the player's POV
        df_cam_z = self._camera_z(player_pos, player_orientation)

        # ── Transitions ──
        if self.state == _DF_EVADE:
            self.evade_timer -= dt
            if self.evade_timer <= 0:
                self.state = _DF_APPROACH

        elif self.state == _DF_APPROACH:
            if dist < self.STRAFE_DIST:
                self.state = _DF_STRAFE

        elif self.state == _DF_STRAFE:
            if df_cam_z < self.TAIL_THRESHOLD:
                self.state = _DF_TAIL
            elif dist > self.STRAFE_DIST * 1.6:
                self.state = _DF_APPROACH

        elif self.state == _DF_TAIL:
            if df_cam_z > 200:
                self.state = _DF_STRAFE

        # ── Velocity target per state ──
        ex, ey, _ = self.pattern_fn(self.t, self.pattern_phase, self.SPEED)

        if self.state == _DF_APPROACH:
            ex_s, ey_s, _ = self.pattern_fn(self.t, self.pattern_phase, self.SPEED * 0.3)
            evade = _apply_evasion(nx, ny, nz, ex_s, ey_s)
            target_v = (
                nx * self.SPEED + evade[0],
                ny * self.SPEED + evade[1],
                nz * self.SPEED + evade[2],
            )

        elif self.state == _DF_STRAFE:
            # Orbit tangentially around the player
            world_up = (0.0, 1.0, 0.0)
            orx = ny*world_up[2] - nz*world_up[1]
            ory = nz*world_up[0] - nx*world_up[2]
            orz = nx*world_up[1] - ny*world_up[0]
            orlen = math.sqrt(orx*orx + ory*ory + orz*orz) or 1.0
            orx /= orlen; ory /= orlen; orz /= orlen

            orbit_frac  = 0.55
            inward_frac = 0.0 if dist < self.STRAFE_DIST * 0.8 else 0.45
            target_v = (
                orx * self.SPEED * orbit_frac * self.orbit_side + nx * self.SPEED * inward_frac,
                ory * self.SPEED * orbit_frac * self.orbit_side + ny * self.SPEED * inward_frac,
                orz * self.SPEED * orbit_frac * self.orbit_side + nz * self.SPEED * inward_frac,
            )

        elif self.state == _DF_TAIL:
            tail_speed = self.SPEED * 0.75
            target_v = (
                nx * tail_speed,
                ny * tail_speed,
                nz * tail_speed,
            )

        else:  # EVADE — break hard away + pattern
            evade = _apply_evasion(-nx, -ny, -nz, ex, ey)
            retreat = self.SPEED * 0.9
            target_v = (
                -nx * retreat + evade[0],
                -ny * retreat + evade[1],
                -nz * retreat + evade[2],
            )

        # ── Integrate ──
        blend = min(1.0, dt * 4.5)
        self.vx += (target_v[0] - self.vx) * blend
        self.vy += (target_v[1] - self.vy) * blend
        self.vz += (target_v[2] - self.vz) * blend

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt

        # ── Orientation ──
        spd = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2)
        if spd > 1e-3:
            self.forward, self.right, self.up = basis_from_forward(
                (self.vx, self.vy, self.vz)
            )

        # ── Fire ──
        if self.fire_timer <= 0 and dist < self.FIRE_RANGE:
            dot = (self.forward[0]*nx +
                   self.forward[1]*ny +
                   self.forward[2]*nz)
            if dot > 0.70:
                nose_x = self.x + self.forward[0] * 70
                nose_y = self.y + self.forward[1] * 70
                nose_z = self.z + self.forward[2] * 70
                self.projectiles.append(
                    EnemyLaser(nose_x, nose_y, nose_z, self.forward)
                )
                self.fire_timer = self.FIRE_RATE

        # ── Own projectile lifecycle ──
        for bolt in self.projectiles[:]:
            bolt.update(dt)
            if bolt.life <= 0:
                self.projectiles.remove(bolt)

        if self._flicker > 0:
            self._flicker = max(0.0, self._flicker - dt * 8.0)

    def on_hit(self):
        self.hp -= 1
        self._flicker = 1.0
        self.state       = _DF_EVADE
        self.evade_timer = self.EVADE_DURATION
        self.orbit_side  = -self.orbit_side    # vary re-engagement angle

    # ── Draw ───────────────────────────────────

    def draw(self, surf, ppos, prot):
        for bolt in self.projectiles:
            bolt.draw(surf, ppos, prot)

        world_verts = []
        for vx, vy, vz in self.verts:
            wx = self.x + vx*self.right[0] + vy*self.up[0] + vz*self.forward[0]
            wy = self.y + vx*self.right[1] + vy*self.up[1] + vz*self.forward[1]
            wz = self.z + vx*self.right[2] + vy*self.up[2] + vz*self.forward[2]
            world_verts.append((wx, wy, wz))

        projected = []
        cam_verts  = []
        for wx, wy, wz in world_verts:
            cx, cy, cz = world_to_camera(wx, wy, wz, *ppos, prot)
            cam_verts.append((cx, cy, cz))
            projected.append(project_to_screen(cx, cy, cz))

        faces_to_draw = []
        for f in self.faces:
            i1, i2, i3 = f
            v1, v2, v3 = cam_verts[i1], cam_verts[i2], cam_verts[i3]
            ux, uy, uz = v2[0]-v1[0], v2[1]-v1[1], v2[2]-v1[2]
            vx2, vy2, vz2 = v3[0]-v1[0], v3[1]-v1[1], v3[2]-v1[2]
            fnx = uy*vz2 - uz*vy2
            fny = uz*vx2 - ux*vz2
            fnz = ux*vy2 - uy*vx2
            if fnz >= 0:
                continue
            p1, p2, p3 = projected[i1], projected[i2], projected[i3]
            if not (p1 and p2 and p3):
                continue

            light = max(0.15, -fnz * 0.0018)
            shade = max(0, min(255, int(255 * light)))

            if self._flicker > 0.5:
                color = (255, 255, 255)
            elif self.hp <= 2:
                color = (shade, int(shade * 0.55), 30)   # dying amber
            else:
                color = (30, int(shade * 0.85), shade)   # healthy teal

            avg_z = (v1[2] + v2[2] + v3[2]) / 3
            faces_to_draw.append((avg_z, (p1, p2, p3), color))

        faces_to_draw.sort(reverse=True)
        for _, pts, color in faces_to_draw:
            pygame.draw.polygon(surf, color, [
                (pts[0][0], pts[0][1]),
                (pts[1][0], pts[1][1]),
                (pts[2][0], pts[2][1]),
            ])