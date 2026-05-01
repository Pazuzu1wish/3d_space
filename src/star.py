import random
from src.math_engine import *
import pygame
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
        self.brightness = random.uniform(0.3, 1.0)

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
            b = min(255, int(255 * self.brightness * min(1.0, 500 / (cz or 1))))
            renderer.submit_sprite(self.x, self.y, self.z, (b, b, b), 2)




