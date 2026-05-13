# pyrefly: ignore [missing-import]
import pygame
import math
from src.camera import Camera
from src.renderer import RenderPipeline
from src.cockpit import draw_cockpit_hud
from src.controller import DS4Input
from src.star import Star
from src.player import Player
from src.laser import Laser
from src.spatial_partition import SpatialPartition
from src.asteroid import AsteroidField
from src.nebula  import NebulaSystem
from src.constants import (
    HIT_FLASH_DURATION, PLAYER_COLLISION_RADIUS,
    ENEMY_CULL_DISTANCE,PARTICLES_ON_HIT, PARTICLES_ON_DESTROY, PARTICLES_ON_PLAYER_HIT,
    COLLISION_DAMAGE, CAMERA_CLIP_NEAR, SNIPER_CHARGE_TIME,
    SNIPER_CHARGE_JITTER, SNIPER_CHARGE_CORE_THRESHOLD, SNIPER_GLARE_MULTIPLIER,
    ASTEROID_PARTICLES_ON_DESTROY, ASTEROID_DAMAGE,
    AIM_MODE_THRESHOLD, AIM_MAGNIFICATION, AIM_MAGNIFICATION_MIN, AIM_MAGNIFICATION_MAX,
    AIM_WINDOW_SIZE, AIM_WINDOW_POS,
    AIM_WINDOW_BORDER_COLOR, AIM_WINDOW_CROSSHAIR_COLOR, PLAYER_LASER_SPEED,
    FULLSCREEN, SCREEN_WIDTH, SCREEN_HEIGHT
)
from src.utils import draw_damage_overlay
from src.director import WaveDirector
from src.encounters import ENCOUNTER_SCRIPT
from src.object_pool import ParticlePool, LaserPool

# ──────────────────────────────────────────────
# Game Class
# ──────────────────────────────────────────────

class Game:
    def __init__(self):
        # Initialize Pygame screen and clock
        pygame.init() # Init Pygame
        self.W, self.H = SCREEN_WIDTH, SCREEN_HEIGHT # Set Screen size
        flags = pygame.FULLSCREEN | pygame.SCALED if FULLSCREEN else 0
        self.screen = pygame.display.set_mode((self.W, self.H), flags) # Set display mode with screen size variables
        pygame.display.set_caption("🚀 3D Cockpit Dogfighter") # Set Window title
        self.clock = pygame.time.Clock() # Init clock for controlling FPS

        # Initialize DS4 controller handler
        self.handler = DS4Input() # Init DS4 controller handler
        self.handler.init() # Init DS4 controller handler

        # Initialize player and wave director
        self.player = Player() # Init Player class
        self.director = WaveDirector(ENCOUNTER_SCRIPT) # Init WaveDirector class

        # Initialize object pools for performance
        self.particle_pool = ParticlePool(initial_size=500, max_size=2000) # Init ParticlePool class
        self.laser_pool = LaserPool(Laser, initial_size=50, max_size=150) # Init LaserPool class
        
        # Initialize spatial partitioning for collision detection and culling
        self.spatial = SpatialPartition(cell_size=1000.0) # Init SpatialPartition class

        # Initialize camera and renderer
        self.camera = Camera(self.W, self.H) # Init Camera class
        self.renderer = RenderPipeline(self.camera) # Init RenderPipeline class

        # Initialize entities
        self.stars = [Star(self.player.pos) for _ in range(220)] # Init Star class
        self.nebulae = NebulaSystem(count=12, area_radius=30000) # Init NebulaSystem class TODO: refactor this intolevel script
        self.enemies = [] # Init Enemy class
        self.enemy_projectiles = [] # Init EnemyProjectiles class
        self.player_missiles = [] # Init PlayerMissile list
        self.asteroids = [] # Init Asteroid class

        # Spawn some initial asteroid fields near encounter points 
        # TODO: Refactor asteroid field creation logic 
        for enc in ENCOUNTER_SCRIPT:
            field = AsteroidField(enc['origin'], count=56, radius=25000)
            for a in field.asteroids:
                self.asteroids.append(a)
                self.spatial.register_entity(a, (a.x, a.y, a.z))
        
        # Initialize game state flags
        self.running = True # Set game state flag to True
        self.paused = False # Set game state flag to False

        # Initialize pause font
        self.pause_font = pygame.font.Font("assets/fonts/interdictionexpand.ttf", 72) # TODO add cache for this font

        # Initialize magnification resources for aim window
        self.magnify_surf = pygame.Surface((AIM_WINDOW_SIZE, AIM_WINDOW_SIZE), pygame.SRCALPHA) # Initialize magnification surface
        self.magnify_camera = Camera(AIM_WINDOW_SIZE, AIM_WINDOW_SIZE) # Initialize magnification camera
        self.magnify_renderer = RenderPipeline(self.magnify_camera) # Initialize magnification renderer
        self.current_magnification = 1.0 # Current smoothed magnification level

        # --- HUD WAYPOINTS ---
        self.show_waypoints = True
        # List of {'pos': (x,y,z), 'label': str, 'active': bool, 'color': (R,G,B,A)}
        self.waypoints = [
            {'pos': (4000, 2000, 8000), 'label': 'SECTOR ALPHA', 'active': True, 'color': (0, 255, 100, 200)},
            {'pos': (-6000, -1500, 3000), 'label': 'COMM RELAY', 'active': True, 'color': (255, 200, 0, 200)},
            {'pos': (0, -2000, -5000), 'label': 'HOME BASE', 'active': True, 'color': (0, 200, 255, 200)}
        ]

