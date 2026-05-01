"""
entity_viewer.py
----------------
Standalone entity inspection tool. Load any drawable entity and
rotate / scale it interactively. Mouse drag rotates, scroll wheel
scales, keyboard shortcuts for reset / export / quit.

Usage
-----
    python entity_viewer.py

Or import and run programmatically:

    from entity_viewer import EntityViewer
    from entities.enemy import EnemyShip

    viewer = EntityViewer(entity_factory=EnemyShip)
    viewer.run()

Controls
--------
    Left-drag          Rotate (free)
    Scroll up/down     Scale +/-
    R                  Reset transform
    G                  Toggle grid
    T                  Toggle trails
    S                  Screenshot (saves to ./screenshots/)
    Q / Escape         Quit
    Arrow Left/Right   Step rotation ±5°
    Arrow Up/Down      Step scale ±0.1
"""

import pygame
import math
import os
import datetime

# ── colours ──────────────────────────────────────────────────────────────────
BG         = (5, 5, 12)
GRID_MAJOR = (25, 30, 45)
GRID_MINOR = (15, 18, 28)
AXIS_X     = (180, 40, 40)
AXIS_Y     = (40, 180, 40)
HUD_COL    = (140, 200, 255)
HUD_DIM    = (60, 90, 130)
ACCENT     = (80, 160, 255)
WARN       = (255, 180, 40)


