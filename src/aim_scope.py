import pygame
import math

from src.camera import Camera
from src.renderer import RenderPipeline
from src.math_engine import calculate_lead_position
from src.constants import (
    AIM_MODE_THRESHOLD,
    AIM_MAGNIFICATION,
    AIM_MAGNIFICATION_MIN,
    AIM_MAGNIFICATION_MAX,
    AIM_WINDOW_SIZE,
    AIM_WINDOW_POS,
    AIM_WINDOW_BORDER_COLOR,
    AIM_WINDOW_CROSSHAIR_COLOR,
    PLAYER_LASER_SPEED,
)


class AimScope:
    """
    Self-contained magnified aim window.

    Owns its own Camera, RenderPipeline, and Surface so it can do a full
    second render pass without touching the main pipeline.

    Usage:
        # init (once, in GameplayState.__init__)
        self.aim_scope = AimScope(main_camera, laser_pool, particle_pool)

        # update (in GameplayState.update)
        self.aim_scope.update(handler.trigger_left(), pygame.key.get_pressed())

        # draw (in GameplayState.draw, after main renderer.render())
        self.aim_scope.draw(screen, player, visible_entities, stars)
    """

    def __init__(self, main_camera, laser_pool, particle_pool):
        self._main_camera   = main_camera
        self._laser_pool    = laser_pool
        self._particle_pool = particle_pool

        self.current_magnification = 1.0

        self._surf     = pygame.Surface((AIM_WINDOW_SIZE, AIM_WINDOW_SIZE), pygame.SRCALPHA)
        self._camera   = Camera(AIM_WINDOW_SIZE, AIM_WINDOW_SIZE)
        self._renderer = RenderPipeline(self._camera)

        self._font = pygame.font.Font("assets/fonts/interdictionexpand.ttf", 14)

    # ── public ────────────────────────────────────────────────────────────

    @property
    def active(self):
        return self.current_magnification > 1.05

    def update(self, l2_val, keys):
        """Advance magnification lerp. Call every frame regardless of active state."""
        if l2_val > AIM_MODE_THRESHOLD:
            t = (l2_val - AIM_MODE_THRESHOLD) / (1.0 - AIM_MODE_THRESHOLD)
            target = AIM_MAGNIFICATION_MIN + t * (AIM_MAGNIFICATION_MAX - AIM_MAGNIFICATION_MIN)
        elif keys[pygame.K_LSHIFT]:
            target = AIM_MAGNIFICATION
        else:
            target = 1.0

        self.current_magnification += (target - self.current_magnification) * 0.15

    def draw(self, screen, player, visible_entities, stars):
        """
        Full second-pass render into the aim window surface, then blit to screen.
        No-ops if not active.
        """
        if not self.active:
            return

        self._surf.fill((5, 5, 25, 200))

        # Sync camera to player with boosted FOV
        self._camera.fov = self._main_camera.fov * self.current_magnification//2
        self._camera.update(player.pos, player.orientation)
        self._renderer.clear()

        # ── scene render pass ─────────────────────────────────────────────
        for star in stars:
            star.submit_to_renderer(self._renderer, player.pos)

        for obj in visible_entities:
            if self._camera.sphere_in_frustum(obj.x, obj.y, obj.z, getattr(obj, 'hit_radius', 500)):
                obj.submit_to_renderer(self._renderer)

        for l in self._laser_pool.get_active():
            if self._camera.sphere_in_frustum(l.x, l.y, l.z, 200):
                l.submit_to_renderer(self._renderer)

        self._particle_pool.submit_to_renderer(self._renderer, self._camera)
        self._renderer.render(self._surf)

        # ── pip lead indicator ────────────────────────────────────────────
        self._draw_pip(player)

        # ── crosshair ─────────────────────────────────────────────────────
        self._draw_crosshair()

        # ── blit surface and frame onto screen ────────────────────────────
        screen.blit(self._surf, AIM_WINDOW_POS)
        self._draw_frame(screen)

    # ── private ───────────────────────────────────────────────────────────

    def _draw_pip(self, player):
        """Project lead position into scope space and draw diamond indicator."""
        if not player.active_target:
            return

        target = player.active_target

        lead = calculate_lead_position(
            tuple(player.pos),
            tuple(player.vel),
            (target.x, target.y, target.z),
            (target.vx, target.vy, target.vz),
            PLAYER_LASER_SPEED,
        )

        # lead returns target_pos as fallback when no intercept — still useful
        lx, ly, lz = lead
        cx, cy, cz = self._camera.world_to_camera(lx, ly, lz)
        proj = self._camera.project(cx, cy, cz)
        if not proj:
            return

        psx, psy, _ = proj
        pts = [
            (psx,     psy - 8),
            (psx + 8, psy    ),
            (psx,     psy + 8),
            (psx - 8, psy    ),
        ]
        pygame.draw.polygon(self._surf, (255, 255, 0), pts, 1)
        pygame.draw.circle(self._surf, (255, 255, 0), (psx, psy), 2)

    def _draw_crosshair(self):
        mid = AIM_WINDOW_SIZE // 2
        col = AIM_WINDOW_CROSSHAIR_COLOR
        pygame.draw.line(self._surf, col, (mid - 20, mid), (mid + 20, mid), 1)
        pygame.draw.line(self._surf, col, (mid, mid - 20), (mid, mid + 20), 1)
        pygame.draw.circle(self._surf, col, (mid, mid), 4, 1)
        lbl = self._font.render("MAGNIFIED AIM", True, (0, 200, 255))
        self._surf.blit(lbl, (10, 10))

    def _draw_frame(self, screen):
        """Corner bracket decoration around the scope window on the main screen."""
        x, y = AIM_WINDOW_POS
        w = h = AIM_WINDOW_SIZE
        c_len = 30

        pygame.draw.rect(screen, AIM_WINDOW_BORDER_COLOR,
                         (x, y, w, h), 2)

        corners = [
            # top-left
            ((x-2,   y-2),   (x+c_len, y-2  )),
            ((x-2,   y-2),   (x-2,     y+c_len)),
            # top-right
            ((x+w-c_len, y-2),   (x+w+2, y-2  )),
            ((x+w+2,     y-2),   (x+w+2, y+c_len)),
            # bottom-left
            ((x-2,   y+h-c_len), (x-2,   y+h+2)),
            ((x-2,   y+h+2),     (x+c_len, y+h+2)),
            # bottom-right
            ((x+w-c_len, y+h+2), (x+w+2, y+h+2)),
            ((x+w+2,     y+h-c_len), (x+w+2, y+h+2)),
        ]
        for p1, p2 in corners:
            pygame.draw.line(screen, (255, 255, 255), p1, p2, 1)