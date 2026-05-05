import math
import random
import pygame
from src.math_engine import world_to_camera
from src.constants import (
    ASTEROID_MIN_HP, ASTEROID_MAX_HP, ASTEROID_DAMAGE,
    ASTEROID_MIN_SCALE, ASTEROID_MAX_SCALE,
    ASTEROID_ROTATION_SPEED_MAX, ASTEROID_DRIFT_SPEED_MAX,
    ASTEROID_PARTICLES_ON_DESTROY
)

class Asteroid:
    def __init__(self, x, y, z, scale=None):
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.scale = scale if scale else random.uniform(ASTEROID_MIN_SCALE, ASTEROID_MAX_SCALE)
        
        # Physics
        self.hp = random.randint(ASTEROID_MIN_HP, ASTEROID_MAX_HP)
        self.max_hp = self.hp
        self.hit_radius = self.scale * 0.8
        
        # Movement
        self.vx = random.uniform(-ASTEROID_DRIFT_SPEED_MAX, ASTEROID_DRIFT_SPEED_MAX)
        self.vy = random.uniform(-ASTEROID_DRIFT_SPEED_MAX, ASTEROID_DRIFT_SPEED_MAX)
        self.vz = random.uniform(-ASTEROID_DRIFT_SPEED_MAX, ASTEROID_DRIFT_SPEED_MAX)
        
        # Rotation
        self.angle_x = random.uniform(0, math.pi * 2)
        self.angle_y = random.uniform(0, math.pi * 2)
        self.angle_z = random.uniform(0, math.pi * 2)
        
        self.rot_vel_x = random.uniform(-ASTEROID_ROTATION_SPEED_MAX, ASTEROID_ROTATION_SPEED_MAX)
        self.rot_vel_y = random.uniform(-ASTEROID_ROTATION_SPEED_MAX, ASTEROID_ROTATION_SPEED_MAX)
        self.rot_vel_z = random.uniform(-ASTEROID_ROTATION_SPEED_MAX, ASTEROID_ROTATION_SPEED_MAX)
        
        # Visuals
        self.base_color = (random.randint(100, 140), random.randint(90, 120), random.randint(80, 110))
        self.verts, self.faces = self._generate_mesh()
        
    def _generate_mesh(self):
        # Start with an octahedron
        # 6 vertices
        raw_verts = [
            (0, 0, 1), (0, 0, -1),
            (1, 0, 0), (-1, 0, 0),
            (0, 1, 0), (0, -1, 0)
        ]
        
        # Jitter vertices for rocky look
        jittered = []
        for vx, vy, vz in raw_verts:
            j = 1.0 + random.uniform(-0.3, 0.3)
            jittered.append((vx * j * self.scale, vy * j * self.scale, vz * j * self.scale))
            
        # 8 faces
        faces = [
            {'v': [0, 2, 4], 'color': self._adjust_color(0.9)},
            {'v': [0, 4, 3], 'color': self._adjust_color(0.8)},
            {'v': [0, 3, 5], 'color': self._adjust_color(0.7)},
            {'v': [0, 5, 2], 'color': self._adjust_color(0.85)},
            {'v': [1, 4, 2], 'color': self._adjust_color(0.6)},
            {'v': [1, 3, 4], 'color': self._adjust_color(0.5)},
            {'v': [1, 5, 3], 'color': self._adjust_color(0.55)},
            {'v': [1, 2, 5], 'color': self._adjust_color(0.65)},
        ]
        
        return jittered, faces

    def _adjust_color(self, factor):
        r, g, b = self.base_color
        return (int(r * factor), int(g * factor), int(b * factor))

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        
        self.angle_x += self.rot_vel_x * dt
        self.angle_y += self.rot_vel_y * dt
        self.angle_z += self.rot_vel_z * dt

    def is_hit(self, px, py, pz):
        dx, dy, dz = self.x - px, self.y - py, self.z - pz
        return (dx * dx + dy * dy + dz * dz) < (self.hit_radius ** 2)

    def on_hit(self, damage=1):
        self.hp -= damage
        # Visual feedback: flash brighter? 
        # For now, just HP reduction.

    def submit_to_renderer(self, renderer):
        # Rotation matrices
        cx, sx = math.cos(self.angle_x), math.sin(self.angle_x)
        cy, sy = math.cos(self.angle_y), math.sin(self.angle_y)
        cz, sz = math.cos(self.angle_z), math.sin(self.angle_z)
        
        world_verts = []
        for vx, vy, vz in self.verts:
            # Rotate Y
            tx = vx * cy + vz * sy
            tz = -vx * sy + vz * cy
            vx, vz = tx, tz
            
            # Rotate X
            ty = vy * cx - vz * sx
            tz = vy * sx + vz * cx
            vy, vz = ty, tz
            
            # Rotate Z
            tx = vx * cz - vy * sz
            ty = vx * sz + vy * cz
            vx, vy = tx, ty
            
            world_verts.append((self.x + vx, self.y + vy, self.z + vz))
            
        for f in self.faces:
            pts = [world_verts[idx] for idx in f['v']]
            renderer.submit_polygon(pts, f['color'])

class AsteroidField:
    def __init__(self, origin, count=10, radius=2000):
        self.origin = origin
        self.asteroids = []
        ox, oy, oz = origin
        
        for _ in range(count):
            ax = ox + random.uniform(-radius, radius)
            ay = oy + random.uniform(-radius, radius)
            az = oz + random.uniform(-radius, radius)
            self.asteroids.append(Asteroid(ax, ay, az))
