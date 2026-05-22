# pyrefly: ignore [missing-import]
from random import choice
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
from src.nebula import NebulaSystem
from src.constants import (
    HIT_FLASH_DURATION, PLAYER_COLLISION_RADIUS,
    ENEMY_CULL_DISTANCE, PARTICLES_ON_HIT, PARTICLES_ON_DESTROY, PARTICLES_ON_PLAYER_HIT,
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
from src.sound_handler import SoundHandler
from src.ship_ai import ShipAI
from src.title_screen import TitleCinematic
from src.hud_data import HUDData

from src.state import State, StateManager

# ──────────────────────────────────────────────
# State Classes
# ──────────────────────────────────────────────

class TitleState(State):
    def __init__(self, context):
        super().__init__(context)
        self.title_cinematic = TitleCinematic(context.W, context.H, context.sound)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and self.title_cinematic.cinematic_done:
            self.start_game()

    def update(self, dt, manager):
        self.title_cinematic.update(dt)
        # Allow starting the game via controller input too
        if self.title_cinematic.cinematic_done:
            if self.context.handler.just_pressed('Cross') or self.context.handler.just_pressed('Options'):
                self.start_game()

    def start_game(self):
        self.context.sound.play_music(self.context.music_file, loops=-1, volume=0.55)
        self.context.state_manager.change(GameplayState(self.context))

    def draw(self, screen):
        self.title_cinematic.draw(screen)


class GameplayState(State):
    def __init__(self, context):
        super().__init__(context)
        # Pull parameters from global context
        self.W, self.H = context.W, context.H
        
        # Initialize players & gameplay managers
        self.player = Player()
        self.player.sound = context.sound
        self.director = WaveDirector(ENCOUNTER_SCRIPT)
        self.ship_ai = ShipAI(context.sound)

        # Initialize object pools
        self.particle_pool = ParticlePool(initial_size=500, max_size=2000)
        self.laser_pool = LaserPool(Laser, initial_size=50, max_size=150)
        
        # Spatial system
        self.spatial = SpatialPartition(cell_size=1000.0)

        # Render tools
        self.camera = Camera(self.W, self.H)
        self.renderer = RenderPipeline(self.camera)

        # Environment & Entities
        self.stars = [Star(self.player.pos) for _ in range(250)]
        self.nebulae = NebulaSystem(count=12, area_radius=30000)
        self.enemies = []
        self.enemy_projectiles = []
        self.player_missiles = []
        self.asteroids = []

        # Spawn Asteroids
        for enc in ENCOUNTER_SCRIPT:
            field = AsteroidField(enc['origin'], count=25, radius=25000)
            for a in field.asteroids:
                self.asteroids.append(a)
                self.spatial.register_entity(a, (a.x, a.y, a.z))

        # Magnification Setup
        self.magnify_surf = pygame.Surface((AIM_WINDOW_SIZE, AIM_WINDOW_SIZE), pygame.SRCALPHA)
        self.magnify_camera = Camera(AIM_WINDOW_SIZE, AIM_WINDOW_SIZE)
        self.magnify_renderer = RenderPipeline(self.magnify_camera)
        self.current_magnification = 1.0

        # Waypoint & HUD toggles
        self.show_waypoints = True
        self.waypoints = [
            {'pos': (0, 0, 75000), 'label': 'Enemy Stronghold', 'active': True, 'color': (0, 255, 100, 200)},
            {'pos': (2000, -500, 25000), 'label': 'CARRIER STRIKE GROUP', 'active': True, 'color': (255, 200, 0, 200)},
            {'pos': (0, 0, 0), 'label': 'ORIGIN', 'active': True, 'color': (0, 200, 255, 200)}
        ]
        self.show_prograde = True
        self.show_coords = False

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_p:
                self.context.state_manager.push(PauseState(self.context))
            elif event.key == pygame.K_h:
                self.show_prograde = not self.show_prograde
            elif event.key == pygame.K_c:
                self.show_coords = not self.show_coords
        self.context.handler.process_event(event)

    def update(self, dt, manager):
        # Polling/DS4 options check
        if self.context.handler.just_pressed('Options'):
            manager.push(PauseState(self.context))
            return

        if self.context.handler.just_pressed('DPad Left'):
            self.show_waypoints = not self.show_waypoints

        if self.context.handler.just_pressed('DPad Right'):
            self.show_prograde = not self.show_prograde

        if self.context.handler.just_pressed('DPad Down'):
            self.show_coords = not self.show_coords

        keys = pygame.key.get_pressed()

        # Update dynamic objects
        self.player.update(dt, self.context.handler, keys, self.laser_pool, self.particle_pool, self.enemy_projectiles, self.player_missiles, self.context.sound)
        self.update_entities(dt, self.player, self.enemies, self.enemy_projectiles)
        self.director.update(dt, self.player.pos, self.player.orientation, self.enemies)
        self.ship_ai.update(self.player, self.enemies, self.enemy_projectiles, self.director, dt)

        # Targeting Checks
        self.player.clear_dead_target(self.enemies)
        if self.player._key_target_closest:
            self.player.target_closest(self.enemies)
        elif self.player._key_cycle_target:
            self.player.cycle_targets(self.enemies)

        # Handle Camera Shake
        if self.player.shake_queued > 0:
            self.camera.trigger_shake(self.player.shake_queued)
            self.player.shake_queued = 0.0

    def draw(self, screen):
        screen.fill((5, 5, 15))

        # Use clock delta to update camera shake offset
        # Note: dt is retrieved from context inside standard loops
        dt = self.context.clock.get_time() / 1000.0

        shake_offset = self.camera.update_shake(dt)
        self.camera.update(self.player.pos, self.player.orientation)
        self.renderer.clear()

        visible_entities = self.spatial.query_visible(self.camera)
        
        Star.submit_batch_to_renderer(self.stars, self.renderer, self.player.pos)
        self.nebulae.submit_to_renderer(self.renderer)

        sniper_beams_to_draw = []
        for obj in visible_entities:
            obj.submit_to_renderer(self.renderer)
            if getattr(obj, 'state', '') == 'charging':
                sniper_beams_to_draw.append(obj)

        for bolt in self.enemy_projectiles:
            if self.camera.sphere_in_frustum(bolt.x, bolt.y, bolt.z, 100):
                bolt.submit_to_renderer(self.renderer)
        
        for l in self.laser_pool.get_active():
            if self.camera.sphere_in_frustum(l.x, l.y, l.z, 200):
                l.submit_to_renderer(self.renderer)

        for m in self.player_missiles:
            if self.camera.sphere_in_frustum(m.x, m.y, m.z, 200):
                m.submit_to_renderer(self.renderer)

        self.particle_pool.submit_to_renderer(self.renderer, self.camera)
        self.renderer.render(screen)

        # Draw sniper beams on screen
        for e in sniper_beams_to_draw:
            cx, cy, cz = self.camera.world_to_camera(e.x, e.y, e.z)
            if cz > CAMERA_CLIP_NEAR:
                proj = self.camera.project(cx, cy, cz)
                if proj:
                    sx, sy, scale = proj
                    intensity = 1.0 - max(0.0, min(1.0, getattr(e, 'timer', SNIPER_CHARGE_TIME) / SNIPER_CHARGE_TIME))
                    jitter = math.sin(pygame.time.get_ticks() * 0.05) * (SNIPER_CHARGE_JITTER * intensity)
                    jx, jy = sx + jitter, sy - jitter
                    thickness = max(1, int(2 * intensity))
                    pygame.draw.line(screen, (255, 0, 0), (jx, jy), (self.W // 2, self.H // 2), thickness)
                    if intensity > SNIPER_CHARGE_CORE_THRESHOLD:
                        pygame.draw.line(screen, (255, 255, 255), (jx, jy), (self.W // 2, self.H // 2), max(1, thickness - 3))
                    glare = int(SNIPER_GLARE_MULTIPLIER * intensity * scale)
                    if glare > 0:
                        pygame.draw.circle(screen, (255, 50, 50), (jx, jy), glare)

        hud = HUDData(
            W=self.W,
            H=self.H,
            throttle=self.player.throttle,
            current_speed=self.player.current_speed,
            weapons_ready=self.player.weapons_cooldown <= 0,
            orientation=self.player.orientation,
            player_pos=self.player.pos,
            player_vel=tuple(self.player.vel),
            enemies=self.enemies,
            radar_enemies=self.spatial.query_nearby(self.player.pos, 6000.0) if hasattr(self, 'spatial') else None,
            player_hp=self.player.hp,
            active_target=self.player.active_target,
            dodge_charge=self.player.dodge_charge,
            dodge_ready=self.player.dodge_ready,
            dodge_flash=self.player.dodge_flash,
            text_fade=0.0,  # Required by some HUD configurations
            shield_charge=self.player.shield_charge,
            shield_recharging=self.player.shield_recharging,
            laser_heat=self.player.laser_heat,
            laser_overheated=self.player.overheated,
            waypoints=self.waypoints if self.show_waypoints else None,
            shake_offset=shake_offset,
            missile_ammo=self.player.missile_ammo,
            missile_lock_timer=self.player.missile_lock_timer,
            missile_locked=self.player.missile_locked,
            drift_mode=self.player.drift_mode,
            show_prograde=self.show_prograde,
            show_coords=self.show_coords,
        )
        draw_cockpit_hud(screen, hud)

        # Zoom Handling
        l2_val = self.context.handler.trigger_left()
        keys = pygame.key.get_pressed()
        
        if l2_val > AIM_MODE_THRESHOLD:
            t = (l2_val - AIM_MODE_THRESHOLD) / (1.0 - AIM_MODE_THRESHOLD)
            target_mag = AIM_MAGNIFICATION_MIN + t * (AIM_MAGNIFICATION_MAX - AIM_MAGNIFICATION_MIN)
        elif keys[pygame.K_LSHIFT]:
            target_mag = AIM_MAGNIFICATION
        else:
            target_mag = 1.0
            
        self.current_magnification += (target_mag - self.current_magnification) * 0.15
        
        if self.current_magnification > 1.05:
            self._render_magnified_window(screen, self.player, visible_entities, self.stars, dt, self.current_magnification)

        draw_damage_overlay(screen, self.W, self.H, self.player.hit_flash / HIT_FLASH_DURATION)

    def update_entities(self, dt, player, enemies, enemy_projectiles):
        # Update Lasers and Particles
        self.laser_pool.update(dt)
        self.particle_pool.update(dt)

        # Update Missiles
        for m in self.player_missiles[:]:
            m.update(dt)
            if m.check_collisions(enemies, self.asteroids, self.spatial, self.particle_pool):
                if m in self.player_missiles:
                    self.player_missiles.remove(m)
            elif m.life <= 0:
                if m in self.player_missiles:
                    self.player_missiles.remove(m)

        # Update Enemies
        for e in enemies[:]:
            e.update(dt, player.pos, player.orientation, enemy_projectiles, enemies, player, spatial=self.spatial)
            self.spatial.update_entity(e, (e.x, e.y, e.z))

            if e.hp <= 0:
                self.context.sound.play_sfx("explosion")
                p_count = 100 if getattr(e, 'did_detonate', False) else PARTICLES_ON_DESTROY
                for _ in range(p_count):
                    self.particle_pool.spawn(e.x, e.y, e.z)
                self.spatial.unregister_entity(e)
                enemies.remove(e)
                continue

            if e.dist_sq_to_player(player.pos) < PLAYER_COLLISION_RADIUS**2:
                player.take_damage(COLLISION_DAMAGE)
                for _ in range(PARTICLES_ON_PLAYER_HIT):
                    self.particle_pool.spawn(e.x, e.y, e.z)
                self.spatial.unregister_entity(e)
                enemies.remove(e)
                continue

            cx, cy, cz = self.camera.world_to_camera(e.x, e.y, e.z)
            if cz < ENEMY_CULL_DISTANCE:
                self.spatial.unregister_entity(e)
                enemies.remove(e)

        # Update Asteroids
        for a in self.asteroids[:]:
            a.update(dt)
            self.spatial.update_entity(a, (a.x, a.y, a.z))
            
            if a.hp <= 0:
                self.context.sound.play_sfx("explosion")
                fragments = a.split()
                for f in fragments:
                    self.asteroids.append(f)
                    self.spatial.register_entity(f, (f.x, f.y, f.z))

                for _ in range(ASTEROID_PARTICLES_ON_DESTROY):
                    self.particle_pool.spawn(a.x, a.y, a.z, colors=[(120, 120, 120), (100, 100, 100), (80, 80, 80)])
                self.spatial.unregister_entity(a)
                self.asteroids.remove(a)
                continue
                
            dist_sq_to_p = (a.x - player.pos[0])**2 + (a.y - player.pos[1])**2 + (a.z - player.pos[2])**2
            if dist_sq_to_p < (a.hit_radius + PLAYER_COLLISION_RADIUS)**2:
                player.take_damage(ASTEROID_DAMAGE)
                for _ in range(PARTICLES_ON_PLAYER_HIT):
                    self.particle_pool.spawn(player.pos[0], player.pos[1], player.pos[2])
                a.on_hit(999) 
                continue

            if a.z < player.pos[2] + ENEMY_CULL_DISTANCE:
                self.spatial.unregister_entity(a)
                self.asteroids.remove(a)

        # Laser Hits
        for l in self.laser_pool.get_active()[:]:
            nearby_objects = self.spatial.query_nearby((l.x, l.y, l.z), 800.0)
            for obj in nearby_objects:
                if hasattr(obj, 'is_hit') and obj.is_hit(l.x, l.y, l.z):
                    if hasattr(obj, 'on_hit'):
                        obj.on_hit(1)
                    l.life = 0
                    for _ in range(PARTICLES_ON_HIT):
                        self.particle_pool.spawn(l.x, l.y, l.z)
                    break

        # Enemy vs Asteroid collisions
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

        # Projectiles
        for bolt in enemy_projectiles[:]:
            bolt.update(dt, player.pos)
            if bolt.check_asteroid_collision(self.spatial, self.particle_pool):
                if bolt in enemy_projectiles:
                    enemy_projectiles.remove(bolt)
                continue

            if bolt.check_player_collision(player, self.particle_pool):
                if bolt in enemy_projectiles:
                    enemy_projectiles.remove(bolt)
                continue

            if bolt.life <= 0:
                if bolt in enemy_projectiles:
                    enemy_projectiles.remove(bolt)

    def _render_magnified_window(self, screen, player, visible_entities, stars, dt, magnification):
        self.magnify_surf.fill((5, 5, 25, 200))
        self.magnify_camera.fov = self.camera.fov * magnification
        self.magnify_camera.update(player.pos, player.orientation)
        self.magnify_renderer.clear()

        for star in stars:
            star.submit_to_renderer(self.magnify_renderer, player.pos)
        
        for obj in visible_entities:
            if self.magnify_camera.sphere_in_frustum(obj.x, obj.y, obj.z, getattr(obj, 'hit_radius', 500)):
                obj.submit_to_renderer(self.magnify_renderer)

        for l in self.laser_pool.get_active():
            if self.magnify_camera.sphere_in_frustum(l.x, l.y, l.z, 200):
                l.submit_to_renderer(self.magnify_renderer)

        self.particle_pool.submit_to_renderer(self.magnify_renderer, self.magnify_camera)
        self.magnify_renderer.render(self.magnify_surf)

        # Target Prediction Indicator
        if player.active_target:
            target = player.active_target
            rx = target.x - player.pos[0]
            ry = target.y - player.pos[1]
            rz = target.z - player.pos[2]
            
            p_vx, p_vy, p_vz = player.vel
            vx = target.vx - p_vx
            vy = target.vy - p_vy
            vz = target.vz - p_vz
            
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
                    lx = target.x + target.vx * t
                    ly = target.y + target.vy * t
                    lz = target.z + target.vz * t
                    
                    cx, cy, cz = self.magnify_camera.world_to_camera(lx, ly, lz)
                    proj = self.magnify_camera.project(cx, cy, cz)
                    if proj:
                        psx, psy, _ = proj
                        pts = [
                            (psx, psy - 8), (psx + 8, psy),
                            (psx, psy + 8), (psx - 8, psy)
                        ]
                        pygame.draw.polygon(self.magnify_surf, (255, 255, 0), pts, 1)
                        pygame.draw.circle(self.magnify_surf, (255, 255, 0), (psx, psy), 2)

        # Draw Crosshair
        mid = AIM_WINDOW_SIZE // 2
        pygame.draw.line(self.magnify_surf, AIM_WINDOW_CROSSHAIR_COLOR, (mid - 20, mid), (mid + 20, mid), 1)
        pygame.draw.line(self.magnify_surf, AIM_WINDOW_CROSSHAIR_COLOR, (mid, mid - 20), (mid, mid + 20), 1)
        pygame.draw.circle(self.magnify_surf, AIM_WINDOW_CROSSHAIR_COLOR, (mid, mid), 4, 1)

        if not hasattr(self, '_aim_font'):
            self._aim_font = pygame.font.Font("assets/fonts/interdictionexpand.ttf", 14)
        lbl = self._aim_font.render("MAGNIFIED AIM", True, (0, 200, 255))
        self.magnify_surf.blit(lbl, (10, 10))

        screen.blit(self.magnify_surf, AIM_WINDOW_POS)
        
        rect = (AIM_WINDOW_POS[0], AIM_WINDOW_POS[1], AIM_WINDOW_SIZE, AIM_WINDOW_SIZE)
        pygame.draw.rect(screen, AIM_WINDOW_BORDER_COLOR, rect, 2)
        
        c_len = 30
        x, y, w, h = rect
        pygame.draw.line(screen, (255, 255, 255), (x-2, y-2), (x+c_len, y-2), 2)
        pygame.draw.line(screen, (255, 255, 255), (x-2, y-2), (x-2, y+c_len), 2)
        pygame.draw.line(screen, (255, 255, 255), (x+w-c_len, y-2), (x+w+2, y-2), 2)
        pygame.draw.line(screen, (255, 255, 255), (x+w+2, y-2), (x+w+2, y+c_len), 2)
        pygame.draw.line(screen, (255, 255, 255), (x-2, y+h-c_len), (x-2, y+h+2), 2)
        pygame.draw.line(screen, (255, 255, 255), (x-2, y+h+2), (x+c_len, y+h+2), 2)
        pygame.draw.line(screen, (255, 255, 255), (x+w-c_len, y+h+2), (x+w+2, y+h+2), 2)
        pygame.draw.line(screen, (255, 255, 255), (x+w+2, y+h-c_len), (x+w+2, y+h+2), 2)


class PauseState(State):
    def __init__(self, context):
        super().__init__(context)
        self.pause_font = pygame.font.Font("assets/fonts/interdictionexpand.ttf", 72)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_p:
            self.context.state_manager.pop()

    def update(self, dt, manager):
        if self.context.handler.just_pressed('Options'):
            manager.pop()

    def draw(self, screen):
        # Draw the gameplay frame beneath the pause overlay
        if len(self.context.state_manager.stack) > 1:
            self.context.state_manager.stack[-2].draw(screen)

        # Translucent dark mask
        overlay = pygame.Surface((self.context.W, self.context.H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, (0, 0))

        # Pause Title
        pause_text = self.pause_font.render("PAUSED", True, (255, 0, 0))
        screen.blit(
            pause_text, 
            (self.context.W // 2 - pause_text.get_width() // 2, 
             self.context.H // 2 - pause_text.get_height() // 2)
        )


# ──────────────────────────────────────────────
# Game Context / App Base
# ──────────────────────────────────────────────

class Game:
    def __init__(self):
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=2048)
        pygame.init()

        # Shared Audio Resource Setup
        self.sound_folder = "assets/sounds/"
        self.sound = SoundHandler()
        self.sound.load_sfx("laser", self.sound_folder + "laser.wav")
        self.sound.load_sfx("laser_strained", self.sound_folder + "laser_strained.wav")
        self.sound.load_sfx("missile", self.sound_folder + "missile.wav")
        self.sound.load_sfx("explosion", self.sound_folder + "explosion.wav")
        self.sound.load_sfx("shield_hit", self.sound_folder + "shield_hit.wav")
        self.sound.load_sfx("armor_hit", self.sound_folder + "armor_hit.wav")
        self.sound.load_sfx("engine_hum_low", self.sound_folder + "engine_hum_low.wav")
        self.sound.load_sfx("engine_hum_mid", self.sound_folder + "engine_hum_mid.wav")
        self.sound.load_sfx("engine_hum_high", self.sound_folder + "engine_hum_high.wav")
        self.sound.load_sfx("engine_hum_overdrive", self.sound_folder + "engine_hum_overdrive.wav")
        
        self.sound.start_engine_hum()

        self.music_file = choice([
            self.sound_folder + "bgm_drone.wav",
            self.sound_folder + "bgm_drone2.wav",
            self.sound_folder + "bgm_drone3.wav"
        ])

        # Window & Clock
        self.W, self.H = SCREEN_WIDTH, SCREEN_HEIGHT
        flags = pygame.FULLSCREEN | pygame.SCALED if FULLSCREEN else 0
        self.screen = pygame.display.set_mode((self.W, self.H), flags)
        pygame.display.set_caption("🚀 3D Cockpit Dogfighter")
        self.clock = pygame.time.Clock()

        # Inputs
        self.handler = DS4Input()
        self.handler.init()

        # State Handling setup
        self.state_manager = StateManager(self)
        self.state_manager.push(TitleState(self))
        self.running = True

    def main(self):
        while self.running:
            dt = self.clock.tick(60) / 1000.0

            # Event Delegation
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (
                    event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
                ):
                    self.running = False
                
                if self.state_manager.current:
                    self.state_manager.current.handle_event(event)

            # State update
            if self.state_manager.current:
                self.state_manager.current.update(dt, self.state_manager)

            # State draw
            if self.state_manager.current:
                self.state_manager.current.draw(self.screen)

            # Device input updates must execute on a polling basis at the end of the frame
            self.handler.update()
            pygame.display.flip()

        self.sound.stop_music()
        pygame.quit()


if __name__ == "__main__":
    game = Game()
    game.main()