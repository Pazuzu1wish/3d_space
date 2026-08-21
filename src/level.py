# src/level.py

import pygame
import math
from src.star import Star
from src.nebula import NebulaSystem
from src.asteroid import AsteroidField
from src.director import WaveDirector

class BaseLevel:
    """
    Unified Base Class representing a space mission or game mode.
    
    Manages the environmental layout, wave directors, waypoints, and maps
    gameplay callbacks to decouple level logic from the core physics engine.
    """
    def __init__(self, context, gameplay_state):
        self.context = context
        self.gameplay_state = gameplay_state
        self.stars = []
        self.nebulae = None
        self.asteroids = []
        self.waypoints = []
        self.director = None
        self.station = []

    def initialize(self):
        """Called once when entering the state to populate initial space layout."""
        pass

    def on_update(self, dt):
        """Lifecycle hook called every frame to update objectives, score decays, etc."""
        pass

    def on_enemy_killed(self, enemy_type):
        """Hook executed when any active enemy is destroyed."""
        pass

    def draw_hud_overlay(self, screen):
        """Draws level-specific UI (e.g., scores, combos, objective counters) over standard cockpit HUD."""
        pass


class ArcadeLevel(BaseLevel):
    """
    The classic Endless Arcade Mode.

    There is no fixed mission script — enemy waves are generated forever by
    the WaveDirector, always spawning near wherever the player currently is
    (never at some fixed point the player has to fly back to). Waves start
    easy and get steadily harder the longer the run goes on. The level also
    maintains a persistent score and a dynamic combo multiplier that decays
    over time if there's no combat activity.
    """
    def __init__(self, context, gameplay_state):
        super().__init__(context, gameplay_state)
        self.score = 0
        self.multiplier = 1.0
        self.combo_decay_rate = 0.15  # multiplier loss per second
        self._font = None

        # ── Roguelite in-run leveling ──
        self.player_level = 1
        self.xp = 0
        self.xp_to_next = self._xp_for_next_level()
        self.pending_level_ups = 0   # queued upgrade picks (a big kill can grant 2+ at once)

    def _xp_for_next_level(self):
        # Exponential curve: 100, 125, 156, 195, ... — quick early upgrades,
        # gently taper off as the run goes on.
        return int(100 * (1.25 ** (self.player_level - 1)))

    def initialize(self):
        # Setup environment and starfields relative to player
        player_pos = self.gameplay_state.player.pos
        self.stars = [Star(player_pos) for _ in range(150)]
        self.nebulae = NebulaSystem(count=6, area_radius=30000)

        # Endless wave mode: no fixed encounter script — the director
        # generates waves procedurally and spawns each one near the
        # player's current position, wherever the last wave ended.
        self.director = WaveDirector()

        # Spawn Space Station
        # self.station.append(SpaceStation(0, 0, 1000, 50))

        # A single asteroid field around the starting position for
        # atmosphere — waves handle all of the actual combat spawning.
        field = AsteroidField(player_pos, count=12, radius=25000)
        for a in field.asteroids:
            self.asteroids.append(a)
            self.gameplay_state.spatial.register_entity(a, (a.x, a.y, a.z))

        # No fixed objectives in endless mode — the waves come to the
        # player, so there's nowhere distant to point a waypoint at.
        self.waypoints = []

        # Font fallback setup
        try:
            self._font = pygame.font.Font("assets/fonts/interdictionexpand.ttf", 20)
        except FileNotFoundError:
            self._font = pygame.font.Font(None, 24)

    def on_update(self, dt):
        # Gradual multiplier decay
        if self.multiplier > 1.0:
            self.multiplier = max(1.0, self.multiplier - self.combo_decay_rate * dt)

    def on_enemy_killed(self, enemy_type):
        # Award base points modified by current combo level
        points_map = {
            'SuicideDrone': 50,
            'Dogfighter': 150,
            'Sniper': 200,
            'Minelayer': 250,
            'StealthInterceptor': 300,
            'Carrier': 1000
        }
        base_val = points_map.get(enemy_type, 100)
        self.score += int(base_val * self.multiplier)
        
        # Build combo up to a maximum limit (e.g. 5.0x)
        self.multiplier = min(5.0, self.multiplier + 0.25)

        # ── XP / leveling (flat, uncombo'd so it stays predictable) ──
        xp_map = {
            'SuicideDrone': 20,
            'Dogfighter': 45,
            'Sniper': 60,
            'Minelayer': 70,
            'StealthInterceptor': 85,
            'Carrier': 250,
        }
        self.xp += xp_map.get(enemy_type, 30)
        while self.xp >= self.xp_to_next:
            self.xp -= self.xp_to_next
            self.player_level += 1
            self.xp_to_next = self._xp_for_next_level()
            self.pending_level_ups += 1

    def draw_hud_overlay(self, screen):
        # Layered UI: Draw Wave / Score & Multiplier on top-right space
        director = self.director

        wave_txt = f"WAVE {director.wave_number}"
        score_txt = f"SCORE: {self.score:,}"
        mult_txt = f"COMBO: {self.multiplier:.2f}X"

        col_mult = (0, 255, 128) if self.multiplier > 1.0 else (140, 140, 160)

        surf_wave = self._font.render(wave_txt, True, (0, 220, 255))
        surf_score = self._font.render(score_txt, True, (255, 220, 0))
        surf_mult = self._font.render(mult_txt, True, col_mult)
        surf_level = self._font.render(
            f"LEVEL {self.player_level}  ({self.xp}/{self.xp_to_next} XP)", True, (180, 100, 255)
        )

        r_edge = self.gameplay_state.W - 40
        y = 40
        screen.blit(surf_wave, (r_edge - surf_wave.get_width(), y))
        y += surf_wave.get_height() + 6
        screen.blit(surf_score, (r_edge - surf_score.get_width(), y))
        y += surf_score.get_height() + 6
        screen.blit(surf_mult, (r_edge - surf_mult.get_width(), y))
        y += surf_mult.get_height() + 6
        screen.blit(surf_level, (r_edge - surf_level.get_width(), y))

        # Countdown to the next wave while the arena is quiet
        if not director.wave_active:
            y += surf_level.get_height() + 6
            countdown = max(0.0, director.intermission_timer)
            next_txt = f"NEXT WAVE: {countdown:0.1f}s"
            surf_next = self._font.render(next_txt, True, (200, 200, 60))
            screen.blit(surf_next, (r_edge - surf_next.get_width(), y))
