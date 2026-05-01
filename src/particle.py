import random
from src.math_engine import *
import pygame



class Particle:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z
        self.vx = random.uniform(-300, 300)
        self.vy = random.uniform(-300, 300)
        self.vz = random.uniform(-300, 300)
        self.life = 1.0
        self.color = random.choice([(255, 100, 50), (255, 200, 50), (100, 100, 100)])

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self.life -= dt

    def submit_to_renderer(self, renderer):
        renderer.submit_sprite(self.x, self.y, self.z, self.color, 15 * self.life)
