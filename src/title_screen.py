# pyrefly: ignore [missing-import]
from src.asteroid import Asteroid
import pygame
import math
import random
from src.star import Star
from src.nebula import NebulaSystem
from src.asteroid import AsteroidField
from src.enemy import Dogfighter, SuicideDrone
from src.camera import Camera
from src.renderer import RenderPipeline
from src.object_pool import ParticlePool
from src.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.cinematic_motion import CinematicScript, CinematicStep, make_ring_swarm
from src.controller import DS4Input

# ─────────────────────────────────────────────────────────────────
# TIMING CONSTANTS  (tweak these to feel right)
# ─────────────────────────────────────────────────────────────────
T_MUSIC_START    = 0.0    # ambient music fires immediately
T_DOGFIGHTER_IN  = 2.0    # ship enters frame
T_LOGO_START     = 3.3   # AAA Studios text starts resolving from trail
T_SWARM_SPAWN    = 4.8    # drone swarm punches in from deep Z
T_EXPLOSION      = 5.8    # manual explosion fallback if drones miss
T_TITLE_DROP     = 6.4    # REDSHIFT SERPENS slams in
T_SUBTITLE_DROP  = 6.9    # DIVIDED SNAKES resolves under it
T_MENU_FADE      = 7.2    # menu items stagger in
T_DONE           = 8.0    # cinematic_done flag, enables keypress to continue

CAM_DETONATE_Z = -400   # world Z; negative = in front of camera origin
                         # tune closer to 0 for earlier pop, more negative
                         # for a deeper in-your-face hit
 

# ─────────────────────────────────────────────────────────────────
# DOGFIGHTER SPAWN  (tune X until ship enters from right edge)
# ─────────────────────────────────────────────────────────────────
DOG_SPAWN_X   =  1000    # positive X = screen right in camera space
DOG_SPAWN_Y   =  300    # slightly above center
DOG_SPAWN_Z   =  450    # comfortable Z depth
DOG_VELOCITY  = -400    # negative X = flies left; tune speed here

# ─────────────────────────────────────────────────────────────────
# DRONE SPAWN
# ─────────────────────────────────────────────────────────────────
DRONE_COUNT   = 12
DRONE_Z_START = 6000     # deep behind camera, punches forward
DRONE_VZ      = -5000    # fast inward velocity

# ─────────────────────────────────────────────────────────────────
# TRAIL CONFIG
# ─────────────────────────────────────────────────────────────────
TRAIL_MAX_LEN  = 60      # screen-space position history frames
TRAIL_HOT      = (255, 255, 220)   # newest = near-white hot
TRAIL_COOL     = (0, 255, 128)     # oldest = green ember (brand color)

CINEMATIC_ASTEROIDS = [
        # (x,      y,     z,      scale)
        ( 3700,   3000,  5000,   400),
        (-2900,   -600,  3000,   280),
        ( 4200,   -500,  4500,   220)
    ]


