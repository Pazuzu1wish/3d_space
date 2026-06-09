import math
import pygame
from src.math_engine import world_to_camera, project_to_screen
from src.constants import HOMING_TURN_RATE, PARTICLES_ON_HIT, PLAYER_COLLISION_RADIUS
class EnemyProjectile:
    def __init__(self, x, y, z, vx, vy, vz, life, damage, color, size_mult, homing=False, owner=None):
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
        self.owner = owner  # Reference to the enemy that fired this projectile

    def update(self, dt, player_pos):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self.life -= dt

    def submit_to_renderer(self, renderer):
        renderer.submit_sprite(self.x, self.y, self.z, self.color, self.size_mult * 2)

        # If it's a homing bolt, draw an inner white core to make it look intense
        if self.homing and self.size_mult * 2 > 2:
            renderer.submit_sprite(self.x, self.y, self.z, (255, 255, 255), self.size_mult)

    def check_player_collision(self, player, particles):
        """Check if this projectile hits the player. Returns True if collision occurred."""
        dist = math.dist((self.x, self.y, self.z), player.pos)
        if dist < PLAYER_COLLISION_RADIUS:
            player.take_damage(self.damage)
            self.life = 0
            for _ in range(12):
                particles.spawn(self.x, self.y, self.z)
            return True
        return False

    def check_asteroid_collision(self, spatial, particles):
        """Check if this projectile hits an asteroid. Returns True if collision occurred."""
        # Using a fixed radius to check for asteroid proximity
        nearby = spatial.query_nearby((self.x, self.y, self.z), 500.0)
        
        for obj in nearby:
            if hasattr(obj, 'is_hit') and obj.is_hit(self.x, self.y, self.z):
                if hasattr(obj, 'on_hit'):
                    obj.on_hit(1) # Damage the asteroid
                
                self.life = 0
                for _ in range(PARTICLES_ON_HIT):
                    particles.spawn(self.x, self.y, self.z)
                return True
        return False

    def check_enemy_collision(self, spatial, particles):
        """Check if this projectile hits an enemy (excluding the owner). Returns True if collision occurred."""
        # Using a fixed radius to check for enemy proximity
        nearby = spatial.query_nearby((self.x, self.y, self.z), 500.0)

        for obj in nearby:
            # Skip if this is the owner of the projectile (no friendly fire on self)
            if obj is self.owner:
                continue
            # Check if it's an enemy (has hit_radius and on_hit methods)
            if hasattr(obj, 'hit_radius') and hasattr(obj, 'on_hit'):
                # Don't collide with asteroids (they have 'split' method)
                if hasattr(obj, 'split'):
                    continue
                # Use spherical collision check
                dx = self.x - obj.x
                dy = self.y - obj.y
                dz = self.z - obj.z
                dist_sq = dx * dx + dy * dy + dz * dz
                if dist_sq < (obj.hit_radius ** 2):
                    obj.on_hit(int(self.damage))
                    self.life = 0
                    for _ in range(PARTICLES_ON_HIT):
                        particles.spawn(self.x, self.y, self.z)
                    return True
        return False

class MachineGunBolt(EnemyProjectile):
    def __init__(self, x, y, z, vx, vy, vz):
        super().__init__(
            x, y, z, vx, vy, vz,
            life=3.0, damage=4.25, color=(255, 200, 50), size_mult=0.7, homing=False
        )


class HomingBolt(EnemyProjectile):
    def __init__(self, x, y, z, vx, vy, vz):
        super().__init__(
            x, y, z, vx, vy, vz,
            life=6.0, damage=50.0, color=(200, 50, 255), size_mult=2.5, homing=True
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
            life=5.0, damage=0.0, color=(255, 30, 30), size_mult=6.0, homing=False
        )


class CorvetteTurret(EnemyProjectile):
    def __init__(self, x, y, z, vx, vy, vz):
        super().__init__(
            x, y, z, vx, vy, vz,
            life=4.0, damage=5.0, color=(50, 255, 50), size_mult=1.5, homing=False
        )


class StealthShotgun(EnemyProjectile):
    def __init__(self, x, y, z, vx, vy, vz):
        super().__init__(
            x, y, z, vx, vy, vz,
            life=1.5, damage=8.0, color=(100, 100, 255), size_mult=1.2, homing=False
        )
