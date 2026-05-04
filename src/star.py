import random

# ─────────────────────────────────────────────
#  GAME ENTITIES
# ──────────────────────────────────────────────

class Star:
    def __init__(self, ppos=(0, 0, 0)):
        self.spawn_around(ppos)

    def spawn_around(self, ppos):
        spread = 3000
        self.x = ppos[0] + random.uniform(-spread, spread)
        self.y = ppos[1] + random.uniform(-spread, spread)
        self.z = ppos[2] + random.uniform(-spread, spread)
        
        # Randomize size: mostly small (1-2), occasionally larger (3-5)
        if random.random() < 0.95:
            self.size = random.uniform(1.0, 2.0)
        else:
            self.size = random.uniform(3.0, 6.0) # Occasional "Hero" stars

        self.brightness = random.uniform(0.5, 1.0)
        
        # Color variety based on weighted probabilities
        # Mostly white/off-white, occasional blue/red/yellow
        c_rand = random.random()
        if c_rand < 0.75:
            self.base_color = (255, 255, 255) # White
        elif c_rand < 0.85:
            self.base_color = (100, 100, 255) # Blue-ish
        elif c_rand < 0.95:
            self.base_color = (255, 100, 100) # Red-ish
        else:
            self.base_color = (255, 255, 100) # Yellow-ish

    def submit_to_renderer(self, renderer, ppos):
        spread = 3000
        dx = self.x - ppos[0]
        dy = self.y - ppos[1]
        dz = self.z - ppos[2]

        if dx > spread: self.x -= 2 * spread
        elif dx < -spread: self.x += 2 * spread
        if dy > spread: self.y -= 2 * spread
        elif dy < -spread: self.y += 2 * spread
        if dz > spread: self.z -= 2 * spread
        elif dz < -spread: self.z += 2 * spread

        cx, cy, cz = renderer.camera.world_to_camera(self.x, self.y, self.z)

        if cz > 0:
            # Distance-based dimming
            dist_factor = min(1.0, 500 / (cz or 1))
            intensity = self.brightness * dist_factor
            
            r = min(255, int(self.base_color[0] * intensity))
            g = min(255, int(self.base_color[1] * intensity))
            b = min(255, int(self.base_color[2] * intensity))
            
            is_glow = self.size > 2.5
            renderer.submit_sprite(self.x, self.y, self.z, (r, g, b), self.size, is_glow=is_glow)