class TitleCinematic:
    def __init__(self, W, H, sound):
        self.W = W
        self.H = H
        self.sound = sound

        self.camera = Camera(W, H)
        self.renderer = RenderPipeline(self.camera)
        self.particle_pool = ParticlePool(initial_size=500, max_size=2000)

        # ── ENVIRONMENT ───────────────────────────────────────
        self.stars = [Star((0, 0, 0)) for _ in range(300)]
        self.nebulae = NebulaSystem(count=15, area_radius=50000)

        # in title_cinematic.py, replace the AsteroidField block

        self.asteroids = []
        for x, y, z, scale in CINEMATIC_ASTEROIDS:
            a = Asteroid(x, y, z, scale=scale)
            a.vx = a.vy = a.vz = 0.0   # pin in place, rotation only
            self.asteroids.append(a)

        # ── DOGFIGHTER ────────────────────────────────────────
        self.dogfighter = Dogfighter(DOG_SPAWN_X, DOG_SPAWN_Y, DOG_SPAWN_Z)
        self.dogfighter.vx = DOG_VELOCITY
        self.dogfighter.vy = 0
        self.dogfighter.vz = 0
        self.dogfighter.forward = (-1, 0, 0)
        self.dogfighter.right   = (0, 0, -1)
        self.dogfighter.up      = (0, 1, 0)

        # ── DRONES ────────────────────────────────────────────
        self.drones = []          # active drones (list of SuicideDrone)
        self._pending_drones = [] # (drone, spawn_time) waiting to activate
        self._swarm_origin_time = None  # wall time when swarm was queued
 

        # ── STATE ─────────────────────────────────────────────
        self.elapsed_time       = 0.0
        self.cinematic_done     = False
        self.music_started      = False
        self.explosion_triggered = False
        self.drones_spawned     = False

        # ── TRAIL ─────────────────────────────────────────────
        self.trail_history = []   # list of (sx, sy) screen coords

        # ── LOGO / TITLE ANIMATION STATE ──────────────────────
        self.logo_alpha    = 0.0   # AAA Studios fade-in
        self.title_alpha   = 0.0   # REDSHIFT SERPENS
        self.title_scale   = 2.8   # starts large, punches to 1.0
        self.sub_alpha     = 0.0   # DIVIDED SNAKES
        self.menu_alpha    = 0.0   # menu items
        self.flash_alpha   = 0.0   # white flash on explosion

        # ── CAMERA PAN STATE ──────────────────────────────────
        self.cam_y = 0.0
        self.cam_z = 0.0

        # ── FONTS ─────────────────────────────────────────────
        try:
            font_path = "assets/fonts/interdictionexpand.ttf"
            self.logo_font     = pygame.font.Font(font_path, 48)
            self.title_font    = pygame.font.Font(font_path, 70)
            self.sub_font      = pygame.font.Font(font_path, 36)
            self.menu_font     = pygame.font.Font(font_path, 28)
            self.prompt_font   = pygame.font.Font(font_path, 22)
        except FileNotFoundError:
            # Fallback to system font if asset missing
            self.logo_font     = pygame.font.Font(None, 48)
            self.title_font    = pygame.font.Font(None, 88)
            self.sub_font      = pygame.font.Font(None, 36)
            self.menu_font     = pygame.font.Font(None, 28)
            self.prompt_font   = pygame.font.Font(None, 22)

        # ── MENU ITEMS ──────────────────────────"──────────────
        self.menu_items = ["ARCADE", "NEW GAME", "CONTINUE", "OPTIONS", "QUIT"]
        self.menu_selected = 0

        self.show_popup = False

        # ── SHOCKWAVE ─────────────────────────────────────────
        self.shockwave_radius  = 0.0
        self.shockwave_alpha   = 0.0
        self.shockwave_active  = False
        self.shockwave_screen_pos = None   # (sx, sy) where it fires

        # ── DEBUG ─────────────────────────────────────────────
        self.debug = False   # set False to hide projection readout
        self._debug_font = pygame.font.Font(None, 20)

        

        self.dogfighter.cinematic_script = CinematicScript(
            CinematicStep(0.7, CinematicScript.linear(-1000, 60, 0)),
            CinematicStep(1.4, CinematicScript.barrel_roll(-1000, 60, 0,
                                                            roll_speed=1.2,
                                                            direction=-1.0)),
            CinematicStep(None, CinematicScript.linear(-1800, 0, 0)),   
        )

    # ─────────────────────────────────────────────────────────────
    # UPDATE
    # ─────────────────────────────────────────────────────────────
    def update(self, dt, handler):
        self.elapsed_time += dt
        t = self.elapsed_time

        # ── MUSIC ─────────────────────────────────────────────
        if not self.music_started:
            self.sound.play_music("assets/sounds/Rust-Orbit.wav", loops=-1, volume=0.85)
            self.music_started = True

        # ── CAMERA DRIFT (gentle upward pan) ──────────────────
        # Slow drift upward and slightly forward to give sense of motion
        self.cam_y = t * 80.0
        self.cam_z = t * 30.0
        cam_pos = (0.0, self.cam_y, self.cam_z)
        self.camera.update(cam_pos, (1, 0, 0, 0))   # identity quaternion = looking forward
        
        for asteroid in self.asteroids:
            asteroid.update(dt)

        # ── DOGFIGHTER FLYBY ──────────────────────────────────
        dog_alive = self.dogfighter.hp > 0
        if t >= T_DOGFIGHTER_IN and dog_alive:
            self.dogfighter.cinematic_update(dt)

            # Project to screen space and record trail
            cx, cy, cz = self.camera.world_to_camera(
                self.dogfighter.x, self.dogfighter.y, self.dogfighter.z
            )
            proj = self.camera.project(cx, cy, cz)
            if proj:
                sx, sy, _ = proj
                self.trail_history.append((sx, sy))
                if len(self.trail_history) > TRAIL_MAX_LEN:
                    self.trail_history.pop(0)

        # ── LOGO FADE (resolves from trail) ───────────────────
        if t >= T_LOGO_START and t < T_TITLE_DROP :
            self.logo_alpha = min(255.0, self.logo_alpha + 280.0 * dt)

         # ── DRONE SWARM SPAWN ─────────────────────────────────
        if t >= T_SWARM_SPAWN and not self.drones_spawned:
            self.drones_spawned = True
            self._swarm_origin_time = t
 
            swarm = make_ring_swarm(
                drone_class     = SuicideDrone,
                count           = DRONE_COUNT,
                center_x        = 0.0,
                center_y        = 0.0,
                spawn_z         = DRONE_Z_START,
                vz              = DRONE_VZ,
                radius          = 500,        # 1000 world units wide
                rotation_speed  = 1.5,        # rotations/sec — tune for speed
                spawn_stagger   = 0.06,       # seconds between activations
            )
            self._pending_drones = [(drone, self._swarm_origin_time + delay)
                                    for drone, delay in swarm]
 
        # ── ACTIVATE STAGGERED DRONES ─────────────────────────
        if self._pending_drones:
            still_pending = []
            for drone, activate_at in self._pending_drones:
                if t >= activate_at:
                    self.drones.append(drone)
                else:
                    still_pending.append((drone, activate_at))
            self._pending_drones = still_pending
 
        # ── DRONE UPDATE + DETONATION CHAIN ───────────────────
        first_detonator = None
        for drone in self.drones:
            if drone.did_detonate:
                continue
 
            drone.cinematic_update(dt)
 
            # Z threshold — blow up just in front of camera
            if drone.z < CAM_DETONATE_Z and not self.explosion_triggered:
                first_detonator = drone
                break   # chain fires below, no need to check rest
 
        if first_detonator is not None:
            # Detonate every active drone simultaneously for swarm flash
            for drone in self.drones:
                drone.did_detonate = True
            self._trigger_explosion()
 
        # ── MANUAL EXPLOSION FALLBACK ─────────────────────────
        if t >= T_EXPLOSION and not self.explosion_triggered:
            self._trigger_explosion()

        # ── SHOCKWAVE UPDATE ──────────────────────────────────
        if self.shockwave_active:
            self.shockwave_radius += 600.0 * dt
            self.shockwave_alpha   = max(0.0, self.shockwave_alpha - 280.0 * dt)
            if self.shockwave_alpha <= 0:
                self.shockwave_active = False

        # ── FLASH FADE ────────────────────────────────────────
        if self.flash_alpha > 0:
            self.flash_alpha = max(0.0, self.flash_alpha - 100.0 * dt)

        # ── TITLE DROP ────────────────────────────────────────
        if t >= T_TITLE_DROP:
            self.logo_alpha = max(0.0, self.logo_alpha - 200.0 * dt)   # logo fades as title comes in
            self.title_alpha = min(255.0, self.title_alpha + 600.0 * dt)
            self.title_scale = max(1.0, self.title_scale - 4.5 * dt)

        # ── SUBTITLE ──────────────────────────────────────────
        if t >= T_SUBTITLE_DROP:
            self.sub_alpha = min(255.0, self.sub_alpha + 400.0 * dt)

        # ── MENU FADE ─────────────────────────────────────────
        if t >= T_MENU_FADE:
            self.menu_alpha = min(255.0, self.menu_alpha + 180.0 * dt)

        # ── DONE FLAG ─────────────────────────────────────────
        if t >= T_DONE:
            self.cinematic_done = True

        # ── PARTICLES ─────────────────────────────────────────
        self.particle_pool.update(dt)

        # ── MENU NAVIGATION ───────────────────────────────────
        if handler and self.cinematic_done:
            # Disable menu updates if the "Coming Soon" popup is visible
            if self.show_popup:
                return None
            selected = self.update_menu_navigation(handler)
            if selected:
                return selected  # Return the selected menu item
        
        return None

    # ─────────────────────────────────────────────────────────────
    # INTERNAL: TRIGGER EXPLOSION
    # ─────────────────────────────────────────────────────────────
    def _trigger_explosion(self):
        self.explosion_triggered = True
        self.sound.play_sfx("explosion")

        # Big particle burst at dogfighter position
        for _ in range(250):
            self.particle_pool.spawn(
                self.dogfighter.x, self.dogfighter.y, self.dogfighter.z,
            )

        # Project shockwave origin to screen
        cx, cy, cz = self.camera.world_to_camera(
            self.dogfighter.x, self.dogfighter.y, self.dogfighter.z
        )
        proj = self.camera.project(cx, cy, cz)
        if proj:
            sx, sy, _ = proj
            self.shockwave_screen_pos = (sx, sy)

        self.shockwave_radius = 10.0
        self.shockwave_alpha  = 255.0
        self.shockwave_active = True
        self.flash_alpha      = 255.0
        self.dogfighter.hp    = 0

    # ─────────────────────────────────────────────────────────────
    # HANDLE INPUT (call from game loop event handler)
    # ─────────────────────────────────────────────────────────────
    
    def update_menu_navigation(self, handler):
        """Handle menu navigation with controller input"""
        if not self.cinematic_done:
            return
            
        # D-pad up/down for menu navigation
        if handler.just_pressed('DPad Up'):
            self.menu_selected = (self.menu_selected - 1) % len(self.menu_items)
        elif handler.just_pressed('DPad Down'):
            self.menu_selected = (self.menu_selected + 1) % len(self.menu_items)
        
        # Also handle controller face buttons for selection
        if handler.just_pressed('X'):  # 'X' button to select
            return self.menu_items[self.menu_selected]
        
        return None  # No selection made yet
    

    # ─────────────────────────────────────────────────────────────
    # DRAW
    # ─────────────────────────────────────────────────────────────
    def draw(self, screen):
        screen.fill((4, 4, 14))

        cam_pos = (0.0, self.cam_y, self.cam_z)

        # ── 3D RENDER PASS ────────────────────────────────────
        self.renderer.clear()

        Star.submit_batch_to_renderer(self.stars, self.renderer, cam_pos)
        self.nebulae.submit_to_renderer(self.renderer)
        for a in self.asteroids:
            a.submit_to_renderer(self.renderer)

        # Dogfighter (while alive and past entry time)
        if self.elapsed_time >= T_DOGFIGHTER_IN and self.dogfighter.hp > 0:
            self.dogfighter.submit_to_renderer(self.renderer)

        # Drones
        for drone in self.drones:
            if not drone.did_detonate:
                drone.submit_to_renderer(self.renderer)

        # Particles
        self.particle_pool.submit_to_renderer(self.renderer, self.camera)

        self.renderer.render(screen)

        # ── 2D OVERLAY PASS ───────────────────────────────────

        # TRAIL + LOGO
        self._draw_trail_and_logo(screen)

        # SHOCKWAVE RING
        if self.shockwave_active and self.shockwave_screen_pos:
            sw_surf = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
            r = int(self.shockwave_radius)
            a = int(self.shockwave_alpha)
            if r > 0:
                pygame.draw.circle(
                    sw_surf, (255, 180, 80, a),
                    self.shockwave_screen_pos, r, max(2, int(6 * (a / 255)))
                )
            screen.blit(sw_surf, (0, 0))

        # FLASH
        if self.flash_alpha > 4:
            flash_surf = pygame.Surface((self.W, self.H))
            flash_surf.fill((255, 255, 240))
            flash_surf.set_alpha(int(self.flash_alpha))
            screen.blit(flash_surf, (0, 0))

        # TITLE BLOCK
        self._draw_title_block(screen)

        # MENU
        if self.menu_alpha > 4:
            self._draw_menu(screen)

        # DEBUG PROJECTION READOUT
        if self.debug:
            self._draw_debug(screen)

        # ── COMING SOON POP-UP OVERLAY ────────────────────────
        if self.show_popup:
            self._draw_coming_soon_popup(screen)

    # ─────────────────────────────────────────────────────────────
    # TRAIL + LOGO HELPER
    # ─────────────────────────────────────────────────────────────
    def _draw_trail_and_logo(self, screen):
        n = len(self.trail_history)
        if n < 2:
            return

        trail_surf = pygame.Surface((self.W, self.H), pygame.SRCALPHA)

        for i, (sx, sy) in enumerate(self.trail_history):
            t = i / (n - 1)   # 0 = oldest/leftmost, 1 = newest/ship position

            # Color lerp: hot white at tip → cool green at tail
            r = int(TRAIL_HOT[0] * t + TRAIL_COOL[0] * (1 - t))
            g = int(TRAIL_HOT[1] * t + TRAIL_COOL[1] * (1 - t))
            b = int(TRAIL_HOT[2] * t + TRAIL_COOL[2] * (1 - t))

            # Alpha: bright at tip, dim at tail
            alpha = int(20 + 220 * t)
            radius = max(1, int(1 + 4 * t))

            pygame.draw.circle(trail_surf, (r, g, b, alpha), (int(sx), int(sy)), radius)

            # Connecting line segment to next point
            if i < n - 1:
                nx, ny = self.trail_history[i + 1]
                t2 = (i + 1) / (n - 1)
                a2 = int(20 + 220 * t2)
                pygame.draw.line(
                    trail_surf,
                    (r, g, b, max(alpha, a2) // 2),
                    (int(sx), int(sy)),
                    (int(nx), int(ny)),
                    max(1, radius)
                )

        screen.blit(trail_surf, (0, 0))

        # LOGO TEXT — anchored to oldest (leftmost) trail point
        # Only show while logo_alpha > 0 and we have enough trail
        if self.logo_alpha > 4 and n >= TRAIL_MAX_LEN // 3:
            anchor_x, anchor_y = self.W // 2, self.H // 3

            logo_surf = self.logo_font.render("A.A.A. GAMES", True, (0, 255, 58))
            logo_surf.set_alpha(int(self.logo_alpha))
            # Position: left of anchor, slightly above trail line
            lx = int(anchor_x - logo_surf.get_width() // 2)
            ly = int(anchor_y - logo_surf.get_height() - 12)
            screen.blit(logo_surf, (lx, ly))

            # Decorative underline glow
            line_surf = pygame.Surface((logo_surf.get_width(), 2), pygame.SRCALPHA)
            line_surf.fill((0, 255, 128, int(self.logo_alpha * 0.6)))
            screen.blit(line_surf, (lx, ly + logo_surf.get_height() + 2))

    # ─────────────────────────────────────────────────────────────
    # TITLE BLOCK HELPER
    # ─────────────────────────────────────────────────────────────
    def _draw_title_block(self, screen):
        if self.title_alpha < 4:
            return

        cx = self.W // 2
        cy = self.H // 2 - 60   # title sits above center

        # ── Title ──────────────────────────────────
        title_raw = self.title_font.render("PYTHON SPACE", True, (220, 40, 40))
        w = int(title_raw.get_width() * self.title_scale)
        h = int(title_raw.get_height() * self.title_scale)
        title_scaled = pygame.transform.scale(title_raw, (w, h))
        title_scaled.set_alpha(int(self.title_alpha))
        screen.blit(title_scaled, (cx - w // 2, cy - h // 2))

        # Scanline glow layer — second blit offset + dimmed for depth
        if self.title_scale < 1.05:   # only once settled
            glow_surf = pygame.Surface((w, h), pygame.SRCALPHA)
            glow_raw = self.title_font.render("PYTHON  SPACE", True, (255, 0, 0))
            glow_scaled = pygame.transform.scale(glow_raw, (w, h))
            glow_scaled.set_alpha(int(self.title_alpha * 0.25))
            screen.blit(glow_scaled, (cx - w // 2 + 2, cy - h // 2 + 2))

        # ── DIVIDED SNAKES ────────────────────────────────────
        if self.sub_alpha > 4:
            sub_raw = self.sub_font.render("S N A K E S  I N  S P A C E", True, (180, 180, 200))
            sub_raw.set_alpha(int(self.sub_alpha))
            sub_y = cy + h // 2 + 14
            screen.blit(sub_raw, (cx - sub_raw.get_width() // 2, sub_y))

            # Thin horizontal rule above subtitle
            rule_w = sub_raw.get_width() + 80
            rule_surf = pygame.Surface((rule_w, 1), pygame.SRCALPHA)
            rule_surf.fill((180, 180, 200, int(self.sub_alpha * 0.5)))
            screen.blit(rule_surf, (cx - rule_w // 2, sub_y - 8))

    # ─────────────────────────────────────────────────────────────
    # MENU HELPER
    # ─────────────────────────────────────────────────────────────
    def _draw_menu(self, screen):
        cx = self.W // 2
        base_y = self.H // 2 + 120
        item_h = 46

        for i, item in enumerate(self.menu_items):
            # Stagger each item's alpha for cascading reveal
            item_alpha = max(0, min(255, int(self.menu_alpha) - i * 40))
            if item_alpha < 4:
                continue

            selected = (i == self.menu_selected) and self.cinematic_done

            if selected:
                color = (0, 255, 128)
                # Selection bracket
                label = f"›  {item}  ‹"
            else:
                color = (140, 140, 160)
                label = item

            item_surf = self.menu_font.render(label, True, color)
            item_surf.set_alpha(item_alpha)

            ix = cx - item_surf.get_width() // 2
            iy = base_y + i * item_h
            screen.blit(item_surf, (ix, iy))

            # Selected item: dim horizontal bars top/bottom
            if selected:
                bar_w = item_surf.get_width() + 40
                bar_surf = pygame.Surface((bar_w, 1), pygame.SRCALPHA)
                bar_surf.fill((0, 255, 128, 80))
                screen.blit(bar_surf, (cx - bar_w // 2, iy - 6))
                screen.blit(bar_surf, (cx - bar_w // 2, iy + item_surf.get_height() + 4))

    # ─────────────────────────────────────────────────────────────
    # PROMPT HELPER # currently not in use, may delete later
    # ─────────────────────────────────────────────────────────────
    def _draw_prompt(self, screen):
        pulse = (math.sin(self.elapsed_time * 3.5) + 1) / 2
        alpha = int(60 + 195 * pulse)
        prompt_surf = self.prompt_font.render("PRESS X TO SKIP", True, (0, 200, 255))
        prompt_surf.set_alpha(alpha)
        screen.blit(
            prompt_surf,
            (self.W // 2 - prompt_surf.get_width() // 2, self.H - 80)
        )

    # ─────────────────────────────────────────────────────────────
    # DEBUG HELPER  (set self.debug = False to hide)
    # ─────────────────────────────────────────────────────────────
    def _draw_debug(self, screen):
        dog = self.dogfighter
        cx, cy, cz = self.camera.world_to_camera(dog.x, dog.y, dog.z)
        proj = self.camera.project(cx, cy, cz)

        lines = [
            f"t={self.elapsed_time:.2f}s",
            f"dog world: ({dog.x:.0f}, {dog.y:.0f}, {dog.z:.0f})",
            f"dog cam:   ({cx:.0f}, {cy:.0f}, {cz:.0f})",
            f"dog proj:  {proj}",
            f"trail len: {len(self.trail_history)}",
            f"drones: {len(self.drones)}  exploded: {self.explosion_triggered}",
            f"cam pos: (0, {self.cam_y:.0f}, {self.cam_z:.0f})",
        ]

        for i, line in enumerate(lines):
            surf = self._debug_font.render(line, True, (255, 255, 0))
            surf.set_alpha(180)
            screen.blit(surf, (10, 10 + i * 18))

    # ─────────────────────────────────────────────────────────────
    # POPUP HELPER
    # ─────────────────────────────────────────────────────────────

    def _draw_coming_soon_popup(self, screen):
        """Draws a themed 'Coming Soon' box overlay on screen."""
        # Semi-transparent dark background layer
        overlay = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        overlay.fill((4, 4, 14, 200))
        screen.blit(overlay, (0, 0))

        # Main popup box
        box_w, box_h = 930, 180
        box_x = (self.W - box_w) // 2
        box_y = (self.H - box_h) // 2 - 50

        # Draw box frame (dark background, glowing green border)
        pygame.draw.rect(screen, (10, 10, 25), (box_x, box_y, box_w, box_h))
        pygame.draw.rect(screen, (0, 255, 128), (box_x, box_y, box_w, box_h), 2)

        # Render elements
        title_surf = self.sub_font.render("COMING SOON", True, (220, 40, 40))
        desc_surf = self.prompt_font.render("This mode is currently under development.", True, (180, 180, 200))
        dismiss_surf = self.prompt_font.render("Press ENTER or X to return", True, (0, 255, 128))

        # Center and draw text surfaces
        screen.blit(title_surf, (self.W // 2 - title_surf.get_width() // 2, box_y + 32))
        screen.blit(desc_surf, (self.W // 2 - desc_surf.get_width() // 2, box_y + 85))
        screen.blit(dismiss_surf, (self.W // 2 - dismiss_surf.get_width() // 2, box_y + 130))


    # ─────────────────────────────────────────────────────────────
    # CINEMATIC CONTROL & SKIP HELPERS
    # ─────────────────────────────────────────────────────────────
    def skip_cinematic(self):
        """Skips straight to the active menu screen."""
        self.elapsed_time = T_DONE + 0.1
        self.cinematic_done = True
        
        # Snap alpha values
        self.logo_alpha = 0.0
        self.title_alpha = 255.0
        self.title_scale = 1.0
        self.sub_alpha = 255.0
        self.menu_alpha = 255.0
        
        # Clear out current entities
        self.dogfighter.hp = 0
        self.trail_history.clear()
        self.explosion_triggered = True

    def navigate_menu(self, direction):
        """Shifts selection index up (-1) or down (1)."""
        self.menu_selected = (self.menu_selected + direction) % len(self.menu_items)

    def get_selected_item(self):
        """Returns the text value of the currently selected menu item."""
        return self.menu_items[self.menu_selected]

    def update_menu_navigation(self, handler):
        """Handle menu navigation with controller input."""
        if not self.cinematic_done or self.show_popup:
            return None
            
        # D-pad up/down navigation
        if handler.just_pressed('DPad Up'):
            self.navigate_menu(-1)
        elif handler.just_pressed('DPad Down'):
            self.navigate_menu(1)
        
        # Controller select
        if handler.just_pressed('X'):
            return self.get_selected_item()
        
        return None