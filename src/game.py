# pyrefly: ignore [missing-import]
import pygame
from random import choice
from src.constants import SCREEN_WIDTH, SCREEN_HEIGHT, FULLSCREEN
from src.controller import DS4Input
from src.sound_handler import SoundHandler
from src.save_data import SaveData
from src.asteroid import init_asteroid_bank
from src.mesh_loader import preload_all_meshes
from src.state import (StateManager, TitleState, GameplayState, PauseState,
                          GameOverState)

# ──────────────────────────────────────────────
# Game Context / App Base
# ──────────────────────────────────────────────

class Game:
    def __init__(self):
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=2048)
        pygame.init()
        preload_all_meshes()
        init_asteroid_bank()
        self.init_sounds()
        self.select_random_bgm()
        self.W, self.H = SCREEN_WIDTH, SCREEN_HEIGHT
        flags = pygame.FULLSCREEN | pygame.SCALED if FULLSCREEN else 0
        self.screen = pygame.display.set_mode((self.W, self.H), flags)
        pygame.display.set_caption("🚀 3D Cockpit Dogfighter")
        self.clock = pygame.time.Clock()
        self.handler = DS4Input()
        self.handler.init()
        self.state_manager = StateManager(self)
        self.save_data = SaveData.load()   # load persistent state
        self.state_manager.push(TitleState(self))
        self.running = True

# ──────────────────────────────────────────────
# Sound Init
# ──────────────────────────────────────────────

    def init_sounds(self):
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

# ──────────────────────────────────────────────
# Random bgm selection
# ──────────────────────────────────────────────

    def select_random_bgm(self):
        self.music_file = choice([
            self.sound_folder + "bgm_drone.wav",
            self.sound_folder + "bgm_drone2.wav",
            self.sound_folder + "bgm_drone3.wav"
        ])
        return self.music_file

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