# -------------------------------------------------------------------------
# Game Loop Methods
# -------------------------------------------------------------------------

    def update_entities(self, dt, player, enemies, enemy_projectiles): 
        # ── UPDATE LASERS (using pool) ─────────────────────────
        self.laser_pool.update(dt)
        
        # ── UPDATE PARTICLES (using pool) ──────────────────────
        self.particle_pool.update(dt)

        # ── UPDATE PLAYER MISSILES ────────────────────
        for m in self.player_missiles[:]:
            m.update(dt)
            if m.check_enemy_collision(enemies, self.spatial, self.particle_pool):
                if m in self.player_missiles:
                    self.player_missiles.remove(m)
            elif m.life <= 0:
                if m in self.player_missiles:
                    self.player_missiles.remove(m)

        # ── UPDATE ENEMIES ────────────────────────
        for e in enemies[:]:
            e.update(dt, player.pos, player.orientation, enemy_projectiles, enemies, player)
            self.spatial.update_entity(e, (e.x, e.y, e.z))

            # Drone destroyed
            if e.hp <= 0:
                p_count = 100 if getattr(e, 'did_detonate', False) else PARTICLES_ON_DESTROY
                for _ in range(p_count):
                    self.particle_pool.spawn(e.x, e.y, e.z)
                self.spatial.unregister_entity(e)
                enemies.remove(e)
                continue

            # Collision with player
            if e.dist_to_player(player.pos) < PLAYER_COLLISION_RADIUS:
                player.take_damage(COLLISION_DAMAGE)
                for _ in range(PARTICLES_ON_PLAYER_HIT):
                    self.particle_pool.spawn(e.x, e.y, e.z)
                self.spatial.unregister_entity(e)
                enemies.remove(e)
                continue

            # Cull enemies far behind the camera
            cx, cy, cz = self.camera.world_to_camera(e.x, e.y, e.z)
            if cz < ENEMY_CULL_DISTANCE:
                self.spatial.unregister_entity(e)
                enemies.remove(e)

        # ── UPDATE ASTEROIDS ──────────────────────
        for a in self.asteroids[:]:
            a.update(dt)
            self.spatial.update_entity(a, (a.x, a.y, a.z))
            
            # Asteroid destroyed
            if a.hp <= 0:
                fragments = a.split()
                for f in fragments:
                    self.asteroids.append(f)
                    self.spatial.register_entity(f, (f.x, f.y, f.z))

                for _ in range(ASTEROID_PARTICLES_ON_DESTROY):
                    self.particle_pool.spawn(a.x, a.y, a.z, colors=[(120, 120, 120), (100, 100, 100), (80, 80, 80)])
                self.spatial.unregister_entity(a)
                self.asteroids.remove(a)
                continue
                
            # Collision with player
            dist_to_p = math.sqrt((a.x-player.pos[0])**2 + (a.y-player.pos[1])**2 + (a.z-player.pos[2])**2)
            if dist_to_p < (a.hit_radius + PLAYER_COLLISION_RADIUS):
                player.take_damage(ASTEROID_DAMAGE)
                for _ in range(PARTICLES_ON_PLAYER_HIT):
                    self.particle_pool.spawn(player.pos[0], player.pos[1], player.pos[2])
                a.on_hit(999) 
                continue

            # Cull far asteroids
            if a.z < player.pos[2] + ENEMY_CULL_DISTANCE:
                self.spatial.unregister_entity(a)
                self.asteroids.remove(a)

        # ── LASER HITS (spatial query) ─────────────────────────────
        for l in self.laser_pool.get_active()[:]:
            # Use spatial query for narrow search
            nearby_objects = self.spatial.query_nearby((l.x, l.y, l.z), 800.0)

            for obj in nearby_objects:
                if hasattr(obj, 'is_hit') and obj.is_hit(l.x, l.y, l.z):
                    if hasattr(obj, 'on_hit'):
                        obj.on_hit(1)
                    l.life = 0
                    for _ in range(PARTICLES_ON_HIT):
                        self.particle_pool.spawn(l.x, l.y, l.z)
                    break

        # ── ENEMY VS ASTEROID COLLISION ──────────────────
        for e in enemies:
            nearby = self.spatial.query_nearby((e.x, e.y, e.z), e.hit_radius + 500.0)
            for obj in nearby:
                if obj in self.asteroids:
                    dist_sq = (e.x - obj.x)**2 + (e.y - obj.y)**2 + (e.z - obj.z)**2
                    if dist_sq < (e.hit_radius + obj.hit_radius)**2:
                        e.on_hit(999) 
                        obj.on_hit(2)
                        for _ in range(PARTICLES_ON_DESTROY):
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

        # 1. Broad-phase Frustum Culling via Spatial Hash
        visible_entities = self.spatial.query_visible(self.camera)
        
        # 2. Submit static/environment
        for star in stars:
            star.submit_to_renderer(self.renderer, player.pos)
        self.nebulae.submit_to_renderer(self.renderer)

        # 3. Submit visible entities
        sniper_beams_to_draw = []
        for obj in visible_entities:
            obj.submit_to_renderer(self.renderer)
            if getattr(obj, 'state', '') == 'charging':
                sniper_beams_to_draw.append(obj)

        # 4. Submit non-spatial entities (small/numerous projectiles)
        for bolt in enemy_projectiles:
            if self.camera.sphere_in_frustum(bolt.x, bolt.y, bolt.z, 100):
                bolt.submit_to_renderer(self.renderer)
        
        for l in self.laser_pool.get_active():
            if self.camera.sphere_in_frustum(l.x, l.y, l.z, 200):
                l.submit_to_renderer(self.renderer)

        for m in self.player_missiles:
            if self.camera.sphere_in_frustum(m.x, m.y, m.z, 200):
                m.submit_to_renderer(self.renderer)

        # 5. Optimized Particle Submission
        self.particle_pool.submit_to_renderer(self.renderer, self.camera)

        # RENDER EVERYTHING
        self.renderer.render(screen)

        # Draw sniper beams on top (2D UI element)
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
            laser_heat=player.laser_heat,
            laser_overheated=player.overheated,
            waypoints=self.waypoints if self.show_waypoints else None,
            shake_offset=shake_offset,
            missile_ammo=player.missile_ammo,
            missile_lock_timer=player.missile_lock_timer,
            missile_locked=player.missile_locked,
        )

        # ── MAGNIFIED AIM WINDOW (L2) ──────────────────────────
        l2_val = self.handler.trigger_left()
        keys = pygame.key.get_pressed()
        
        # Calculate target magnification
        if l2_val > AIM_MODE_THRESHOLD:
            t = (l2_val - AIM_MODE_THRESHOLD) / (1.0 - AIM_MODE_THRESHOLD)
            target_mag = AIM_MAGNIFICATION_MIN + t * (AIM_MAGNIFICATION_MAX - AIM_MAGNIFICATION_MIN)
        elif keys[pygame.K_LSHIFT]:
            target_mag = AIM_MAGNIFICATION
        else:
            target_mag = 1.0 # Return to base
            
        # Smoothly lerp magnification (0.15 for responsive but premium feel)
        self.current_magnification += (target_mag - self.current_magnification) * 0.15
        
        # Render window if significantly zoomed in
        if self.current_magnification > 1.05:
            self._render_magnified_window(screen, self.player, visible_entities, stars, dt, self.current_magnification)

        draw_damage_overlay(screen, W, H, player.hit_flash / HIT_FLASH_DURATION)

        # if self.paused:
        #     pause_text = self.pause_font.render("PAUSE", True, (255, 0, 0))
        #     screen.blit(pause_text, (W // 2 - pause_text.get_width() // 2, H // 2 - pause_text.get_height() // 2))

    def _render_magnified_window(self, screen, player, visible_entities, stars, dt, magnification):
        """Render a secondary pass for the magnified aim window."""
        self.magnify_surf.fill((5, 5, 25, 200)) # Darker, slightly blue tint
        
        # Update magnify camera to match player but with dynamic FOV
        self.magnify_camera.fov = self.camera.fov * magnification
        self.magnify_camera.update(player.pos, player.orientation)
        self.magnify_renderer.clear()

        # Re-submit entities to magnify_renderer
        for star in stars:
            star.submit_to_renderer(self.magnify_renderer, player.pos)
        
        for obj in visible_entities:
            # Check if object is in frustum of the magnify camera
            if self.magnify_camera.sphere_in_frustum(obj.x, obj.y, obj.z, getattr(obj, 'hit_radius', 500)):
                obj.submit_to_renderer(self.magnify_renderer)

        for l in self.laser_pool.get_active():
            if self.magnify_camera.sphere_in_frustum(l.x, l.y, l.z, 200):
                l.submit_to_renderer(self.magnify_renderer)

        # ── PARTICLES IN MAGNIFIED VIEW ────────────────────────
        self.particle_pool.submit_to_renderer(self.magnify_renderer, self.magnify_camera)

        self.magnify_renderer.render(self.magnify_surf)

        # ── LEAD INDICATOR (PIP Leading) ────────────────────────
        if player.active_target:
            target = player.active_target
            # Target relative to player
            rx = target.x - player.pos[0]
            ry = target.y - player.pos[1]
            rz = target.z - player.pos[2]
            
            # Relative velocity
            p_vx, p_vy, p_vz = player.vel
            vx = target.vx - p_vx
            vy = target.vy - p_vy
            vz = target.vz - p_vz
            
            # Quadratic: (v.v - s^2)t^2 + 2(r.v)t + (r.r) = 0
            s = PLAYER_LASER_SPEED
            a = (vx*vx + vy*vy + vz*vz) - s*s
            b = 2 * (rx*vx + ry*vy + rz*vz)
            c = rx*rx + ry*ry + rz*rz
            
            det = b*b - 4*a*c
            if det >= 0:
                sqrt_det = math.sqrt(det)
                t1 = (-b - sqrt_det) / (2*a)
                t2 = (-b + sqrt_det) / (2*a)
                
                t = -1
                if t1 > 0 and t2 > 0: t = min(t1, t2)
                elif t1 > 0: t = t1
                elif t2 > 0: t = t2
                
                if t > 0:
                    # Predicted world position
                    lx = target.x + target.vx * t
                    ly = target.y + target.vy * t
                    lz = target.z + target.vz * t
                    
                    # Project onto magnification surface
                    cx, cy, cz = self.magnify_camera.world_to_camera(lx, ly, lz)
                    proj = self.magnify_camera.project(cx, cy, cz)
                    if proj:
                        psx, psy, _ = proj
                        # Draw lead diamond/circle
                        pts = [
                            (psx, psy - 8), (psx + 8, psy),
                            (psx, psy + 8), (psx - 8, psy)
                        ]
                        pygame.draw.polygon(self.magnify_surf, (255, 255, 0), pts, 1)
                        pygame.draw.circle(self.magnify_surf, (255, 255, 0), (psx, psy), 2)

        # Draw crosshair in magnify window
        mid = AIM_WINDOW_SIZE // 2
        pygame.draw.line(self.magnify_surf, AIM_WINDOW_CROSSHAIR_COLOR, (mid - 20, mid), (mid + 20, mid), 1)
        pygame.draw.line(self.magnify_surf, AIM_WINDOW_CROSSHAIR_COLOR, (mid, mid - 20), (mid, mid + 20), 1)
        pygame.draw.circle(self.magnify_surf, AIM_WINDOW_CROSSHAIR_COLOR, (mid, mid), 4, 1)

        # Draw "AIM MODE" text
        if not hasattr(self, '_aim_font'):
            self._aim_font = pygame.font.Font("assets/fonts/interdictionexpand.ttf", 14)
        lbl = self._aim_font.render("MAGNIFIED AIM", True, (0, 200, 255))
        self.magnify_surf.blit(lbl, (10, 10))

        # Blit magnified window to main screen
        screen.blit(self.magnify_surf, AIM_WINDOW_POS)
        
        # Draw frame/border
        rect = (AIM_WINDOW_POS[0], AIM_WINDOW_POS[1], AIM_WINDOW_SIZE, AIM_WINDOW_SIZE)
        pygame.draw.rect(screen, AIM_WINDOW_BORDER_COLOR, rect, 2)
        
        # Decorative corners
        c_len = 30
        x, y, w, h = rect
        # TL
        pygame.draw.line(screen, (255, 255, 255), (x-2, y-2), (x+c_len, y-2), 2)
        pygame.draw.line(screen, (255, 255, 255), (x-2, y-2), (x-2, y+c_len), 2)
        # TR
        pygame.draw.line(screen, (255, 255, 255), (x+w-c_len, y-2), (x+w+2, y-2), 2)
        pygame.draw.line(screen, (255, 255, 255), (x+w+2, y-2), (x+w+2, y+c_len), 2)
        # BL
        pygame.draw.line(screen, (255, 255, 255), (x-2, y+h-c_len), (x-2, y+h+2), 2)
        pygame.draw.line(screen, (255, 255, 255), (x-2, y+h+2), (x+c_len, y+h+2), 2)
        # BR
        pygame.draw.line(screen, (255, 255, 255), (x+w-c_len, y+h+2), (x+w+2, y+h+2), 2)
        pygame.draw.line(screen, (255, 255, 255), (x+w+2, y+h-c_len), (x+w+2, y+h+2), 2)

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

            if self.handler.just_pressed('DPad Left'):
                self.show_waypoints = not self.show_waypoints

            keys = pygame.key.get_pressed()

            if not self.paused:
                # ── UPDATE ────────────────────────────────
                self.player.update(dt, self.handler, keys, self.laser_pool, self.particle_pool, self.enemy_projectiles, self.player_missiles)
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
