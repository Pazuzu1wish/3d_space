from .math_engine import *
import pygame

class Laser:
    def __init__(self, ppos, prot):
        fx, fy, fz = get_forward_from_quat(prot)
        # Start laser slightly ahead of the ship so it doesn't clip the camera
        self.x = ppos[0] + fx * 50
        self.y = ppos[1] + fy * 50
        self.z = ppos[2] + fz * 50

        # Track previous position to draw as a line (blaster bolt)
        self.px, self.py, self.pz = self.x, self.y, self.z

        speed = 5000
        self.vx, self.vy, self.vz = fx * speed, fy * speed, fz * speed
        self.life = 1.0

    def update(self, dt):
        self.px, self.py, self.pz = self.x, self.y, self.z
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self.life -= dt

    def draw(self, surf, ppos, prot):
        # Project both the head and the tail of the laser
        cx1, cy1, cz1 = world_to_camera(self.px, self.py, self.pz, *ppos, prot)
        cx2, cy2, cz2 = world_to_camera(self.x, self.y, self.z, *ppos, prot)

        proj1 = project_to_screen(cx1, cy1, cz1)
        proj2 = project_to_screen(cx2, cy2, cz2)

        if proj1 and proj2:
            pygame.draw.line(surf, (100, 255, 100), (proj1[0], proj1[1]), (proj2[0], proj2[1]), 4)
