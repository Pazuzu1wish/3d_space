import random
import math

class NebulaCloud:
    def __init__(self, x, y, z, color=None, num_puffs=10, radius=1000):
        self.x, self.y, self.z = x, y, z
        
        # Vibrant Nebula Palette
        palette = [
            (180, 50, 255), # Purple
            (50, 255, 220), # Teal
            (50, 100, 255), # Deep Blue
            (255, 100, 50), # Orange
            (255, 50, 150), # Pink
            (100, 255, 50)  # Green
        ]
        self.color = color if color else random.choice(palette)
        
        self.puffs = []
        for _ in range(num_puffs):
            # Random offset within the cloud radius
            ox = random.uniform(-radius, radius)
            oy = random.uniform(-radius, radius)
            oz = random.uniform(-radius, radius)
            
            # Random size for each puff
            p_size = random.uniform(radius * 0.5, radius * 1.5)
            # Random alpha for variety
            p_alpha = random.randint(20, 50)
            
            self.puffs.append({
                'rel_pos': (ox, oy, oz),
                'size': p_size,
                'alpha': p_alpha
            })
            
    def submit_to_renderer(self, renderer):
        for p in self.puffs:
            px = self.x + p['rel_pos'][0]
            py = self.y + p['rel_pos'][1]
            pz = self.z + p['rel_pos'][2]
            renderer.submit_nebula(px, py, pz, self.color, p['size'], p['alpha'])

class NebulaSystem:
    def __init__(self, count=5, area_radius=15000):
        self.clouds = []
        for _ in range(count):
            # Spawn clouds in a large area around the scene
            nx = random.uniform(-area_radius, area_radius)
            ny = random.uniform(-area_radius, area_radius)
            nz = random.uniform(2000, area_radius * 2) # Mostly in front
            
            self.clouds.append(NebulaCloud(nx, ny, nz, radius=random.uniform(2000, 5000)))
            
    def submit_to_renderer(self, renderer):
        for cloud in self.clouds:
            cloud.submit_to_renderer(renderer)
