import math
import pygame

class PlayerMissile:
    def __init__(self, x, y, z, vx, vy, vz, life, damage, color=(200, 200, 200), size_mult=1.5, homing=False):
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

        self.px = self.x
        self.py = self.y
        self.pz = self.z

    def update(self, dt):
        self.px = self.x
        self.py = self.y
        self.pz = self.z

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self.life -= dt

    def submit_to_renderer(self, renderer):
        # Draw trail
        renderer.submit_line((self.px, self.py, self.pz), (self.x, self.y, self.z), self.color, int(self.size_mult * 4))
        # Draw missile core
        renderer.submit_sprite(self.x, self.y, self.z, (255, 255, 255), self.size_mult * 2)

    def check_enemy_collision(self, enemies, spatial, particle_pool):
        nearby = spatial.query_nearby((self.x, self.y, self.z), 500.0)
        for obj in nearby:
            if obj in enemies:
                dist_sq = (self.x - obj.x)**2 + (self.y - obj.y)**2 + (self.z - obj.z)**2
                rad = getattr(obj, 'hit_radius', 80)
                if dist_sq < (rad + 20)**2:
                    if hasattr(obj, 'on_hit'):
                        obj.on_hit(self.damage)
                    self.life = 0
                    for _ in range(25):
                        particle_pool.spawn(self.x, self.y, self.z)
                    return True
        return False

class HomingMissile(PlayerMissile):
    def __init__(self, x, y, z, vx, vy, vz, life, damage, target):
        super().__init__(
            x, y, z, vx, vy, vz,
            life=life, damage=damage, color=(255, 100, 50), size_mult=2.0, homing=True
        )
        self.target = target

    def update(self, dt):
        from src.constants import PLAYER_MISSILE_TURN_RATE
        if self.target and self.target.hp > 0:
            dx = self.target.x - self.x
            dy = self.target.y - self.y
            dz = self.target.z - self.z
            dist_sq = dx * dx + dy * dy + dz * dz
            dist = math.sqrt(dist_sq) if dist_sq > 0 else 1

            turn_rate = PLAYER_MISSILE_TURN_RATE * dt

            spd = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2) or 1

            new_nx = (self.vx / spd) + (dx / dist) * turn_rate
            new_ny = (self.vy / spd) + (dy / dist) * turn_rate
            new_nz = (self.vz / spd) + (dz / dist) * turn_rate

            new_norm = math.sqrt(new_nx**2 + new_ny**2 + new_nz**2) or 1
            self.vx = (new_nx / new_norm) * spd
            self.vy = (new_ny / new_norm) * spd
            self.vz = (new_nz / new_norm) * spd

        super().update(dt)