# ── default entity: enemy ship ────────────────────────────────────────────────
class DefaultEnemyShip:
    """
    Self-contained enemy ship drawn in pure pygame vectors.
    Swap this class out for your real entity once integrated —
    just ensure it exposes  draw(surface, pos, angle, scale)  and
    optionally  draw_trails(surface, pos, angle, scale).
    """

    # Ship geometry defined as unit vectors (scaled at draw time)
    HULL = [
        (0,   -1.0),   # nose
        (0.45, -0.2),
        (0.55,  0.3),
        (0.25,  0.55),
        (0.0,   0.4),
        (-0.25, 0.55),
        (-0.55, 0.3),
        (-0.45,-0.2),
    ]

    COCKPIT = [
        (0,   -0.65),
        (0.18, -0.1),
        (0,    0.05),
        (-0.18,-0.1),
    ]

    # Wing detail lines [ (x1,y1), (x2,y2) ]
    WING_LINES = [
        [(0.08, 0.1),  (0.45, 0.25)],
        [(0.08, 0.25), (0.42, 0.42)],
        [(-0.08, 0.1), (-0.45, 0.25)],
        [(-0.08, 0.25),(-0.42, 0.42)],
    ]

    # Engine nacelle positions (local coords)
    ENGINES = [(0.32, 0.45), (-0.32, 0.45)]
    ENGINE_R = 0.09

    # Trail spawn points (local coords)
    TRAIL_ORIGINS = [(0.32, 0.5), (-0.32, 0.5), (0.0, 0.38)]

    # Hull colour scheme
    HULL_FILL    = (28, 36, 52)
    HULL_STROKE  = (60, 120, 200)
    COCKPIT_FILL = (20, 180, 220)
    ENGINE_FILL  = (40, 50, 70)
    ENGINE_GLOW  = (80, 160, 255)

    def __init__(self):
        self.trail_particles = []
        self.time = 0

    def _transform(self, points, cx, cy, angle_deg, scale):
        """Rotate + scale a list of (x, y) unit coords around cx, cy."""
        rad = math.radians(angle_deg)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        out = []
        for px, py in points:
            rx = px * cos_a - py * sin_a
            ry = px * sin_a + py * cos_a
            out.append((cx + rx * scale, cy + ry * scale))
        return out

    def _tp(self, lx, ly, cx, cy, angle_deg, scale):
        """Transform a single local point."""
        return self._transform([(lx, ly)], cx, cy, angle_deg, scale)[0]

    def update_trails(self, pos, angle, scale):
        """Call once per frame to keep trail particles alive."""
        cx, cy = pos
        self.time += 1
        # spawn
        for ox, oy in self.TRAIL_ORIGINS:
            wx, wy = self._tp(ox, oy, cx, cy, angle, scale)
            self.trail_particles.append({
                "x": wx, "y": wy,
                "life": 1.0,
                "decay": 0.04 + 0.02 * (hash((ox, oy, self.time)) % 10) / 10,
                "r": 3 + int(abs(ox) * scale * 0.15),
            })
        # age
        self.trail_particles = [
            {**p, "life": p["life"] - p["decay"]}
            for p in self.trail_particles
            if p["life"] > 0
        ]

    def draw_trails(self, surface, pos, angle, scale):
        for p in self.trail_particles:
            alpha = int(p["life"] * 200)
            r = int(p["r"] * p["life"])
            if r < 1:
                continue
            colour = (
                int(60 * p["life"]),
                int(120 * p["life"]),
                min(255, int(255 * p["life"])),
            )
            glow_surf = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (*colour, alpha // 2), (r * 2, r * 2), r * 2)
            pygame.draw.circle(glow_surf, (*colour, alpha),      (r * 2, r * 2), r)
            surface.blit(glow_surf, (int(p["x"]) - r * 2, int(p["y"]) - r * 2))

    def draw(self, surface, pos, angle, scale):
        cx, cy = pos

        # hull
        hull_pts = self._transform(self.HULL, cx, cy, angle, scale)
        pygame.draw.polygon(surface, self.HULL_FILL,   hull_pts)
        pygame.draw.polygon(surface, self.HULL_STROKE, hull_pts, 2)

        # wing detail lines
        for seg in self.WING_LINES:
            p1 = self._tp(*seg[0], cx, cy, angle, scale)
            p2 = self._tp(*seg[1], cx, cy, angle, scale)
            pygame.draw.line(surface, self.HULL_STROKE, p1, p2, 1)

        # engines
        for ex, ey in self.ENGINES:
            ep = self._tp(ex, ey, cx, cy, angle, scale)
            er = int(self.ENGINE_R * scale)
            pygame.draw.circle(surface, self.ENGINE_FILL, (int(ep[0]), int(ep[1])), er)
            pygame.draw.circle(surface, self.ENGINE_GLOW, (int(ep[0]), int(ep[1])), er, 2)
            # inner glow dot
            pygame.draw.circle(surface, (180, 220, 255), (int(ep[0]), int(ep[1])), max(1, er // 3))

        # cockpit
        cock_pts = self._transform(self.COCKPIT, cx, cy, angle, scale)
        pygame.draw.polygon(surface, self.COCKPIT_FILL, cock_pts)


# ── main viewer ───────────────────────────────────────────────────────────────
class EntityViewer:
    """
    Interactive viewer. Pass an entity_factory callable that returns
    an object with .draw(surface, pos, angle, scale) and optionally
    .draw_trails(surface, pos, angle, scale) and
    .update_trails(pos, angle, scale).
    """

    WIDTH, HEIGHT = 960, 720
    FPS           = 60
    FONT_NAME     = None   # use pygame default; swap for a monospace path

    def __init__(self, entity_factory=None, title="Entity Viewer"):
        pygame.init()
        self.screen  = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        pygame.display.set_caption(title)
        self.clock   = pygame.time.Clock()
        self.font_sm = pygame.font.SysFont("monospace", 13)
        self.font_md = pygame.font.SysFont("monospace", 16, bold=True)

        factory = entity_factory or DefaultEnemyShip
        self.entity = factory()
        self.has_trails  = hasattr(self.entity, "draw_trails")
        self.has_update  = hasattr(self.entity, "update_trails")

        # transform state
        self.angle  = 0.0
        self.scale  = 80.0    # pixels per unit
        self.pos    = [self.WIDTH // 2, self.HEIGHT // 2]

        # interaction state
        self.dragging     = False
        self.drag_start   = (0, 0)
        self.angle_start  = 0.0
        self.show_grid    = True
        self.show_trails  = True
        self.running      = True

        os.makedirs("../screenshots", exist_ok=True)

    # ── grid ──────────────────────────────────────────────────────────────────
    def _draw_grid(self):
        surf = self.screen
        w, h = self.WIDTH, self.HEIGHT

        # minor grid every 40px
        for x in range(0, w, 40):
            pygame.draw.line(surf, GRID_MINOR, (x, 0), (x, h))
        for y in range(0, h, 40):
            pygame.draw.line(surf, GRID_MINOR, (0, y), (w, y))

        # major grid every 200px
        for x in range(0, w, 200):
            pygame.draw.line(surf, GRID_MAJOR, (x, 0), (x, h))
        for y in range(0, h, 200):
            pygame.draw.line(surf, GRID_MAJOR, (0, y), (w, y))

        # axes through centre
        cx, cy = int(self.pos[0]), int(self.pos[1])
        pygame.draw.line(surf, AXIS_X, (0, cy), (w, cy), 1)
        pygame.draw.line(surf, AXIS_Y, (cx, 0), (cx, h), 1)

        # centre dot
        pygame.draw.circle(surf, ACCENT, (cx, cy), 4)
        pygame.draw.circle(surf, BG,     (cx, cy), 2)

    # ── HUD ───────────────────────────────────────────────────────────────────
    def _draw_hud(self):
        lines = [
            ("ANGLE",  f"{self.angle % 360:.1f}°"),
            ("SCALE",  f"{self.scale:.1f}px"),
            ("",       ""),
            ("DRAG",   "rotate"),
            ("SCROLL", "scale"),
            ("ARROWS", "fine adjust"),
            ("R",      "reset"),
            ("G",      "grid"),
            ("T",      "trails"),
            ("S",      "screenshot"),
            ("Q/ESC",  "quit"),
        ]

        x, y = 18, 18
        for label, value in lines:
            if not label and not value:
                y += 8
                continue
            lbl_surf = self.font_sm.render(label, True, HUD_DIM)
            val_surf = self.font_sm.render(value,  True, HUD_COL)
            self.screen.blit(lbl_surf, (x, y))
            self.screen.blit(val_surf, (x + 80, y))
            y += 18

        # entity class name top-right
        name = type(self.entity).__name__
        name_surf = self.font_md.render(name, True, ACCENT)
        self.screen.blit(name_surf, (self.WIDTH - name_surf.get_width() - 18, 18))

        # trail toggle indicator
        if self.has_trails:
            t_col = ACCENT if self.show_trails else HUD_DIM
            t_surf = self.font_sm.render(
                f"trails {'ON' if self.show_trails else 'OFF'}", True, t_col)
            self.screen.blit(t_surf, (self.WIDTH - t_surf.get_width() - 18, 44))

    # ── drag helpers ──────────────────────────────────────────────────────────
    def _angle_from_mouse(self, mx, my):
        """Map horizontal mouse drag → rotation angle."""
        dx = mx - self.drag_start[0]
        return self.angle_start + dx * 0.5   # 0.5 deg per pixel

    # ── screenshot ────────────────────────────────────────────────────────────
    def _save_screenshot(self):
        ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"screenshots/{type(self.entity).__name__}_{ts}.png"
        pygame.image.save(self.screen, name)
        print(f"[viewer] saved {name}")

    # ── event handling ────────────────────────────────────────────────────────
    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                k = event.key
                if k in (pygame.K_q, pygame.K_ESCAPE):
                    self.running = False
                elif k == pygame.K_r:
                    self.angle = 0.0
                    self.scale = 80.0
                    self.pos   = [self.WIDTH // 2, self.HEIGHT // 2]
                    if hasattr(self.entity, "trail_particles"):
                        self.entity.trail_particles = []
                elif k == pygame.K_g:
                    self.show_grid = not self.show_grid
                elif k == pygame.K_t:
                    self.show_trails = not self.show_trails
                elif k == pygame.K_s:
                    self._save_screenshot()
                elif k == pygame.K_LEFT:
                    self.angle -= 5.0
                elif k == pygame.K_RIGHT:
                    self.angle += 5.0
                elif k == pygame.K_UP:
                    self.scale = min(400.0, self.scale + 10.0)
                elif k == pygame.K_DOWN:
                    self.scale = max(10.0, self.scale - 10.0)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    self.dragging    = True
                    self.drag_start  = event.pos
                    self.angle_start = self.angle
                elif event.button == 4:   # scroll up
                    self.scale = min(400.0, self.scale * 1.08)
                elif event.button == 5:   # scroll down
                    self.scale = max(10.0, self.scale / 1.08)

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.dragging = False

            elif event.type == pygame.MOUSEMOTION:
                if self.dragging:
                    self.angle = self._angle_from_mouse(*event.pos)

    # ── main loop ─────────────────────────────────────────────────────────────
    def run(self):
        while self.running:
            self._handle_events()

            self.screen.fill(BG)

            if self.show_grid:
                self._draw_grid()

            pos_tuple = (self.pos[0], self.pos[1])

            # trails behind entity
            if self.has_trails and self.show_trails:
                if self.has_update:
                    self.entity.update_trails(pos_tuple, self.angle, self.scale)
                self.entity.draw_trails(self.screen, pos_tuple, self.angle, self.scale)

            # entity
            self.entity.draw(self.screen, pos_tuple, self.angle, self.scale)

            self._draw_hud()

            pygame.display.flip()
            self.clock.tick(self.FPS)

        pygame.quit()


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # swap DefaultEnemyShip for any class that matches the draw() interface
    viewer = EntityViewer(entity_factory=DefaultEnemyShip, title="Enemy Ship — Entity Viewer")
    viewer.run()