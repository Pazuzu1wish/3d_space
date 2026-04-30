import pygame
import math
from .math_engine import (
    world_to_camera, project_to_screen
)
from .cockpit import draw_cockpit_hud
from .controller import DS4Input
from .star import Star
from .particle import Particle
from .player import Player
from .laser import Laser
from .constants import (
    HIT_FLASH_DURATION, PLAYER_COLLISION_RADIUS,
    ENEMY_HIT_RADIUS_SQ, ENEMY_CULL_DISTANCE, HOMING_TURN_RATE,
    PARTICLES_ON_HIT, PARTICLES_ON_DESTROY, PARTICLES_ON_PLAYER_HIT,
    COLLISION_DAMAGE, CAMERA_CLIP_NEAR, SNIPER_CHARGE_TIME,
    SNIPER_CHARGE_JITTER, SNIPER_CHARGE_CORE_THRESHOLD, SNIPER_GLARE_MULTIPLIER
)
from .utils import draw_damage_overlay
from .director import WaveDirector
from .encounters import ENCOUNTER_SCRIPT
from .object_pool import ParticlePool, LaserPool
from .spatial_partition import SpatialPartition

# ──────────────────────────────────────────────
# MAIN LOOP
# ──────────────────────────────────────────────

class Game:
    def __init__(self):
        pygame.init()
        self.W, self.H = 1280, 760
        self.screen = pygame.display.set_mode((self.W, self.H))
        pygame.display.set_caption("🚀 3D Cockpit Dogfighter")
        self.clock = pygame.time.Clock()

        self.handler = DS4Input()
        self.handler.init()

        self.player = Player()
        self.director = WaveDirector(ENCOUNTER_SCRIPT)

        # Initialize object pools for performance
        self.particle_pool = ParticlePool(Particle, initial_size=300, max_size=1500)
        self.laser_pool = LaserPool(Laser, initial_size=50, max_size=150)
        
        # Initialize spatial partitioning for collision detection
        self.spatial = SpatialPartition(world_size=20000.0, cell_size=500.0)

        self.stars = [Star(self.player.pos) for _ in range(250)]
        self.enemies = []
        self.enemy_projectiles = []

        self.running = True
        
        # Track which enemies are registered in spatial partition
        self._registered_enemies = set()

    def update_entities(self, dt, player, enemies, enemy_projectiles):
        # ── UPDATE LASERS (using pool) ─────────────────────────
        self.laser_pool.update(dt)
        
        # ── UPDATE PARTICLES (using pool) ──────────────────────
        self.particle_pool.update(dt)

        # ── UPDATE ENEMIES ────────────────────────
        for e in enemies[:]:
            e.update(dt, player.pos, player.orientation, enemy_projectiles, enemies)

            # Drone destroyed
            if e.hp <= 0:
                for _ in range(PARTICLES_ON_DESTROY):
                    self.particle_pool.spawn(e.x, e.y, e.z)
                # Remove from spatial partition
                self.spatial.unregister_entity(e)
                self._registered_enemies.discard(id(e))
                enemies.remove(e)
                continue

            # Collision with player
            if e.dist_to_player(player.pos) < PLAYER_COLLISION_RADIUS:
                player.take_damage(COLLISION_DAMAGE)
                for _ in range(PARTICLES_ON_PLAYER_HIT):
                    self.particle_pool.spawn(e.x, e.y, e.z)
                # Remove from spatial partition
                self.spatial.unregister_entity(e)
                self._registered_enemies.discard(id(e))
                enemies.remove(e)
                continue

            # Cull enemies far behind the camera
            _, _, cz = world_to_camera(
                e.x, e.y, e.z,
                player.pos[0], player.pos[1], player.pos[2],
                player.orientation,
            )
            if cz < ENEMY_CULL_DISTANCE:
                # Remove from spatial partition
                self.spatial.unregister_entity(e)
                self._registered_enemies.discard(id(e))
                enemies.remove(e)

        # ── REBUILD SPATIAL PARTITION (enemies have moved) ─────────
        # Re-register all remaining enemies at their current positions
        # Use each enemy's individual hit_radius for proper spatial partitioning
        self.spatial.clear()
        self._registered_enemies.clear()
        for e in enemies:
            self.spatial.register_entity(e, (e.x, e.y, e.z), radius=e.hit_radius)
            self._registered_enemies.add(id(e))

        # ── LASER HITS (spatial query) ─────────────────────────────
        # Use the dynamic is_hit() method for flexible collision detection
        for l in self.laser_pool.get_active()[:]:

            # CHANGE 1: Increase search radius to 800.0!
            # Since the Carrier is 800 units long, its center could be up to 800
            # units away from the laser hitting its nose. We must search a wider net.
            nearby_enemies = self.spatial.query_collision((l.x, l.y, l.z), 800.0)

            for e in nearby_enemies:
                if e not in enemies:
                    continue
                    
                # CHANGE 2: Use the dynamic is_hit() method instead of the hardcoded distance
                if e.is_hit(l.x, l.y, l.z):
                    e.on_hit()
                    l.life = 0  # Pool's own update() will recycle it next tick
                    for _ in range(PARTICLES_ON_HIT):
                        self.particle_pool.spawn(e.x, e.y, e.z)
                    break

        # ── UPDATE PROJECTILES ────────────────────────
        for bolt in enemy_projectiles[:]:
            if bolt.get('homing', False):
                dx = player.pos[0] - bolt['x']
                dy = player.pos[1] - bolt['y']
                dz = player.pos[2] - bolt['z']
                dist_sq = dx*dx + dy*dy + dz*dz
                dist = math.sqrt(dist_sq) if dist_sq > 0 else 1

                turn_rate = HOMING_TURN_RATE * dt

                spd = math.sqrt(bolt['vx']**2 + bolt['vy']**2 + bolt['vz']**2) or 1

                new_nx = (bolt['vx'] / spd) + (dx / dist) * turn_rate
                new_ny = (bolt['vy'] / spd) + (dy / dist) * turn_rate
                new_nz = (bolt['vz'] / spd) + (dz / dist) * turn_rate

                new_norm = math.sqrt(new_nx**2 + new_ny**2 + new_nz**2) or 1
                bolt['vx'] = (new_nx / new_norm) * spd
                bolt['vy'] = (new_ny / new_norm) * spd
                bolt['vz'] = (new_nz / new_norm) * spd

            bolt['x'] += bolt['vx'] * dt
            bolt['y'] += bolt['vy'] * dt
            bolt['z'] += bolt['vz'] * dt
            bolt['life'] -= dt

            if bolt['life'] <= 0:
                enemy_projectiles.remove(bolt)

    def draw_game(self, screen, W, H, player, stars, enemies, enemy_projectiles):
        screen.fill((5, 5, 15))

        draw_args = (player.pos, player.orientation)
        for star in stars:  star.draw(screen, *draw_args)

        # ── DRAW ENEMIES & SNIPER LASERS ────────────────
        for e in enemies:
            e.draw(screen, *draw_args)

            # If this is a Sniper in the charging state, draw the targeting beam!
            if getattr(e, 'state', '') == 'charging':
                # 1. Figure out where the sniper is on the screen
                cx, cy, cz = world_to_camera(e.x, e.y, e.z, *draw_args[0], draw_args[1])

                if cz > CAMERA_CLIP_NEAR:  # Only draw if the sniper is in front of the camera
                    proj = project_to_screen(cx, cy, cz)
                    if proj:
                        sx, sy, scale = proj

                        # 2. Calculate intensity (Charge timer goes SNIPER_CHARGE_TIME down to 0)
                        intensity = 1.0 - max(0.0, min(1.0, getattr(e, 'timer', SNIPER_CHARGE_TIME) / SNIPER_CHARGE_TIME))

                        # 3. Add an unstable jitter effect that gets worse as it charges
                        jitter = math.sin(pygame.time.get_ticks() * 0.05) * (SNIPER_CHARGE_JITTER * intensity)
                        jx, jy = sx + jitter, sy - jitter

                        # 4. Draw outer red glow (gets thicker)
                        thickness = max(1, int(8 * intensity))
                        pygame.draw.line(screen, (255, 0, 0), (jx, jy), (W//2, H//2), thickness)

                        # 5. Draw inner white-hot core right before firing
                        if intensity > SNIPER_CHARGE_CORE_THRESHOLD:
                            pygame.draw.line(screen, (255, 255, 255), (jx, jy), (W//2, H//2), max(1, thickness - 3))

                        # 6. Draw a bright glare on the front of the sniper's ship
                        glare = int(SNIPER_GLARE_MULTIPLIER * intensity * scale)
                        if glare > 0:
                            pygame.draw.circle(screen, (255, 50, 50), (jx, jy), glare)

        # Draw particles from pool
        for p in self.particle_pool.get_active_particles():
            self._draw_particle(screen, *draw_args, p)
        
        # Draw lasers from pool
        for l in self.laser_pool.get_active():
            l.draw(screen, *draw_args)

        # Draw projectiles
        for bolt in enemy_projectiles:
            cx, cy, cz = world_to_camera(bolt['x'], bolt['y'], bolt['z'], *draw_args[0], draw_args[1])
            proj = project_to_screen(cx, cy, cz)
            if proj:
                sx, sy, scale = proj
                # Grab customized traits, or fallback to defaults
                color = bolt.get('color', (255, 100, 100))
                size_mult = bolt.get('size_mult', 1.0)

                size = max(2, int(scale * 2 * size_mult))
                pygame.draw.circle(screen, color, (sx, sy), size)

                # If it's a homing bolt, draw an inner white core to make it look intense
                if bolt.get('homing', False) and size > 2:
                    pygame.draw.circle(screen, (255, 255, 255), (sx, sy), int(size / 2))

        draw_cockpit_hud(
            screen, W, H, player.throttle, player.current_speed, player.weapons_cooldown <= 0,
            orientation=player.orientation,
            player_pos=player.pos,
            player_vel=tuple(player.vel),
            enemies=enemies,
            player_hp=player.hp,
            active_target=player.active_target,
            dodge_charge=player.dodge_charge,
            dodge_ready=player.dodge_ready,
            dodge_flash=player.dodge_flash,
            shield_charge=player.shield_charge,
            shield_recharging=player.shield_recharging,
        )

        # Damage overlay
        draw_damage_overlay(screen, W, H, player.hit_flash / HIT_FLASH_DURATION)
    
    def _draw_particle(self, surf, ppos, prot, pdata):
        """Helper method to draw a particle from pool data."""
        cx, cy, cz = world_to_camera(pdata['x'], pdata['y'], pdata['z'], *ppos, prot)
        proj = project_to_screen(cx, cy, cz)
        if proj:
            sx, sy, scale = proj
            size = max(1, int(15 * scale * pdata['life']))
            pygame.draw.circle(surf, pdata['color'], (sx, sy), size)

    def main(self):

        while self.running:
            dt = self.clock.tick(60) / 1000.0

            # ── EVENTS ───────────────────────────────
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (
                    event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
                ):
                    self.running = False
                self.handler.process_event(event)

            keys = pygame.key.get_pressed()

            # ── UPDATE ────────────────────────────────
            self.player.update(dt, self.handler, keys, self.laser_pool, self.particle_pool, self.enemy_projectiles)
            self.update_entities(dt, self.player, self.enemies, self.enemy_projectiles)
            self.director.update(dt, self.player.pos, self.player.orientation, self.enemies)

            # ── TARGETING ──────────────────────────────────────
            # Keep target valid after kills/culls
            self.player.clear_dead_target(self.enemies)
            if self.player._key_target_closest:
                self.player.target_closest(self.enemies)
            elif self.player._key_cycle_target:
                self.player.cycle_targets(self.enemies)

            # ── DRAW ──────────────────────────────────
            self.draw_game(self.screen, self.W, self.H, self.player, self.stars, self.enemies, self.enemy_projectiles)

            pygame.display.flip()
            self.handler.update()

        pygame.quit()

