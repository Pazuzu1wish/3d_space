from .math_engine import *
import pygame


class Enemy:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z
        self.hp = 3
        self.verts = [
            (0, 0, 40),  # Nose
            (-20, 0, -20),  # Left Wing
            (20, 0, -20),  # Right Wing
            (0, -15, -20),  # Top Fin
            (0, 10, -15)  # Bottom Belly
        ]
        self.edges = [(0, 1), (0, 2), (0, 3), (0, 4), (1, 2), (1, 3), (2, 3), (1, 4), (2, 4)]

    def draw(self, surf, ppos, prot):
        projected = {}
        for i, (vx, vy, vz) in enumerate(self.verts):
            cx, cy, cz = world_to_camera(self.x + vx, self.y + vy, self.z + vz, *ppos, prot)
            proj = project_to_screen(cx, cy, cz)
            if proj: projected[i] = proj

        if len(projected) == len(self.verts):
            color = (255, 80, 80) if self.hp > 1 else (255, 200, 80)
            for p1, p2 in self.edges:
                sx1, sy1, _ = projected[p1]
                sx2, sy2, _ = projected[p2]
                pygame.draw.line(surf, color, (sx1, sy1), (sx2, sy2), 2)
