# src/level.py

import pygame
import math
from src.star import Star
from src.nebula import NebulaSystem
from src.asteroid import AsteroidField
from src.director import WaveDirector
from src.space_station import SpaceStation
from src.encounters import ARCADE_ENCOUNTER_SCRIPT

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
    
    Spawns wave-based threats, maintains a persistent score, and tracks a dynamic 
    combo multiplier that decays over time if there's no combat activity.
    """
    def __init__(self, context, gameplay_state):
        super().__init__(context, gameplay_state)
        self.score = 0
        self.multiplier = 1.0
        self.combo_decay_rate = 0.15  # multiplier loss per second
        self._font = None

    def initialize(self):
        # Setup environment and starfields relative to player
        player_pos = self.gameplay_state.player.pos
        self.stars = [Star(player_pos) for _ in range(150)]
        self.nebulae = NebulaSystem(count=6, area_radius=30000)
        self.director = WaveDirector(ARCADE_ENCOUNTER_SCRIPT)

        # Spawn Space Station
        self.station.append(SpaceStation(0, 0, 1000, 50))

        # Setup and register Asteroids directly into the engine's spatial partitions
        for enc in ARCADE_ENCOUNTER_SCRIPT:
            field = AsteroidField(enc['origin'], count=12, radius=25000)
            for a in field.asteroids:
                self.asteroids.append(a)
                self.gameplay_state.spatial.register_entity(a, (a.x, a.y, a.z))

        # Core navigation points
        self.waypoints = [
            {'pos': (0, 0, 75000), 'label': 'Enemy Stronghold', 'active': True, 'color': (0, 255, 100, 200)},
            {'pos': (2000, -500, 25000), 'label': 'CARRIER STRIKE GROUP', 'active': True, 'color': (255, 200, 0, 200)},
            {'pos': (0, 0, 0), 'label': 'ORIGIN', 'active': True, 'color': (0, 200, 255, 200)},
            {'pos': (0, 0, 1000), 'label': 'SPACE STATION', 'active': True, 'color': (0, 255, 0, 200)}
        ]

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

    def draw_hud_overlay(self, screen):
        # Layered UI: Draw Score & Multiplier on top-right space
        score_txt = f"SCORE: {self.score:,}"
        mult_txt = f"COMBO: {self.multiplier:.2f}X"

        col_mult = (0, 255, 128) if self.multiplier > 1.0 else (140, 140, 160)
        
        surf_score = self._font.render(score_txt, True, (255, 220, 0))
        surf_mult = self._font.render(mult_txt, True, col_mult)

        r_edge = self.gameplay_state.W - 40
        screen.blit(surf_score, (r_edge - surf_score.get_width(), 40))
        screen.blit(surf_mult, (r_edge - surf_mult.get_width(), 40 + surf_score.get_height() + 6))