import math
import random
import pygame
from src.math_engine import basis_from_forward
from src.constants import PLAYER_MISSILE_TURN_RATE

class PlayerMissile:
    def __init__(self, x, y, z, vx, vy, vz, life, damage, color=(200, 200, 200), size_mult=3.5, homing=False):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.vx = float(vx)
        self.vy = float(vy)
        self.vz = float(vz)
        self.life = float(life)
        self.damage = float(damage)
        self.color = color
        self.size_mult = float(size_mult)
        self.homing = homing

        self.px = self.x
        self.py = self.y
        self.pz = self.z

        # Engine trail (ship-style)
        self.engine_trail = []
        self.trail_life = 0.5
        self.trail_drift = 50.0
        self.engine_color = (255, 150, 50) if homing else (100, 180, 255)
        self.engine_size = 1.5
        
        # Missile geometry (low-poly mesh)
        C_BODY = (170, 170, 180)
        C_NOSE = (255, 30, 30) if homing else (40, 100, 255)
        C_DARK = (45, 45, 50)
        
        self.verts = {
            'v0': (0, 0, 15),       # Nose
            'v1': (-3.5, -3.5, -8), # Body corners
            'v2': (3.5, -3.5, -8),
            'v3': (3.5, 3.5, -8),
            'v4': (-3.5, 3.5, -8),
            'v5': (0, 0, -18),      # Engine tip
            # Fins
            'f0': (0, 9, -10),      # Top fin
            'f1': (0, -9, -10),     # Bot fin
            'f2': (9, 0, -10),      # Right fin
            'f3': (-9, 0, -10),     # Left fin
            'f4': (0, 0, -10),      # Fin root
        }
        self.faces = [
            # Nose cone
            {'v': ['v0', 'v3', 'v2'], 'color': C_NOSE},
            {'v': ['v0', 'v4', 'v3'], 'color': C_NOSE},
            {'v': ['v0', 'v1', 'v4'], 'color': C_NOSE},
            {'v': ['v0', 'v2', 'v1'], 'color': C_NOSE},
            # Tapered body
            {'v': ['v1', 'v2', 'v5'], 'color': C_BODY},
            {'v': ['v2', 'v3', 'v5'], 'color': C_BODY},
            {'v': ['v3', 'v4', 'v5'], 'color': C_BODY},
            {'v': ['v4', 'v1', 'v5'], 'color': C_BODY},
            # Fins (Dark contrast)
            {'v': ['f4', 'v3', 'f0'], 'color': C_DARK},
            {'v': ['f4', 'f0', 'v4'], 'color': C_DARK},
            {'v': ['f4', 'v1', 'f1'], 'color': C_DARK},
            {'v': ['f4', 'f1', 'v2'], 'color': C_DARK},
            {'v': ['f4', 'v2', 'f2'], 'color': C_DARK},
            {'v': ['f4', 'f2', 'v3'], 'color': C_DARK},
            {'v': ['f4', 'v4', 'f3'], 'color': C_DARK},
            {'v': ['f4', 'f3', 'v1'], 'color': C_DARK},
        ]

    def update(self, dt):
        self.px = self.x
        self.py = self.y
        self.pz = self.z

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self.life -= dt
        
        self._spawn_engine_trail()
        self._update_engine_trail(dt)

    def _spawn_engine_trail(self):
        # Spawn trail at the back of the missile
        dvx = (random.random() - 0.5) * self.trail_drift
        dvy = (random.random() - 0.5) * self.trail_drift
        dvz = (random.random() - 0.5) * self.trail_drift
        self.engine_trail.append([self.x, self.y, self.z, dvx, dvy, dvz, self.trail_life, self.engine_color, self.engine_size])

    def _update_engine_trail(self, dt):
        for p in self.engine_trail:
            p[0] += p[3] * dt
            p[1] += p[4] * dt
            p[2] += p[5] * dt
            p[6] -= dt
        self.engine_trail = [p for p in self.engine_trail if p[6] > 0]

    def _submit_engine_trail(self, renderer):
        for x, y, z, vx, vy, vz, life, color, base_size in self.engine_trail:
            ratio = max(0.0, life / self.trail_life)
            r = int(color[0] * ratio)
            g = int(color[1] * ratio)
            b = int(color[2] * ratio)
            renderer.submit_sprite(x, y, z, (r, g, b), base_size * 6 * ratio, layer='alpha')

    def submit_to_renderer(self, renderer):
        # 1. Engine Trail
        self._submit_engine_trail(renderer)

        # 2. Geometry
        spd = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2) or 1.0
        fwd = (self.vx/spd, self.vy/spd, self.vz/spd)
        f, r, u = basis_from_forward(fwd)
        renderer.submit_mesh((self.x, self.y, self.z), r, u, f, self.verts, self.faces, radius=50)

        # 3. Glow & Core (tuned down to reveal geometry)
        pulse = (math.sin(pygame.time.get_ticks() * 0.02) + 1.0) * 0.5
        glow_size = self.size_mult * (3.0 + pulse * 2.0)
        glow_color = (255, 120, 30) if self.homing else (100, 180, 255)
        renderer.submit_sprite(self.x, self.y, self.z, glow_color, glow_size)
        renderer.submit_sprite(self.x, self.y, self.z, (255, 255, 255), self.size_mult * 1.5)

    def check_collisions(self, enemies, asteroids, spatial, particle_pool):
        # Increased query radius for better reliability with larger objects
        nearby = spatial.query_nearby((self.x, self.y, self.z), 800.0)
        for obj in nearby:
            if obj in enemies or obj in asteroids:
                dist_sq = (self.x - obj.x)**2 + (self.y - obj.y)**2 + (self.z - obj.z)**2
                rad = getattr(obj, 'hit_radius', 80)
                # Slightly larger collision buffer for missiles
                if dist_sq < (rad + 50)**2:
                    if hasattr(obj, 'on_hit'):
                        obj.on_hit(self.damage)
                    self.life = 0
                    for _ in range(35):
                        particle_pool.spawn(self.x, self.y, self.z)
                    return True
        return False

class HomingMissile(PlayerMissile):
    def __init__(self, x, y, z, vx, vy, vz, life, damage, target):
        super().__init__(
            x, y, z, vx, vy, vz,
            life=life, damage=damage, color=(255, 100, 50), size_mult=4.0, homing=True
        )
        self.target = target

    def update(self, dt):
        if self.target and self.target.hp > 0:
            dx = self.target.x - self.x
            dy = self.target.y - self.y
            dz = self.target.z - self.z
            dist_sq = dx * dx + dy * dy + dz * dz
            dist = math.sqrt(dist_sq) if dist_sq > 0 else 1

            turn_rate = PLAYER_MISSILE_TURN_RATE * dt

            spd = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2) or 1

            new_nx = (self.vx / spd) + (dx / dist) * turn_rate
            new_ny = (self.vy / spd) + (dy / dist) * turn_rate
            new_nz = (self.vz / spd) + (dz / dist) * turn_rate

            new_norm = math.sqrt(new_nx**2 + new_ny**2 + new_nz**2) or 1
            self.vx = (new_nx / new_norm) * spd
            self.vy = (new_ny / new_norm) * spd
            self.vz = (new_nz / new_norm) * spd

        super().update(dt)
