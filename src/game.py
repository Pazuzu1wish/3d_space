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
import moderngl
import numpy as np

class UIPresenter:
    def __init__(self, W, H):
        self.ctx = moderngl.create_context()
        self.prog = self.ctx.program(
            vertex_shader="#version 330\nin vec2 in_vert; in vec2 in_texcoord; out vec2 v_texcoord; void main() { gl_Position = vec4(in_vert, 0.0, 1.0); v_texcoord = in_texcoord; }",
            fragment_shader="#version 330\nuniform sampler2D tex; in vec2 v_texcoord; out vec4 f_color; void main() { f_color = texture(tex, v_texcoord); }"
        )
        quad_verts = np.array([-1, 1, 0, 1,  -1, -1, 0, 0,  1, -1, 1, 0,  -1, 1, 0, 1,  1, -1, 1, 0,  1, 1, 1, 1], dtype='f4')
        self.vbo = self.ctx.buffer(quad_verts.tobytes())
        self.vao = self.ctx.vertex_array(self.prog, [(self.vbo, '2f 2f', 'in_vert', 'in_texcoord')])
        self.tex = self.ctx.texture((W, H), 4)
        self.tex.filter = (moderngl.NEAREST, moderngl.NEAREST)

    def present(self, surface):
        self.ctx.clear(0, 0, 0, 1)
        raw_bytes = pygame.image.tobytes(surface, "RGBA", True)
        self.tex.write(raw_bytes)
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.tex.use(0)
        self.prog['tex'].value = 0
        self.vao.render(moderngl.TRIANGLES)

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
        flags = pygame.OPENGL | pygame.DOUBLEBUF | (pygame.FULLSCREEN | pygame.SCALED if FULLSCREEN else 0)
        self.opengl_screen = pygame.display.set_mode((self.W, self.H), flags)
        self.screen = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self.ui_presenter = UIPresenter(self.W, self.H)
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
                self.screen.fill((0, 0, 0, 0)) # Clear UI surface with transparency
                self.state_manager.current.draw(self.screen)
                
            # If there's an active renderer, tell it to present the screen surface to ModernGL
            current_state = self.state_manager.current
            renderer = getattr(current_state, 'renderer', None)
            if not renderer and hasattr(current_state, 'title_cinematic'):
                renderer = getattr(current_state.title_cinematic, 'renderer', None)
                
            if renderer:
                renderer.present(self.screen)
            else:
                self.ui_presenter.present(self.screen)

            # Device input updates must execute on a polling basis at the end of the frame
            self.handler.update()
            pygame.display.flip()

        self.sound.stop_music()
        pygame.quit()
