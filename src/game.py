# pyrefly: ignore [missing-import]
from random import choice
import pygame
import math
from src.save_data import RunResult, SaveData
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
from src.state import State, StateManager
from src.aim_scope import AimScope

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
        self.spatial = SpatialPartition(cell_size=1000.0)

        # Render tools
        self.camera = Camera(self.W, self.H)
        self.renderer = RenderPipeline(self.camera)

        # Initialize aim scope
        self.aim_scope = AimScope(self.camera, self.laser_pool, self.particle_pool)
        
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

        # Update aim scope
        self.aim_scope.update(
            self.context.handler.trigger_left(),
            keys,
            )

        # Handle Death
        if self.player.hp <= 0:
            result = RunResult(
                kills         = self.director.kills,
                survival_time = self.director.elapsed,
                shots_fired   = self.player.shots_fired,
                shots_hit     = self.player.shots_hit,
                damage_taken  = self.player.damage_taken,
                max_hp        = self.player.max_hp
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
                        pygame.draw.line(screen, (255, 255, 255), (jx, jy), (self.W // 2, self.H // 2), max(1, thickness - 3))
                    glare = int(SNIPER_GLARE_MULTIPLIER * intensity * scale)
                    if glare > 0:
                        pygame.draw.circle(screen, (255, 50, 50), (jx, jy), glare)

        

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
                self.director.kills.append(type(e).__name__)
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
                        self.player.shots_hit += 1
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
        self.result  = result
 
        # Persist immediately on construction
        self.context.save_data.record_run(result)
        self.context.save_data.save()
 
        self._build_fonts()
        self._anim_timer  = 0.0     # drives line-by-line reveal
        self._lines_shown = 0
        self._done        = False   # all lines revealed
 
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
            ls = font.render(left,  True, color_l)
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
 
        from collections import Counter
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
        self._font_med   = pygame.font.Font(path, 28)
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
                f"{i+1}.  {s['final_score']:>10,}   {len(s['kills'])}k", True, color
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
        self.pause_font = pygame.font.Font("assets/fonts/interdictionexpand.ttf", 72)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_p:
            self.context.state_manager.pop()
        self.context.handler.process_event(event)

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
        self.save_data = SaveData.load()   # load persistent state
        self.state_manager.push(TitleState(self))
        self.running = True


# ──────────────────────────────────────────────
# Main Loop
# ──────────────────────────────────────────────

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