import pygame
import math
from src.math_engine import (
    world_to_camera, project_to_screen
)
from src.camera import Camera
from src.renderer import RenderPipeline
from src.cockpit import draw_cockpit_hud
from src.controller import DS4Input
from src.star import Star
from src.particle import Particle
from src.player import Player
from src.laser import Laser
from src.constants import (
    HIT_FLASH_DURATION, PLAYER_COLLISION_RADIUS,
    ENEMY_HIT_RADIUS_SQ, ENEMY_CULL_DISTANCE, HOMING_TURN_RATE,
    PARTICLES_ON_HIT, PARTICLES_ON_DESTROY, PARTICLES_ON_PLAYER_HIT,
    COLLISION_DAMAGE, CAMERA_CLIP_NEAR, SNIPER_CHARGE_TIME,
    SNIPER_CHARGE_JITTER, SNIPER_CHARGE_CORE_THRESHOLD, SNIPER_GLARE_MULTIPLIER
)
from src.utils import draw_damage_overlay
from src.director import WaveDirector
from src.encounters import ENCOUNTER_SCRIPT
from src.object_pool import ParticlePool, LaserPool
from src.spatial_partition import SpatialPartition

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

        self.camera = Camera(self.W, self.H)
        self.renderer = RenderPipeline(self.camera)

        self.stars = [Star(self.player.pos) for _ in range(350)]
        self.enemies = []
        self.enemy_projectiles = []

        self.running = True
        self.paused = False

        # Track which enemies are registered in spatial partition
        self._registered_enemies = set()

        # Load pause font
        self.pause_font = pygame.font.Font("assets/fonts/interdictionexpand.ttf", 72)

    def update_entities(self, dt, player, enemies, enemy_projectiles):
        # ── UPDATE LASERS (using pool) ─────────────────────────
        self.laser_pool.update(dt)
        
        # ── UPDATE PARTICLES (using pool) ──────────────────────
        self.particle_pool.update(dt)

        # ── UPDATE ENEMIES ────────────────────────
        for e in enemies[:]:
            e.update(dt, player.pos, player.orientation, enemy_projectiles, enemies, player)

            # Drone destroyed
            if e.hp <= 0:
                p_count = 100 if getattr(e, 'did_detonate', False) else PARTICLES_ON_DESTROY
                for _ in range(p_count):
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
            cx, cy, cz = self.camera.world_to_camera(e.x, e.y, e.z)
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
            bolt.update(dt, player.pos)

            if bolt.life <= 0:
                enemy_projectiles.remove(bolt)

    def draw_game(self, screen, W, H, player, stars, enemies, enemy_projectiles, dt):
        screen.fill((5, 5, 15))

        shake_offset = self.camera.update_shake(dt)
        self.camera.update(player.pos, player.orientation)
        self.renderer.clear()

        for star in stars:
            star.submit_to_renderer(self.renderer, player.pos)

        sniper_beams_to_draw = []

        # ── DRAW ENEMIES & SNIPER LASERS ────────────────
        for e in enemies:
            if self.camera.sphere_in_frustum(e.x, e.y, e.z, getattr(e, 'hit_radius', 50) * 2):
                e.submit_to_renderer(self.renderer)

                # If this is a Sniper in the charging state, remember it to draw the targeting beam on top
                if getattr(e, 'state', '') == 'charging':
                    sniper_beams_to_draw.append(e)

        # Draw particles from pool
        for pdata in self.particle_pool.get_active_particles():
            if self.camera.sphere_in_frustum(pdata['x'], pdata['y'], pdata['z'], 50):
                self._submit_particle(pdata)
        
        # Draw lasers from pool
        for l in self.laser_pool.get_active():
            if self.camera.sphere_in_frustum(l.x, l.y, l.z, 200):
                l.submit_to_renderer(self.renderer)

        # Draw projectiles
        for bolt in enemy_projectiles:
            if self.camera.sphere_in_frustum(bolt.x, bolt.y, bolt.z, 100):
                bolt.submit_to_renderer(self.renderer)

        # RENDER EVERYTHING
        self.renderer.render(screen)

        # Draw sniper beams on top
        for e in sniper_beams_to_draw:
            cx, cy, cz = self.camera.world_to_camera(e.x, e.y, e.z)
            if cz > CAMERA_CLIP_NEAR:
                proj = self.camera.project(cx, cy, cz)
                if proj:
                    sx, sy, scale = proj
                    intensity = 1.0 - max(0.0, min(1.0, getattr(e, 'timer', SNIPER_CHARGE_TIME) / SNIPER_CHARGE_TIME))
                    jitter = math.sin(pygame.time.get_ticks() * 0.05) * (SNIPER_CHARGE_JITTER * intensity)
                    jx, jy = sx + jitter, sy - jitter
                    thickness = max(1, int(8 * intensity))
                    pygame.draw.line(screen, (255, 0, 0), (jx, jy), (W//2, H//2), thickness)
                    if intensity > SNIPER_CHARGE_CORE_THRESHOLD:
                        pygame.draw.line(screen, (255, 255, 255), (jx, jy), (W//2, H//2), max(1, thickness - 3))
                    glare = int(SNIPER_GLARE_MULTIPLIER * intensity * scale)
                    if glare > 0:
                        pygame.draw.circle(screen, (255, 50, 50), (jx, jy), glare)

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
            shake_offset=shake_offset,
        )

        # Damage overlay
        draw_damage_overlay(screen, W, H, player.hit_flash / HIT_FLASH_DURATION)

        # Pause overlay
        if self.paused:
            pause_text = self.pause_font.render("PAUSE", True, (255, 0, 0))
            screen.blit(pause_text, (W // 2 - pause_text.get_width() // 2, H // 2 - pause_text.get_height() // 2))

    def _submit_particle(self, pdata):
        """Helper method to submit a particle from pool data to renderer."""
        self.renderer.submit_sprite(pdata['x'], pdata['y'], pdata['z'], pdata['color'], 15 * pdata['life'])

    def main(self):

        while self.running:
            dt = self.clock.tick(60) / 1000.0

            # ── EVENTS ───────────────────────────────
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (
                    event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
                ):
                    self.running = False
                if event.type == pygame.KEYDOWN and event.key == pygame.K_p:
                    self.paused = not self.paused
                self.handler.process_event(event)

            if self.handler.just_pressed('Options'):
                self.paused = not self.paused

            keys = pygame.key.get_pressed()

            if not self.paused:
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
            if self.player.shake_queued > 0:
                self.camera.trigger_shake(self.player.shake_queued)
                self.player.shake_queued = 0.0

            self.draw_game(self.screen, self.W, self.H, self.player, self.stars, self.enemies, self.enemy_projectiles, dt)

            pygame.display.flip()
            self.handler.update()

        pygame.quit()
