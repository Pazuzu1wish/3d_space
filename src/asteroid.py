import math
import random
import numpy as np
import pygame

# Import the BakedMesh class we created earlier
from src.mesh_loader import BakedMesh 
from src.math_engine import world_to_camera
from src.constants import (
    ASTEROID_MIN_HP, ASTEROID_MAX_HP, ASTEROID_DAMAGE,
    ASTEROID_MIN_SCALE, ASTEROID_MAX_SCALE,
    ASTEROID_ROTATION_SPEED_MAX, ASTEROID_DRIFT_SPEED_MAX,
    ASTEROID_PARTICLES_ON_DESTROY
)

# ──────────────────────────────────────────────
#  ASTEROID MESH BANK (Generated once at startup)
# ──────────────────────────────────────────────

ASTEROID_MESH_BANK = []

def init_asteroid_bank(variations=20):
    """Generates a pool of baked asteroid meshes with varied shapes and colors."""
    global ASTEROID_MESH_BANK
    ASTEROID_MESH_BANK.clear()
    
    phi = (1 + 5**0.5) / 2
    raw_verts = [
        (-1,  phi, 0), ( 1,  phi, 0), (-1, -phi, 0), ( 1, -phi, 0),
        (0, -1,  phi), (0,  1,  phi), (0, -1, -phi), (0,  1, -phi),
        ( phi, 0, -1), ( phi, 0,  1), (-phi, 0, -1), (-phi, 0,  1)
    ]
    raw_faces = [
        (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
        (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
        (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
        (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)
    ]

    for _ in range(variations):
        # 1. Pick a base color theme
        rand = random.random()
        if rand < 0.7:
            # Grayish
            c = random.randint(100, 140)
            base_color = (c, c, c + random.randint(-10, 10))
        elif rand < 0.85:
            # Reddish (Iron)
            base_color = (random.randint(130, 170), random.randint(80, 110), random.randint(70, 90))
        else:
            # Brownish
            base_color = (random.randint(120, 150), random.randint(100, 130), random.randint(60, 90))

        # 2. Jitter vertices to create a unique rock shape
        jittered_verts = []
        for vx, vy, vz in raw_verts:
            length = math.sqrt(vx*vx + vy*vy + vz*vz)
            nx, ny, nz = vx/length, vy/length, vz/length
            j = 1.0 + random.uniform(-0.25, 0.25)
            # Notice we do NOT scale here. The mesh is generated at unit size (radius ~1.0)
            # The renderer will scale it on the GPU side.
            jittered_verts.append([nx * j, ny * j, nz * j])

        # 3. Assign flat-shaded colors to faces
        f_idx = []
        f_col = []
        for idxs in raw_faces:
            shade = 0.5 + (random.random() * 0.5)
            r = max(0, min(255, int(base_color[0] * shade)))
            g = max(0, min(255, int(base_color[1] * shade)))
            b = max(0, min(255, int(base_color[2] * shade)))
            
            f_idx.append(list(idxs))
            f_col.append([r, g, b])

        v_data = np.array(jittered_verts, dtype=np.float64)
        
        # Max distance from origin becomes the collision/culling radius
        max_radius = float(np.max(np.linalg.norm(v_data, axis=1)))

        mesh = BakedMesh(
            v_data=v_data,
            f_idx=np.array(f_idx, dtype=np.int32),
            f_col=np.array(f_col, dtype=np.int32),
            radius=max_radius
        )
        ASTEROID_MESH_BANK.append(mesh)

# ──────────────────────────────────────────────
#  ASTEROID CLASS
# ──────────────────────────────────────────────

class Asteroid:
    def __init__(self, x, y, z, scale=None, generation=0, mesh=None):
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.scale = scale if scale else random.uniform(ASTEROID_MIN_SCALE, ASTEROID_MAX_SCALE)
        self.generation = generation
        
        # ⚡ The core optimization: share a pre-baked mesh pointer!
        # If no mesh is provided (e.g., initial spawn), pick a random one from the bank.
        if mesh is None:
            self.mesh = random.choice(ASTEROID_MESH_BANK)
        else:
            self.mesh = mesh
            
        # Physics
        base_hp = random.randint(ASTEROID_MIN_HP, ASTEROID_MAX_HP)
        self.hp = base_hp if generation == 0 else max(1, int(base_hp * 0.5))
        self.max_hp = self.hp
        
        # Use the baked mesh's native radius scaled by our asteroid size!
        self.hit_radius = self.mesh.radius * self.scale * 0.8
        
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
        impulse_mag = 450.0  
        
        last_dx, last_dy, last_dz = 0, 0, 0
        
        for i in range(num_fragments):
            if i == 0:
                theta = random.uniform(0, 2 * math.pi)
                phi = random.uniform(0, math.pi)
                dx = math.sin(phi) * math.cos(theta)
                dy = math.sin(phi) * math.sin(theta)
                dz = math.cos(phi)
                last_dx, last_dy, last_dz = dx, dy, dz
            elif i == 1:
                dx, dy, dz = -last_dx, -last_dy, -last_dz
            else:
                theta = random.uniform(0, 2 * math.pi)
                phi = random.uniform(0, math.pi)
                dx = math.sin(phi) * math.cos(theta)
                dy = math.sin(phi) * math.sin(theta)
                dz = math.cos(phi)

            f_scale = self.scale * random.uniform(0.3, 0.5)
            offset = f_scale * 0.5
            
            # ⚡ Pass `self.mesh` to the fragment! 
            # A broken rock fragment should look like the parent rock.
            f = Asteroid(self.x + dx * offset, self.y + dy * offset, self.z + dz * offset, 
                         scale=f_scale, generation=self.generation + 1, mesh=self.mesh)
            
            f.vx = self.vx + dx * impulse_mag
            f.vy = self.vy + dy * impulse_mag
            f.vz = self.vz + dz * impulse_mag
            
            f.rot_vel_x *= 2.0
            f.rot_vel_y *= 2.0
            f.rot_vel_z *= 2.0
            
            fragments.append(f)
        return fragments

    def submit_to_renderer(self, renderer):
        cx, sx = math.cos(self.angle_x), math.sin(self.angle_x)
        cy, sy = math.cos(self.angle_y), math.sin(self.angle_y)
        cz, sz = math.cos(self.angle_z), math.sin(self.angle_z)

        # Right (1, 0, 0)
        rx = cy * cz - sy * sx * sz
        ry = cy * sz + sy * sx * cz
        rz = -sy * cx
        # Up (0, 1, 0)
        ux = -cx * sz
        uy = cx * cz
        uz = sx
        # Forward (0, 0, 1)
        fx = sy * cz + cy * sx * sz
        fy = sy * sz - cy * sx * cz
        fz = cy * cx

        # ⚡ Send directly to the fast-path! 
        renderer.submit_baked_mesh(
            (self.x, self.y, self.z),
            (rx, ry, rz), (ux, uy, uz), (fx, fy, fz),
            self.mesh,
            layer='opaque',
            scale=self.scale
        )

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