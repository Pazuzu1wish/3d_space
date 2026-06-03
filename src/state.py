from random import choice
import pygame
import math
import numpy as np
from src.save_data import RunResult, SaveData
from src.camera import Camera
from src.renderer import RenderPipeline, process_faces_batch_numba

from src.cockpit import draw_cockpit_hud
from src.controller import DS4Input
from src.star import Star
from src.player import Player
from src.laser import Laser
from src.spatial_partition import SpatialPartition
from src.asteroid import AsteroidField, init_asteroid_bank
from src.nebula import NebulaSystem
from src.constants import (
    HIT_FLASH_DURATION, PLAYER_COLLISION_RADIUS,
    ENEMY_CULL_DISTANCE, PARTICLES_ON_HIT, PARTICLES_ON_DESTROY, PARTICLES_ON_PLAYER_HIT,
    COLLISION_DAMAGE, CAMERA_CLIP_NEAR, SNIPER_CHARGE_TIME,
    SNIPER_CHARGE_JITTER, SNIPER_CHARGE_CORE_THRESHOLD, SNIPER_GLARE_MULTIPLIER,
    ASTEROID_PARTICLES_ON_DESTROY, ASTEROID_DAMAGE, FULLSCREEN,
    SCREEN_WIDTH, SCREEN_HEIGHT
)
from src.utils import draw_damage_overlay
from src.director import WaveDirector
from src.encounters import ENCOUNTER_SCRIPT
from src.object_pool import ParticlePool, LaserPool
from src.sound_handler import SoundHandler
from src.ship_ai import ShipAI
from src.title_screen import TitleCinematic
from src.hud_data import HUDData

from src.aim_scope import AimScope
from src.math_engine import world_to_camera_batch, project_to_screen_batch, get_forward_from_quat, quat_from_axis_angle, quat_mul
from collections import Counter




class State:
    """Base class for all game states.
    
    Provides standard lifecycle hooks and loop hooks for event handling,
    updating, and drawing.
    """
    def __init__(self, context):
        self.context = context

    def on_enter(self, manager):
        """Called when this state is pushed onto the stack."""
        pass

    def on_exit(self, manager):
        """Called when this state is popped off the stack."""
        pass

    def handle_event(self, event):
        """Called for every pygame event."""
        pass

    def update(self, dt, manager):
        """Called every frame to update state logic."""
        pass

    def draw(self, screen):
        """Called every frame to draw state visuals."""
        pass


class StateManager:
    """Manages the lifecycle and stack of active game states."""
    def __init__(self, context):
        self.context = context
        self.stack = []

    @property
    def current(self):
        """Returns the current active state at the top of the stack, or None if empty."""
        return self.stack[-1] if self.stack else None

    def push(self, state):
        """Pushes a new state onto the stack and enters it."""
        self.stack.append(state)
        state.on_enter(self)

    def pop(self):
        """Pops the top state off the stack and exits it, returning it."""
        if self.stack:
            state = self.stack.pop()
            state.on_exit(self)
            return state
        return None

    def change(self, state):
        """Replaces the top state of the stack with a new state."""
        self.pop()
        self.push(state)


# ──────────────────────────────────────────────
# State Classes
# ──────────────────────────────────────────────

# ──────────────────────────────────────────────
# Title State
# ──────────────────────────────────────────────


class TitleState(State):
    def __init__(self, context):
        super().__init__(context)
        self.title_cinematic = TitleCinematic(context.W, context.H, context.sound)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and self.title_cinematic.cinematic_done:
            self.start_game()
        self.context.handler.process_event(event)

    def update(self, dt, manager):
        self.title_cinematic.update(dt, self.context.handler)

        # Handle menu navigation
        selected = self.title_cinematic.update_menu_navigation(self.context.handler)
        if selected:
            self.start_game()

        # Allow starting the game via controller input too
        if self.title_cinematic.cinematic_done:
            if self.context.handler.just_pressed('X') or self.context.handler.just_pressed('Options'):
                self.start_game()

    def start_game(self):
        self.context.sound.play_music(self.context.music_file, loops=-1, volume=0.55)
        self.context.state_manager.change(GameplayState(self.context))

    def draw(self, screen):
        self.title_cinematic.draw(screen)


