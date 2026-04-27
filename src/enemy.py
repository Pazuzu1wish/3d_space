import math
import random
import pygame

from .math_engine import (
    world_to_camera,
    project_to_screen,
    basis_from_forward,
    get_forward_from_quat,
)

# ──────────────────────────────────────────────
#  BASE ENEMY
# ──────────────────────────────────────────────

class Enemy:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.hp = 1

        self.vx = self.vy = self.vz = 0.0

        self.forward = (0,0,1)
        self.right   = (1,0,0)
        self.up      = (0,1,0)

        self.engine_trail = []
        self.base_color = (255, 255, 255)


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
            ax*self.right[0] +
            ay*self.right[1] +
            az*self.right[2]
        )

        roll = max(-1.5, min(1.5, roll_signal * 0.002))

        ux, uy, uz = self.up
        rx, ry, rz = self.right

        ux += rx * roll
        uy += ry * roll
        uz += rz * roll

        ulen = math.sqrt(ux*ux + uy*uy + uz*uz) or 1.0
        ux, uy, uz = ux/ulen, uy/ulen, uz/ulen

        fx, fy, fz = self.forward
        rx = fy*uz - fz*uy
        ry = fz*ux - fx*uz
        rz = fx*uy - fy*ux

        self.up = (ux, uy, uz)
        self.right = (rx, ry, rz)

    def _update_orientation(self):
        spd = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2)
        if spd > 1e-3:
            self.forward, self.right, self.up = basis_from_forward(
                (self.vx, self.vy, self.vz)
            )

    def _spawn_engine_trail(self):
        ex = self.x - self.forward[0]*35
        ey = self.y - self.forward[1]*35
        ez = self.z - self.forward[2]*35

        self.engine_trail.append([ex, ey, ez, 0.5])

    def _update_engine_trail(self, dt):
        for p in self.engine_trail:
            p[3] -= dt
        self.engine_trail = [p for p in self.engine_trail if p[3] > 0]

    def _draw_engine_trail(self, surf, ppos, prot):
        for x,y,z,life in self.engine_trail:
            cx, cy, cz = world_to_camera(x,y,z,*ppos, prot)
            proj = project_to_screen(cx, cy, cz)
            if proj:
                sx, sy, scale = proj
                size = max(1, int(scale * 4 * life))
                color = (int(255*life), int(200*life), 255)
                pygame.draw.circle(surf, color, (sx,sy), size)

    def _draw_engine_glow(self, surf, ppos, prot):
        ex = self.x - self.forward[0]*35
        ey = self.y - self.forward[1]*35
        ez = self.z - self.forward[2]*35

        cx, cy, cz = world_to_camera(ex,ey,ez,*ppos, prot)
        proj = project_to_screen(cx, cy, cz)
        if proj:
            sx, sy, scale = proj
            size = max(2, int(scale * 6))
            pygame.draw.circle(surf, (255,255,255), (sx,sy), size)

    def dist_to_player(self, player_pos):
        dx = self.x - player_pos[0]
        dy = self.y - player_pos[1]
        dz = self.z - player_pos[2]
        return math.sqrt(dx*dx + dy*dy + dz*dz)

    def draw(self, surf, ppos, prot):
        self._draw_engine_trail(surf, ppos, prot)
        self._draw_engine_glow(surf, ppos, prot)

        world_verts = []
        for vx,vy,vz in self.verts:
            wx = self.x + vx*self.right[0] + vy*self.up[0] + vz*self.forward[0]
            wy = self.y + vx*self.right[1] + vy*self.up[1] + vz*self.forward[1]
            wz = self.z + vx*self.right[2] + vy*self.up[2] + vz*self.forward[2]
            world_verts.append((wx,wy,wz))

        projected=[]
        cam_verts=[]
        for wx,wy,wz in world_verts:
            cx,cy,cz = world_to_camera(wx,wy,wz,*ppos, prot)
            cam_verts.append((cx,cy,cz))
            projected.append(project_to_screen(cx,cy,cz))

        faces=[]
        for f in self.faces:
            i1,i2,i3=f
            v1,v2,v3 = cam_verts[i1], cam_verts[i2], cam_verts[i3]

            ux,uy,uz = v2[0]-v1[0],v2[1]-v1[1],v2[2]-v1[2]
            vx2,vy2,vz2 = v3[0]-v1[0],v3[1]-v1[1],v3[2]-v1[2]

            fnz = ux*vy2 - uy*vx2
            if fnz >= 0: continue

            p1,p2,p3 = projected[i1],projected[i2],projected[i3]
            if not(p1 and p2 and p3): continue

            length = math.sqrt(fnz**2)
            if length > 0.0001:
                normalized_z = fnz / length
            else:
                normalized_z = 0
                
            shade = max(0, min(255, int(255 * max(0.2, -normalized_z))))
            color = (
                int(self.base_color[0] * (shade/255)),
                int(self.base_color[1] * (shade/255)),
                int(self.base_color[2] * (shade/255))
            )

            faces.append(((v1[2]+v2[2]+v3[2])/3,(p1,p2,p3),color))

        faces.sort(reverse=True)
        for _,pts,color in faces:
            pygame.draw.polygon(surf,color,[(p[0],p[1]) for p in pts])


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

    SPEED = 1500

    def __init__(self, x,y,z):
        super().__init__(x,y,z)
        self.hp = 1
        self.base_color = (255, 30, 30)

        self.t = 0

        self.pattern = random.choice(PATTERNS)
        self.pattern_phase = random.uniform(0, math.pi*2)

        self._flicker = 0

        self.verts = [
            (0,0,40),(-20,0,-20),(20,0,-20),(0,-15,-20),(0,10,-15)
        ]
        self.faces = [(0,1,2),(0,1,3),(0,2,3),(1,2,4)]

        # Add to SuicideDrone.__init__:
        self.pattern = None   # None = dynamic tail-check each frame
        self._pattern_cache = None   # avoid flipping pattern every single frame
        self._pattern_check_timer = 0.0

    def set_pattern(self, pattern_name):
        if pattern_name in PATTERN_MAP:
            self.pattern = PATTERN_MAP[pattern_name]

    def update(self, dt, player_pos, player_orientation, global_projectiles=None):
        self.t += dt
        self._pattern_check_timer += dt

        px, py, pz = player_pos
        dx, dy, dz = px-self.x, py-self.y, pz-self.z
        dist = math.sqrt(dx*dx + dy*dy + dz*dz) or 1
        nx, ny, nz = dx/dist, dy/dist, dz/dist

        # ── PATTERN SELECTION ─────────────────────
        # Re-evaluate every 0.5s so it doesn't thrash frame-to-frame
        if self.pattern is not None:
            # Scripted drones: fixed pattern assigned by director
            active_pattern = self.pattern
        elif self._pattern_check_timer >= 0.5:
            self._pattern_check_timer = 0.0
            fwd = get_forward_from_quat(player_orientation)

            # Dot of (drone→player) against player forward.
            # drone is BEHIND player when this is negative,
            # because drone-to-player points same way as player-forward
            # only when drone is ahead. Behind = dot strongly negative.
            to_player_nx = -nx  # flip: player→drone becomes drone→player direction... 
            # actually cleaner: dot of (player→drone) against player fwd
            # player→drone = (dx,dy,dz)/dist, already computed as (nx,ny,nz)
            dot = nx*fwd[0] + ny*fwd[1] + nz*fwd[2]

            # dot > 0.85: drone is in front of player — definitely not safe
            # dot < -0.82: drone is within ~35° of directly behind — safe cone
            if dot < -0.82:
                self._pattern_cache = _pattern_direct
            else:
                if self._pattern_cache is _pattern_direct:
                    # Just left the safe cone — pick a new evasive pattern
                    self._pattern_cache = random.choice(PATTERNS[1:])
                elif self._pattern_cache is None:
                    self._pattern_cache = random.choice(PATTERNS[1:])

            active_pattern = self._pattern_cache
        else:
            active_pattern = self._pattern_cache or _pattern_weave

        # ── MOVEMENT ──────────────────────────────
        offset = active_pattern(self.t, self.pattern_phase, self.SPEED)
        target_v = (
            nx*self.SPEED + offset[0],
            ny*self.SPEED + offset[1],
            nz*self.SPEED + offset[2],
        )

        self._apply_banking(target_v, dt)

        blend = min(1, dt*6)
        self.vx += (target_v[0]-self.vx)*blend
        self.vy += (target_v[1]-self.vy)*blend
        self.vz += (target_v[2]-self.vz)*blend

        self.x += self.vx*dt
        self.y += self.vy*dt
        self.z += self.vz*dt

        self._update_orientation()
        self._spawn_engine_trail()
        self._update_engine_trail(dt)

        if self._flicker > 0:
            self._flicker -= dt*8

    def on_hit(self):
        self.hp -= 1
        self._flicker = 1
        # Getting hit breaks it out of direct immediately
        if self._pattern_cache is _pattern_direct:
            self._pattern_cache = random.choice(PATTERNS[1:])



