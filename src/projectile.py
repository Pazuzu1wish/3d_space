import math
import pygame
from src.math_engine import world_to_camera, project_to_screen
from src.constants import HOMING_TURN_RATE

class EnemyProjectile:
    def __init__(self, x, y, z, vx, vy, vz, life, damage, color, size_mult, homing=False):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.vx = float(vx)
        self.vy = float(vy)
        self.vz = float(vz)
        self.life = float(life)
        self.damage = float(damage)
        self.color = color
        self.size_mult = float(size_mult)
        self.homing = homing

    def update(self, dt, player_pos):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self.life -= dt

    def draw(self, surf, ppos, prot):
        cx, cy, cz = world_to_camera(self.x, self.y, self.z, *ppos, prot)
        proj = project_to_screen(cx, cy, cz)
        if proj:
            sx, sy, scale = proj
            size = max(2, int(scale * 2 * self.size_mult))
            pygame.draw.circle(surf, self.color, (sx, sy), size)

            # If it's a homing bolt, draw an inner white core to make it look intense
            if self.homing and size > 2:
                pygame.draw.circle(surf, (255, 255, 255), (sx, sy), int(size / 2))


class MachineGunBolt(EnemyProjectile):
    def __init__(self, x, y, z, vx, vy, vz):
        super().__init__(
            x, y, z, vx, vy, vz,
            life=3.0, damage=0.25, color=(255, 200, 50), size_mult=0.7, homing=False
        )


class HomingBolt(EnemyProjectile):
    def __init__(self, x, y, z, vx, vy, vz):
        super().__init__(
            x, y, z, vx, vy, vz,
            life=6.0, damage=15.0, color=(200, 50, 255), size_mult=2.5, homing=True
        )

    def update(self, dt, player_pos):
        dx = player_pos[0] - self.x
        dy = player_pos[1] - self.y
        dz = player_pos[2] - self.z
        dist_sq = dx * dx + dy * dy + dz * dz
        dist = math.sqrt(dist_sq) if dist_sq > 0 else 1

        turn_rate = HOMING_TURN_RATE * dt

        spd = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2) or 1

        new_nx = (self.vx / spd) + (dx / dist) * turn_rate
        new_ny = (self.vy / spd) + (dy / dist) * turn_rate
        new_nz = (self.vz / spd) + (dz / dist) * turn_rate

        new_norm = math.sqrt(new_nx**2 + new_ny**2 + new_nz**2) or 1
        self.vx = (new_nx / new_norm) * spd
        self.vy = (new_ny / new_norm) * spd
        self.vz = (new_nz / new_norm) * spd

        super().update(dt, player_pos)


class SniperBeam(EnemyProjectile):
    def __init__(self, x, y, z, vx, vy, vz):
        super().__init__(
            x, y, z, vx, vy, vz,
            life=5.0, damage=70.0, color=(10, 255, 10), size_mult=6.0, homing=True
        )


class CorvetteTurret(EnemyProjectile):
    def __init__(self, x, y, z, vx, vy, vz):
        super().__init__(
            x, y, z, vx, vy, vz,
            life=4.0, damage=5.0, color=(50, 255, 50), size_mult=1.5, homing=False
        )


class Mine(EnemyProjectile):
    def __init__(self, x, y, z, vx, vy, vz):
        super().__init__(
            x, y, z, vx, vy, vz,
            life=25.0, damage=25.0, color=(255, 30, 30), size_mult=6.0, homing=False
        )


class StealthShotgun(EnemyProjectile):
    def __init__(self, x, y, z, vx, vy, vz):
        super().__init__(
            x, y, z, vx, vy, vz,
            life=1.5, damage=8.0, color=(100, 100, 255), size_mult=1.2, homing=False
        )