# ──────────────────────────────────────────────
# Gameplay Class
# ──────────────────────────────────────────────

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
        self.spatial = SpatialPartition(cell_size=500.0)

        # Render tools
        self.camera = Camera(self.W, self.H)
        self.renderer = RenderPipeline(self.camera)

        # Initialize aim scope
        self.aim_scope = AimScope(self.camera, self.laser_pool, self.particle_pool)

        # Environment & Entities
        self.stars = [Star(self.player.pos) for _ in range(150)]
        self.nebulae = NebulaSystem(count=6, area_radius=30000)
        self.enemies = []
        self.enemy_projectiles = []
        self.player_missiles = []
        self.asteroids = []

        # Spawn Asteroids
        for enc in ENCOUNTER_SCRIPT:
            field = AsteroidField(enc['origin'], count=12, radius=25000)
            for a in field.asteroids:
                self.asteroids.append(a)
                self.spatial.register_entity(a, (a.x, a.y, a.z))

        # Waypoint & HUD toggles
        self.show_waypoints = True
        self.waypoints = [
            {'pos': (0, 0, 75000), 'label': 'Enemy Stronghold', 'active': True, 'color': (0, 255, 100, 200)},
            {'pos': (2000, -500, 25000), 'label': 'CARRIER STRIKE GROUP', 'active': True, 'color': (255, 200, 0, 200)},
            {'pos': (0, 0, 0), 'label': 'ORIGIN', 'active': True, 'color': (0, 200, 255, 200)}
        ]
        self.show_prograde = True
        self.show_coords = False
        # FPS debug toggle
        self.show_fps = True

        # Force all Numba JIT compilations to happen now (during load),
        # not on the first gameplay frame.
        self._warmup_numba()

    def _warmup_numba(self):
        """Pre-compile every @njit function used in the hot render path.

        Each call uses tiny dummy arrays so the compile finishes in ~1-2 s
        during the title / loading phase rather than causing a stutter on
        the very first gameplay frame.
        """

        # Minimal dummy data — 1 vert, 1 face
        dummy_verts = np.zeros((3, 3), dtype=np.float64)
        dummy_cam = np.zeros((3, 3), dtype=np.float64)
        dummy_cam[:, 2] = 1.0  # Z > near-clip so projection doesn’t sentinel
        dummy_proj = np.zeros((3, 3), dtype=np.float64)
        dummy_fidx = np.array([[0, 1, 2]], dtype=np.int32)
        dummy_fcol = np.array([[200, 200, 200]], dtype=np.int32)
        dummy_rcoef = np.eye(3, dtype=np.float64).ravel()  # identity rotation

        # world_to_camera_batch
        world_to_camera_batch(dummy_verts, 0.0, 0.0, 0.0, dummy_rcoef)
        # project_to_screen_batch
        project_to_screen_batch(dummy_cam, 400.0, 640.0, 360.0, 0.0, 0.0, 0.1)
        # process_faces_batch_numba (main face shading + depth sort)
        process_faces_batch_numba(dummy_cam, dummy_proj, dummy_fidx, dummy_fcol)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_p:
                self.context.state_manager.push(PauseState(self.context))
            elif event.key == pygame.K_h:
                self.show_prograde = not self.show_prograde
            elif event.key == pygame.K_c:
                self.show_coords = not self.show_coords
            elif event.key == pygame.K_o:
                # Toggle lightweight FPS debug HUD
                self.show_fps = not self.show_fps
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
        self.player.update(dt, self.context.handler, keys, self.laser_pool, self.particle_pool, self.enemy_projectiles,
                           self.player_missiles, self.context.sound)
        self.update_entities(dt, self.player, self.enemies, self.enemy_projectiles)
        self.director.update(dt, self.player.pos, self.player.orientation, self.enemies)
        self.ship_ai.update(self.player, self.enemies, self.enemy_projectiles, self.director, dt)

        # Targeting Checks
        self.player.clear_dead_target(self.enemies)
        if self.player._key_target_closest:
            self.player.target_closest(self.enemies)
        elif self.player._key_cycle_target:
            self.player.cycle_targets(self.enemies)

        # Update aim scope
        self.aim_scope.update(
            self.context.handler.trigger_left(),
            keys,
        )

        # Handle Death
        if self.player.hp <= 0:
            result = RunResult(
                kills=self.director.kills,
                survival_time=self.director.elapsed,
                shots_fired=self.player.shots_fired,
                shots_hit=self.player.shots_hit,
                damage_taken=self.player.damage_taken,
                max_hp=self.player.max_hp
            )
            manager.change(GameOverState(self.context, result))
            return

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
        self.draw_sniper_beams(screen, sniper_beams_to_draw)

        # Lightweight FPS value from the shared clock (smoothed by pygame)
        fps_val = self.context.clock.get_fps()

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
            show_fps=self.show_fps,
            fps=fps_val,
        )
        draw_cockpit_hud(screen, hud)

        self.aim_scope.draw(screen, self.player, visible_entities, self.stars)

        draw_damage_overlay(screen, self.W, self.H, self.player.hit_flash / HIT_FLASH_DURATION)

    def draw_sniper_beams(self, screen, sniper_beams_to_draw):
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
                        pygame.draw.line(screen, (255, 255, 255), (jx, jy), (self.W // 2, self.H // 2),
                                         max(1, thickness - 3))
                    glare = int(SNIPER_GLARE_MULTIPLIER * intensity * scale)
                    if glare > 0:
                        pygame.draw.circle(screen, (255, 50, 50), (jx, jy), glare)

    def draw_photo_mode(self, screen, cam_pos, q_cam):
        screen.fill((5, 5, 15))

        # Temp save original camera position & orientation
        orig_pos = self.camera.pos
        orig_orient = self.camera.orientation

        # Set camera to the orbit camera
        self.camera.update(cam_pos, q_cam)
        self.renderer.clear()

        # Submit elements to renderer
        Star.submit_batch_to_renderer(self.stars, self.renderer, self.player.pos)
        self.nebulae.submit_to_renderer(self.renderer)

        # Query nearby entities to render in Photo Mode
        visible_entities = self.spatial.query_nearby(self.player.pos, 15000.0)
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

        # Submit the Player Ship in 3D!
        self.player.submit_to_renderer(self.renderer)

        # Render the 3D scene!
        self.renderer.render(screen)

        # Draw sniper beams if charging
        self.draw_sniper_beams(screen, sniper_beams_to_draw)

        # Restore camera
        self.camera.update(orig_pos, orig_orient)

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

            # Decrement spawn immunity timer
            if e.spawn_immunity_timer > 0:
                e.spawn_immunity_timer -= dt

            if e.hp <= 0:
                self.context.sound.play_sfx("explosion")
                self.director.kills.append(type(e).__name__)
                p_count = 100 if getattr(e, 'did_detonate', False) else PARTICLES_ON_DESTROY
                for _ in range(p_count):
                    self.particle_pool.spawn(e.x, e.y, e.z)
                self.spatial.unregister_entity(e)
                enemies.remove(e)
                continue

            if e.dist_sq_to_player(player.pos) < PLAYER_COLLISION_RADIUS ** 2:
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

            dist_sq_to_p = (a.x - player.pos[0]) ** 2 + (a.y - player.pos[1]) ** 2 + (a.z - player.pos[2]) ** 2
            if dist_sq_to_p < (a.hit_radius + PLAYER_COLLISION_RADIUS) ** 2:
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
                        self.player.shots_hit += 1
                    l.life = 0
                    for _ in range(PARTICLES_ON_HIT):
                        self.particle_pool.spawn(l.x, l.y, l.z)
                    break

        # Enemy vs Asteroid collisions
        for e in enemies:
            # Skip collision check if enemy is in spawn immunity period
            if e.spawn_immunity_timer > 0:
                continue

            nearby = self.spatial.query_nearby((e.x, e.y, e.z), e.hit_radius + 500.0)
            for obj in nearby:
                # OPTIMIZATION: 'hasattr' is instant. 'in list' is extremely slow!
                if hasattr(obj, 'split'):
                    dist_sq = (e.x - obj.x) ** 2 + (e.y - obj.y) ** 2 + (e.z - obj.z) ** 2
                    if dist_sq < (e.hit_radius + obj.hit_radius) ** 2:
                        e.on_hit(999)
                        obj.on_hit(2)
                        for _ in range(PARTICLES_ON_DESTROY):
                            self.particle_pool.spawn(e.x, e.y, e.z)
                        break

        # Enemy vs Enemy collisions
        for i, e1 in enumerate(enemies):
            nearby = self.spatial.query_nearby((e1.x, e1.y, e1.z), e1.hit_radius + 500.0)
            for e2 in nearby:
                # Skip if it's the same enemy or not an enemy (check for enemy-specific attributes)
                if e2 is e1 or not isinstance(e2, type(e1).__bases__[0] if e1.__class__.__bases__ else object):
                    continue
                # Check if it has hit_radius and on_hit (enemy attributes)
                if not hasattr(e2, 'hit_radius') or not hasattr(e2, 'on_hit'):
                    continue
                # Skip asteroids (they have 'split' method)
                if hasattr(e2, 'split'):
                    continue
                # Check if it's actually in the enemies list
                if e2 not in enemies:
                    continue

                # Skip collision if either enemy is in spawn immunity period
                if e1.spawn_immunity_timer > 0 or e2.spawn_immunity_timer > 0:
                    continue

                dist_sq = (e1.x - e2.x) ** 2 + (e1.y - e2.y) ** 2 + (e1.z - e2.z) ** 2
                if dist_sq < (e1.hit_radius + e2.hit_radius) ** 2:
                    e1.on_hit(1)
                    e2.on_hit(1)
                    for _ in range(PARTICLES_ON_HIT):
                        self.particle_pool.spawn(e1.x, e1.y, e1.z)
                    break

        # Projectiles
        for bolt in enemy_projectiles[:]:
            bolt.update(dt, player.pos)
            if bolt.check_asteroid_collision(self.spatial, self.particle_pool):
                if bolt in enemy_projectiles:
                    enemy_projectiles.remove(bolt)
                continue

            if bolt.check_enemy_collision(self.spatial, self.particle_pool):
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


# ──────────────────────────────────────────────
# Game Over Class
# ──────────────────────────────────────────────

class GameOverState(State):
    """
    Displays score breakdown for the completed run and top scores.
    No gameplay systems — purely presentation.

    Usage (from GameplayState.update):
        result = RunResult(
            kills         = self.director.kills,
            survival_time = self.director.elapsed,
            shots_fired   = self.player.shots_fired,
            shots_hit     = self.player.shots_hit,
            damage_taken  = self.player.damage_taken,
            max_hp        = self.player.max_hp,
        )
        manager.change(GameOverState(self.context, result))
    """

    def __init__(self, context, result: RunResult):
        super().__init__(context)
        self.result = result

        # Persist immediately on construction
        self.context.save_data.record_run(result)
        self.context.save_data.save()

        self._build_fonts()
        self._anim_timer = 0.0  # drives line-by-line reveal
        self._lines_shown = 0
        self._done = False  # all lines revealed

    # ── State interface ───────────────────────────────────────────────────────

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                self._handle_confirm()
        self.context.handler.process_event(event)

    def update(self, dt, manager):
        # Skip to fully revealed on any button
        if self.context.handler.just_pressed('X') or self.context.handler.just_pressed('Cross'):
            if not self._done:
                self._lines_shown = 999
                self._done = True
            else:
                self._go_to_title(manager)
            return

        if self.context.handler.just_pressed('Circle'):
            self._go_to_retry(manager)
            return

        # Timed line reveal
        self._anim_timer += dt
        target = int(self._anim_timer / 0.18)
        if target > self._lines_shown:
            self._lines_shown = target
        if self._lines_shown >= self._total_lines():
            self._done = True

    def draw(self, screen):
        screen.fill((5, 5, 15))
        self._draw_scanlines(screen)

        W, H = self.context.W, self.context.H
        cx = W // 2
        r = self.result

        lines_drawn = 0

        def draw_line(text, font, color, y, alpha=255):
            nonlocal lines_drawn
            lines_drawn += 1
            if lines_drawn > self._lines_shown:
                return
            surf = font.render(text, True, color)
            surf.set_alpha(alpha)
            screen.blit(surf, (cx - surf.get_width() // 2, y))

        def draw_line_lr(left, right, font, color_l, color_r, y):
            nonlocal lines_drawn
            lines_drawn += 1
            if lines_drawn > self._lines_shown:
                return
            ls = font.render(left, True, color_l)
            rs = font.render(right, True, color_r)
            screen.blit(ls, (cx - 260, y))
            screen.blit(rs, (cx + 260 - rs.get_width(), y))

        # ── header ────────────────────────────────────────────────────────
        draw_line("MISSION COMPLETE" if r.kill_count() > 0 else "PILOT DOWN",
                  self._font_large,
                  (255, 50, 50) if r.kill_count() == 0 else (0, 220, 255),
                  H * 0.08)

        draw_line("─" * 48, self._font_small, (40, 80, 100), H * 0.16)

        # ── kill breakdown ────────────────────────────────────────────────
        draw_line("KILLS", self._font_med, (180, 180, 180), H * 0.21)

        counts = Counter(r.kills)
        kill_y = H * 0.27
        for etype, count in sorted(counts.items(), key=lambda x: -x[1]):
            pts = RunResult.KILL_POINTS.get(etype, 100)
            draw_line_lr(
                f"  {etype}  ×{count}",
                f"{pts * count:,}",
                self._font_small,
                (200, 200, 200),
                (255, 220, 80),
                kill_y,
            )
            kill_y += 28

        if not r.kills:
            draw_line("  no kills", self._font_small, (100, 100, 100), kill_y)
            kill_y += 28

        # ── modifiers ────────────────────────────────────────────────────
        mod_y = kill_y + 16
        draw_line("─" * 48, self._font_small, (40, 80, 100), mod_y)
        mod_y += 20

        draw_line("MODIFIERS", self._font_med, (180, 180, 180), mod_y)
        mod_y += 32

        mins = int(r.survival_time // 60)
        secs = int(r.survival_time % 60)
        draw_line_lr(
            f"  Survival  {mins}m {secs:02d}s",
            f"×{r.time_modifier():.2f}",
            self._font_small, (200, 200, 200), (100, 220, 255), mod_y,
        )
        mod_y += 28

        draw_line_lr(
            f"  Accuracy  {r.accuracy() * 100:.1f}%  ({r.shots_hit}/{r.shots_fired})",
            f"×{r.accuracy_modifier():.2f}",
            self._font_small, (200, 200, 200), (100, 220, 255), mod_y,
        )
        mod_y += 28

        dmg_pct = min(100, int(r.damage_taken / max(1, r.max_hp) * 100))
        draw_line_lr(
            f"  Damage taken  {dmg_pct}%",
            f"×{r.damage_modifier():.2f}",
            self._font_small, (200, 200, 200), (100, 220, 255), mod_y,
        )
        mod_y += 28

        # ── final score ───────────────────────────────────────────────────
        draw_line("─" * 48, self._font_small, (40, 80, 100), mod_y + 8)

        draw_line_lr(
            "  FINAL SCORE",
            f"{r.final_score():,}",
            self._font_med,
            (220, 220, 220),
            (255, 220, 0),
            mod_y + 36,
        )

        # ── top scores sidebar ────────────────────────────────────────────
        scores = self.context.save_data.high_scores
        if scores and self._done:
            self._draw_high_scores(screen, scores)

        # ── prompt ────────────────────────────────────────────────────────
        if self._done:
            prompt = "[ X ] Continue    [ O ] Retry"
            ps = self._font_small.render(prompt, True, (120, 120, 120))
            screen.blit(ps, (cx - ps.get_width() // 2, H * 0.92))

    # ── private ───────────────────────────────────────────────────────────────

    def _build_fonts(self):
        path = "assets/fonts/interdictionexpand.ttf"
        self._font_large = pygame.font.Font(path, 64)
        self._font_med = pygame.font.Font(path, 28)
        self._font_small = pygame.font.Font(path, 18)

    def _total_lines(self):
        """Approximate total drawable lines — controls when _done fires."""
        return 6 + len(self.result.kills) + 8

    def _draw_scanlines(self, screen):
        W, H = self.context.W, self.context.H
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        for y in range(0, H, 4):
            pygame.draw.line(overlay, (0, 0, 0, 40), (0, y), (W, y))
        screen.blit(overlay, (0, 0))

    def _draw_high_scores(self, screen, scores):
        W, H = self.context.W, self.context.H
        x = W * 0.78
        y = H * 0.22
        title = self._font_med.render("TOP SCORES", True, (80, 80, 120))
        screen.blit(title, (x, y))
        y += 36
        for i, s in enumerate(scores[:SaveData.MAX_SCORES]):
            color = (255, 220, 0) if s['final_score'] == self.result.final_score() else (120, 120, 140)
            line = self._font_small.render(
                f"{i + 1}.  {s['final_score']:>10,}   {len(s['kills'])}k", True, color
            )
            screen.blit(line, (x, y))
            y += 24

    def _handle_confirm(self):
        pass  # handled in update via just_pressed

    def _go_to_title(self, manager):
        manager.change(TitleState(self.context))

    def _go_to_retry(self, manager):
        manager.change(GameplayState(self.context))


# ──────────────────────────────────────────────
# Pause Class
# ──────────────────────────────────────────────

class PauseState(State):
    def __init__(self, context):
        super().__init__(context)
        self.title_font = pygame.font.Font("assets/fonts/interdictionexpand.ttf", 34)
        self.menu_font = pygame.font.Font("assets/fonts/interdictionexpand.ttf", 18)
        self.hint_font = pygame.font.Font("assets/fonts/interdictionexpand.ttf", 11)

        # 3D Orbit Camera state
        self.orbit_yaw = 0.0
        self.orbit_pitch = 0.2
        self.orbit_distance = 250.0

        # Timing / Auto-Orbit
        self.idle_timer = 0.0
        self.user_rotated = False

        # Menu state
        self.menu_items = ["RESUME", "TRAIL COLOR", "RESTART", "TITLE", "EXIT"]
        self.selected_item = 0

    @property
    def gameplay_state(self):
        if len(self.context.state_manager.stack) > 1:
            state = self.context.state_manager.stack[-2]
            if hasattr(state, 'player'):
                return state
        return None

    def handle_event(self, event):
        gp = self.gameplay_state
        if not gp:
            return

        manager = self.context.state_manager

        # Mouse interactions
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left-click
                m_x, m_y = event.pos
                if m_x < 380:  # clicked inside the sidebar!
                    for i, item in enumerate(self.menu_items):
                        y_item = 140 + i * 80
                        if 20 <= m_x <= 355 and y_item - 6 <= m_y <= y_item + 36:
                            if self.selected_item == i:
                                self.trigger_action(item, manager)
                            else:
                                self.selected_item = i
                                self.context.sound.play_sfx("laser")
                            break
                        if item == "TRAIL COLOR":
                            y_dots = y_item + 46
                            for dot_idx in range(8):
                                cx = 50 + dot_idx * 38
                                if (m_x - cx) ** 2 + (m_y - y_dots) ** 2 <= 144:  # inside 12px radius
                                    gp.player.trail_color_index = dot_idx
                                    gp.player.change_trail_color(0)
                                    self.selected_item = i
                                    self.context.sound.play_sfx("laser")
                                    break
            elif event.button == 4:  # Scroll Up (Zoom In)
                self.orbit_distance = max(100.0, self.orbit_distance - 20.0)
                self.user_rotated = True
                self.idle_timer = 0.0
            elif event.button == 5:  # Scroll Down (Zoom Out)
                self.orbit_distance = min(700.0, self.orbit_distance + 20.0)
                self.user_rotated = True
                self.idle_timer = 0.0

        # Keyboard interactions
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_p, pygame.K_ESCAPE):
                manager.pop()
            elif event.key in (pygame.K_UP, pygame.K_w):
                self.selected_item = (self.selected_item - 1) % len(self.menu_items)
                self.context.sound.play_sfx("laser")
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected_item = (self.selected_item + 1) % len(self.menu_items)
                self.context.sound.play_sfx("laser")
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                if self.menu_items[self.selected_item] == "TRAIL COLOR":
                    gp.player.change_trail_color(-1)
                    self.context.sound.play_sfx("laser")
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                if self.menu_items[self.selected_item] == "TRAIL COLOR":
                    gp.player.change_trail_color(1)
                    self.context.sound.play_sfx("laser")
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.trigger_action(self.menu_items[self.selected_item], manager)

        self.context.handler.process_event(event)

    def update(self, dt, manager):
        gp = self.gameplay_state
        if not gp:
            return

        # Option / Pause button on controller resumes game
        if self.context.handler.just_pressed('Options'):
            manager.pop()
            return

        # D-pad controls for controller menu navigation
        if self.context.handler.just_pressed('DPad Up'):
            self.selected_item = (self.selected_item - 1) % len(self.menu_items)
            self.context.sound.play_sfx("laser")
        elif self.context.handler.just_pressed('DPad Down'):
            self.selected_item = (self.selected_item + 1) % len(self.menu_items)
            self.context.sound.play_sfx("laser")

        if self.menu_items[self.selected_item] == "TRAIL COLOR":
            if self.context.handler.just_pressed('DPad Left'):
                gp.player.change_trail_color(-1)
                self.context.sound.play_sfx("laser")
            elif self.context.handler.just_pressed('DPad Right'):
                gp.player.change_trail_color(1)
                self.context.sound.play_sfx("laser")

        if self.context.handler.just_pressed('X'):
            self.trigger_action(self.menu_items[self.selected_item], manager)

        # Manual Orbit Camera input checks
        lx, ly = self.context.handler.stick_left()
        rx, ry = self.context.handler.stick_right()
        cx = rx if abs(rx) > abs(lx) else lx
        cy = ry if abs(ry) > abs(ly) else ly

        # Keyboard key holdings for manual orbit
        keys = pygame.key.get_pressed()
        kb_yaw = 0.0
        kb_pitch = 0.0
        speed_mult = 1.8

        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            kb_yaw -= dt * speed_mult
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            kb_yaw += dt * speed_mult
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            kb_pitch -= dt * speed_mult
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            kb_pitch += dt * speed_mult

        if keys[pygame.K_q]:
            self.orbit_distance = max(100.0, self.orbit_distance - dt * 300.0)
            self.user_rotated = True
            self.idle_timer = 0.0
        if keys[pygame.K_e]:
            self.orbit_distance = min(700.0, self.orbit_distance + dt * 300.0)
            self.user_rotated = True
            self.idle_timer = 0.0

        # Mouse drag calculations
        m_pressed = pygame.mouse.get_pressed()
        m_rel = pygame.mouse.get_rel()
        m_pos = pygame.mouse.get_pos()
        mouse_active = False
        if m_pressed[0] and m_pos[0] > 380:
            self.orbit_yaw += m_rel[0] * 0.007
            self.orbit_pitch = max(-1.4, min(1.4, self.orbit_pitch + m_rel[1] * 0.007))
            mouse_active = True

        if abs(cx) > 0.05 or abs(cy) > 0.05 or abs(kb_yaw) > 0 or abs(kb_pitch) > 0 or mouse_active:
            self.orbit_yaw += cx * dt * 2.5 + kb_yaw
            self.orbit_pitch = max(-1.4, min(1.4, self.orbit_pitch + cy * dt * 2.5 + kb_pitch))
            self.user_rotated = True
            self.idle_timer = 0.0
        else:
            self.idle_timer += dt
            if self.idle_timer > 3.0:
                self.user_rotated = False

        # Controller bumper/trigger zooms
        if self.context.handler.held('R1') or self.context.handler.trigger_right() > 0.1:
            self.orbit_distance = max(100.0, self.orbit_distance - dt * 400.0)
            self.user_rotated = True
            self.idle_timer = 0.0
        if self.context.handler.held('L1') or self.context.handler.trigger_left() > 0.1:
            self.orbit_distance = min(700.0, self.orbit_distance + dt * 400.0)
            self.user_rotated = True
            self.idle_timer = 0.0

        # Auto orbit rotation
        if not self.user_rotated:
            self.orbit_yaw += dt * 0.15

        # Damped engine hum sound during pause
        if self.context.sound:
            self.context.sound.update_engine_hum(0.0, 0.0, 0.0, 0.0)

    def draw(self, screen):
        gp = self.gameplay_state
        if not gp:
            screen.fill((10, 10, 20))
            return

        # 1. Calculate Orbit Camera coordinates

        q_yaw = quat_from_axis_angle(0.0, 1.0, 0.0, self.orbit_yaw)
        q_pitch = quat_from_axis_angle(1.0, 0.0, 0.0, self.orbit_pitch)
        q_orbit = quat_mul(q_yaw, q_pitch)

        q_cam = quat_mul(gp.player.orientation, q_orbit)
        cam_fwd = get_forward_from_quat(q_cam)
        cam_pos = (
            gp.player.pos[0] - cam_fwd[0] * self.orbit_distance,
            gp.player.pos[1] - cam_fwd[1] * self.orbit_distance,
            gp.player.pos[2] - cam_fwd[2] * self.orbit_distance
        )

        # 2. Draw the 3D scene from the orbital camera view!
        gp.draw_photo_mode(screen, cam_pos, q_cam)

        # 3. Draw premium translucent sidebar glassmorphic overlay
        sidebar = pygame.Surface((380, self.context.H), pygame.SRCALPHA)
        # Deep dark cybernetic glass
        sidebar.fill((10, 10, 18, 215))
        # Sleek neon border on the right
        pygame.draw.line(sidebar, (45, 45, 65), (378, 0), (378, self.context.H), 1)
        pygame.draw.line(sidebar, (0, 180, 255), (379, 0), (379, self.context.H), 1)

        # Title text: SYSTEM PAUSED
        title_text = self.title_font.render("SYSTEM PAUSED", True, (255, 255, 255))
        # Draw a little neon highlight glow behind title
        pygame.draw.line(sidebar, (0, 180, 255), (25, 80), (355, 80), 2)
        sidebar.blit(title_text, (25, 30))

        # Draw interactive menu items
        for i, item in enumerate(self.menu_items):
            y_item = 140 + i * 80
            is_sel = (self.selected_item == i)

            if is_sel:
                # Glowing selection box
                pygame.draw.rect(sidebar, (0, 180, 255, 35), (20, y_item - 6, 335, 42), border_radius=4)
                pygame.draw.rect(sidebar, (0, 180, 255, 180), (20, y_item - 6, 335, 42), 1, border_radius=4)

                text_col = (255, 255, 255)
                # Caret indicators
                caret_l = self.menu_font.render("> ", True, (0, 180, 255))
                sidebar.blit(caret_l, (30, y_item))
            else:
                text_col = (130, 130, 140)

            # Render menu item text
            if item == "TRAIL COLOR":
                val_text = self.menu_font.render(f"TRAIL: {gp.player.trail_color_name}", True,
                                                 gp.player.trail_color if is_sel else text_col)
                sidebar.blit(val_text, (50 if is_sel else 40, y_item))

                # Draw neon cycling arrow guides if selected
                if is_sel:
                    arrow_l = self.menu_font.render("<", True, (0, 180, 255))
                    arrow_r = self.menu_font.render(">", True, (0, 180, 255))
                    sidebar.blit(arrow_l, (270, y_item))
                    sidebar.blit(arrow_r, (330, y_item))

                # Draw the glowing color beads selector below the item!
                y_dots = y_item + 46
                for dot_idx, (name, col) in enumerate(gp.player.trail_colors):
                    cx = 50 + dot_idx * 38
                    pygame.draw.circle(sidebar, col, (cx, y_dots), 10)
                    if dot_idx == gp.player.trail_color_index:
                        pygame.draw.circle(sidebar, (255, 255, 255), (cx, y_dots), 13, 2)
            else:
                lbl = self.menu_font.render(item, True, text_col)
                sidebar.blit(lbl, (50 if is_sel else 40, y_item))

        # 4. Render Mission/Tactical statistics panel at the bottom of the sidebar
        y_stats = self.context.H - 220
        pygame.draw.line(sidebar, (35, 35, 45), (25, y_stats), (355, y_stats), 1)

        stats_hdr = self.hint_font.render("TACTICAL DATA INTEGRITY", True, (0, 180, 255))
        sidebar.blit(stats_hdr, (25, y_stats + 12))

        acc_pct = (gp.player.shots_hit / max(1, gp.player.shots_fired)) * 100
        stats_list = [
            ("HULL STRENGTH", f"{int(gp.player.hp)} / {int(gp.player.max_hp)}",
             (255, 50, 50) if gp.player.hp < 30 else (220, 220, 220)),
            ("SHIELD POWER", f"{int(gp.player.shield)} / 100",
             (0, 180, 255) if gp.player.shield > 0 else (100, 100, 110)),
            ("MISSILES LOADED", f"{gp.player.missile_ammo} / 10", (255, 210, 60)),
            ("WEAPON ACCURACY", f"{acc_pct:.1f}%", (60, 220, 120)),
        ]

        for k, (label, val, val_col) in enumerate(stats_list):
            lbl_surf = self.hint_font.render(label, True, (130, 130, 140))
            val_surf = self.hint_font.render(val, True, val_col)
            sidebar.blit(lbl_surf, (25, y_stats + 42 + k * 28))
            sidebar.blit(val_surf, (355 - val_surf.get_width(), y_stats + 42 + k * 28))

        screen.blit(sidebar, (0, 0))

        # 5. Draw Orbit instructions HUD on the bottom-right side of screen!
        helper_bg = pygame.Surface((600, 40), pygame.SRCALPHA)
        helper_bg.fill((5, 5, 10, 160))
        pygame.draw.rect(helper_bg, (45, 45, 55), (0, 0, 600, 40), 1, border_radius=6)

        instructions = "[W/S/A/D or Mouse Drag] Orbit Camera  •  [Q/E or Scroll] Zoom  •  [UP/DOWN] Menu"
        instr_surf = self.hint_font.render(instructions, True, (200, 220, 255))
        helper_bg.blit(instr_surf, (300 - instr_surf.get_width() // 2, 20 - instr_surf.get_height() // 2))

        screen.blit(helper_bg, (self.context.W - 630, self.context.H - 60))

    def trigger_action(self, action, manager):
        self.context.sound.play_sfx("laser")
        if action == "RESUME":
            manager.pop()
        elif action == "TRAIL COLOR":
            self.gameplay_state.player.change_trail_color(1)
        elif action == "RESTART":
            manager.pop()
            manager.change(GameplayState(self.context))
        elif action == "TITLE":
            manager.pop()
            manager.change(TitleState(self.context))
        elif action == "EXIT":
            self.context.running = False


    