# ──────────────────────────────────────────────
#  DOGFIGHTER (UPGRADED)
# ──────────────────────────────────────────────

class Dogfighter(Enemy):

    SPEED = 1500
    FIRE_RATE = 50.2
    FIRE_RANGE = 3000
    IDEAL_RANGE = 800      # How far behind the player it tries to stay
    CIRCLE_RADIUS = 2000    # Width of its strafing/circling pattern

    def __init__(self, x, y, z):
        super().__init__(x, y, z)

        self.hp = 3
        self.t = 0
        self.base_color = (30, 200, 255)

        self.fire_timer = random.uniform(0, self.FIRE_RATE)
        self.aggression = random.uniform(0.7, 1.3)

        self._flicker = 0
        self.phase = random.uniform(0, math.pi * 2)  # Unique circling offset

        self.verts = [
            (0, 0, 60), (-40, 5, -10), (40, 5, -10),
            (-15, 0, -30), (15, 0, -30), (0, -20, -20)
        ]
        self.faces = [(0, 1, 3), (0, 2, 4), (1, 2, 5)]

    def _player_forward(self, orientation):
        """Calculate player's forward vector from quaternion."""
        return get_forward_from_quat(orientation)

    def update(self, dt, player_pos, player_orientation, global_projectiles=None):
        self.t += dt
        self.fire_timer -= dt

        px, py, pz = player_pos

        # 1. Find point behind the player
        pfw = self._player_forward(player_orientation)
        behind_x = px - pfw[0] * self.IDEAL_RANGE
        behind_y = py - pfw[1] * self.IDEAL_RANGE
        behind_z = pz - pfw[2] * self.IDEAL_RANGE

        # 2. Add lateral offset so it circles/strafes instead of lining up perfectly
        offset_x = math.sin(self.t * 0.8 + self.phase) * self.CIRCLE_RADIUS
        offset_y = math.cos(self.t * 0.6 + self.phase) * self.CIRCLE_RADIUS * 0.4
        offset_z = math.sin(self.t * 0.5 + self.phase) * self.CIRCLE_RADIUS * 0.3

        target_x = behind_x + offset_x
        target_y = behind_y + offset_y
        target_z = behind_z + offset_z

        # 3. Direction & speed towards that target
        dx = target_x - self.x
        dy = target_y - self.y
        dz = target_z - self.z
        dist = math.sqrt(dx*dx + dy*dy + dz*dz) or 1.0

        nx, ny, nz = dx/dist, dy/dist, dz/dist
        target_v = (nx * self.SPEED, ny * self.SPEED, nz * self.SPEED)

        # 4. Apply banking & blend velocity (unchanged from your original)
        self._apply_banking(target_v, dt)
        blend = min(1.0, dt * 4.0)
        self.vx += (target_v[0] - self.vx) * blend
        self.vy += (target_v[1] - self.vy) * blend
        self.vz += (target_v[2] - self.vz) * blend

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt

        self._update_orientation()

        # 5. Firing logic
        to_px = px - self.x
        to_py = py - self.y
        to_pz = pz - self.z
        dist_to_player = math.sqrt(to_px**2 + to_py**2 + to_pz**2) or 1.0

        if dist_to_player < self.FIRE_RANGE and self.fire_timer <= 0:
            # Check if roughly facing player
            to_player_norm = (to_px/dist_to_player, to_py/dist_to_player, to_pz/dist_to_player)
            dot = (self.forward[0]*to_player_norm[0] +
                   self.forward[1]*to_player_norm[1] +
                   self.forward[2]*to_player_norm[2])

            if dot > .001:  # Lower threshold = shoots while maneuvering
                self.fire_timer = self.FIRE_RATE * random.uniform(0.7, 1.2)
                self._fire_projectile(to_player_norm, dist_to_player, global_projectiles)

        # Trails & hit flicker
        self._spawn_engine_trail()
        self._update_engine_trail(dt)
        if self._flicker > 0:
            self._flicker -= dt * 8

    def _fire_projectile(self, aim_dir, dist, global_projectiles):
        """Spawn a bullet. Adapt this dict structure to match your bullet system."""
        proj_speed = 4000
        # Add a portion of enemy velocity for realistic ballistics
        vx = aim_dir[0] * proj_speed + self.vx * 0.4
        vy = aim_dir[1] * proj_speed + self.vy * 0.4
        vz = aim_dir[2] * proj_speed + self.vz * 0.4

        if global_projectiles is not None:
            global_projectiles.append({
                'x': self.x, 'y': self.y, 'z': self.z,
                'vx': vx, 'vy': vy, 'vz': vz,
                'life': 4.5  # seconds before auto-delete
            })

    def on_hit(self):
        self.hp -= 1
        self._flicker = 1