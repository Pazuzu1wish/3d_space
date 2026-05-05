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
    def __init__(self, x, y, z, scale=None, generation=0, base_color=None):
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.scale = scale if scale else random.uniform(ASTEROID_MIN_SCALE, ASTEROID_MAX_SCALE)
        self.generation = generation
        
        # Physics
        # HP scales with size, but fragments are easier to break
        base_hp = random.randint(ASTEROID_MIN_HP, ASTEROID_MAX_HP)
        self.hp = base_hp if generation == 0 else max(1, int(base_hp * 0.5))
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
        if base_color:
            self.base_color = base_color
        else:
            # randomized color logic for top-level asteroids
            # 70% Gray, 15% Reddish/Iron, 15% Brownish
            rand = random.random()
            if rand < 0.7:
                # Grayish
                c = random.randint(100, 140)
                self.base_color = (c, c, c + random.randint(-10, 10))
            elif rand < 0.85:
                # Reddish (Iron)
                self.base_color = (random.randint(130, 170), random.randint(80, 110), random.randint(70, 90))
            else:
                # Brownish
                self.base_color = (random.randint(120, 150), random.randint(100, 130), random.randint(60, 90))
            
        self.verts, self.faces = self._generate_mesh()
        
    def _generate_mesh(self):
        # Start with an icosahedron for more roundness
        phi = (1 + 5**0.5) / 2
        raw_verts = [
            (-1,  phi, 0), ( 1,  phi, 0), (-1, -phi, 0), ( 1, -phi, 0),
            (0, -1,  phi), (0,  1,  phi), (0, -1, -phi), (0,  1, -phi),
            ( phi, 0, -1), ( phi, 0,  1), (-phi, 0, -1), (-phi, 0,  1)
        ]
        
        # Jitter and scale vertices
        jittered = []
        for vx, vy, vz in raw_verts:
            # Normalize to sphere and then jitter
            length = math.sqrt(vx*vx + vy*vy + vz*vz)
            nx, ny, nz = vx/length, vy/length, vz/length
            j = 1.0 + random.uniform(-0.25, 0.25)
            jittered.append((nx * j * self.scale, ny * j * self.scale, nz * j * self.scale))
            
        # 20 faces
        raw_faces = [
            (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
            (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
            (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
            (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)
        ]
        
        faces = []
        for idxs in raw_faces:
            # Simple flat shading variety based on face index
            shade = 0.5 + (random.random() * 0.5)
            faces.append({'v': list(idxs), 'color': self._adjust_color(shade)})
            
        return jittered, faces

    def _adjust_color(self, factor):
        r, g, b = self.base_color
        return (max(0, min(255, int(r * factor))), 
                max(0, min(255, int(g * factor))), 
                max(0, min(255, int(b * factor))))

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

    def split(self):
        """Create smaller fragments that explode away from each other."""
        if self.generation >= 1: # Limit to one level of splitting for performance
            return []
            
        fragments = []
        num_fragments = random.randint(2, 4)
        impulse_mag = 450.0  # High velocity for satisfying "shatter"
        
        last_dx, last_dy, last_dz = 0, 0, 0
        
        for i in range(num_fragments):
            if i == 0:
                # Pick a random direction on a sphere
                theta = random.uniform(0, 2 * math.pi)
                phi = random.uniform(0, math.pi)
                dx = math.sin(phi) * math.cos(theta)
                dy = math.sin(phi) * math.sin(theta)
                dz = math.cos(phi)
                last_dx, last_dy, last_dz = dx, dy, dz
            elif i == 1:
                # Force the second fragment to go in the opposite direction
                dx, dy, dz = -last_dx, -last_dy, -last_dz
            else:
                # Further fragments get fresh random directions
                theta = random.uniform(0, 2 * math.pi)
                phi = random.uniform(0, math.pi)
                dx = math.sin(phi) * math.cos(theta)
                dy = math.sin(phi) * math.sin(theta)
                dz = math.cos(phi)

            f_scale = self.scale * random.uniform(0.3, 0.5)
            # Offset position slightly so they don't overlap immediately
            offset = f_scale * 0.5
            f = Asteroid(self.x + dx * offset, self.y + dy * offset, self.z + dz * offset, 
                         scale=f_scale, generation=self.generation + 1, base_color=self.base_color)
            
            # Inherit parent velocity and add outward impulse
            f.vx = self.vx + dx * impulse_mag
            f.vy = self.vy + dy * impulse_mag
            f.vz = self.vz + dz * impulse_mag
            
            # Increase rotation speed of fragments for chaos
            f.rot_vel_x *= 2.0
            f.rot_vel_y *= 2.0
            f.rot_vel_z *= 2.0
            
            fragments.append(f)
        return fragments

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
