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
        cx, cy, cz = world_to_camera(self.x, self.y, self.z, *ppos, prot)

        if cz < -100:
            fx, fy, fz = get_forward_from_quat(prot)
            dist = random.uniform(2000, 4000)
            self.x = ppos[0] + fx * dist + random.uniform(-1500, 1500)
            self.y = ppos[1] + fy * dist + random.uniform(-1500, 1500)
            self.z = ppos[2] + fz * dist + random.uniform(-1500, 1500)
            return

        proj = project_to_screen(cx, cy, cz)
        if proj:
            sx, sy, scale = proj
            size = max(1, int(2 * scale))
            b = min(255, int(255 * self.brightness * min(1.0, 500 / (cz or 1))))
            pygame.draw.circle(surf, (b, b, b), (sx, sy), size)




