import random
from .math_engine import *
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

    def draw(self, surf, ppos, prot):
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

        cx, cy, cz = world_to_camera(self.x, self.y, self.z, *ppos, prot)

        if cz > 0:
            proj = project_to_screen(cx, cy, cz)
            if proj:
                sx, sy, scale = proj
                size = max(1, int(2 * scale))
                b = min(255, int(255 * self.brightness * min(1.0, 500 / (cz or 1))))
                pygame.draw.circle(surf, (255, 255, 255), (sx, sy), size)




