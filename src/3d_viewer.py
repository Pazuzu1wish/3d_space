import sys
from math_engine import *
from enemy import *
from controller import DS4Input
from cockpit import custom_font
from constants import HUD_RED


# ==========================================
# 3D VIEWER APP
# ==========================================

class Viewer:
    def __init__(self):
        pygame.init()
        self.W, self.H = 1280, 760
        self.screen = pygame.display.set_mode((self.W, self.H))
        pygame.display.set_caption("3D Entity Viewer - Ship Modeler")
        self.clock = pygame.time.Clock()

        # Instantiate the controller handler
        self.handler = DS4Input

        # Instantiate the ship to view
        self.ship = Sniper(0, 0, 0)

        # Viewer Camera & State
        self.camera_z = 250.0  # Distance from object (Zoom)
        self.fov = 400
        self.obj_quat = quat_identity()  # The rotation of the ship in the viewer

        # Interaction state
        self.is_dragging = False
        self.last_mouse_pos = (0, 0)

        # Particles to simulate trails sitting still in 3D
        self.particles = []

        _FONT_CACHE = {}

    def update_trails(self, dt):
        # 1. Spawn new particles at engine offsets
        for offset in self.ship.engine_offsets:
            # Rotate offset to match current ship viewing angle
            rx, ry, rz = quat_rotate_vec(self.obj_quat, offset)

            # Trails flow backwards relative to ship's local Z
            # Local backward is (0, 0, -1), rotate it to global
            bx, by, bz = quat_rotate_vec(self.obj_quat, (0, 0, -150))

            self.particles.append({
                'pos': [rx, ry, rz],
                'vel': [bx + random.uniform(-10, 10), by + random.uniform(-10, 10), bz + random.uniform(-10, 10)],
                'life': self.ship.trail_life,
                'max_life': self.ship.trail_life
            })

        # 2. Update existing particles
        for p in self.particles:
            p['pos'][0] += p['vel'][0] * dt
            p['pos'][1] += p['vel'][1] * dt
            p['pos'][2] += p['vel'][2] * dt
            p['life'] -= dt

        self.particles = [p for p in self.particles if p['life'] > 0]

    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    self.is_dragging = True
                    self.last_mouse_pos = event.pos
                elif event.button == 4:
                    self.camera_z = max(50, self.camera_z - 20)
                elif event.button == 5:
                    self.camera_z += 20

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.is_dragging = False

            elif event.type == pygame.MOUSEMOTION and self.is_dragging:
                dx = event.pos[0] - self.last_mouse_pos[0]
                dy = event.pos[1] - self.last_mouse_pos[1]
                self.last_mouse_pos = event.pos

                self.obj_quat = rotate_yaw(self.obj_quat, dx * 0.01)
                self.obj_quat = rotate_pitch(self.obj_quat, dy * 0.01)

        return True

    def build_render_queue(self):
        cx, cy = self.W // 2, self.H // 2

        rotated_verts = []
        for vx, vy, vz in self.ship.verts:
            rx, ry, rz = quat_rotate_vec(self.obj_quat, (vx, vy, vz))
            rz += self.camera_z
            rotated_verts.append((rx, ry, rz))

        faces = []

        for face in self.ship.faces:
            v0, v1, v2 = [rotated_verts[i] for i in face]

            # normal
            dx1, dy1, dz1 = v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2]
            dx2, dy2, dz2 = v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2]

            nx = dy1 * dz2 - dz1 * dy2
            ny = dz1 * dx2 - dx1 * dz2
            nz = dx1 * dy2 - dy1 * dx2

            # proper culling (fixed version)
            vx, vy, vz = -v0[0], -v0[1], -v0[2]
            if nx * vx + ny * vy + nz * vz <= 0:
                continue

            # lighting
            mag = math.sqrt(nx * nx + ny * ny + nz * nz) or 1
            light_dot = max(0.2, (nx * 0.5 + ny * 0.5 - nz * 0.7) / mag)

            # projection
            pts = [
                project_to_screen(*rotated_verts[i], self.fov, cx, cy)
                for i in face
            ]

            if None in pts:
                continue

            color = tuple(
                min(255, int(c * light_dot))
                for c in self.ship.base_color
            )

            depth = max(rotated_verts[i][2] for i in face)

            faces.append(("face", depth, [p[:2] for p in pts], color))

        return faces

    def build_particle_queue(self):
        cx, cy = self.W // 2, self.H // 2
        items = []

        for p in self.particles:
            pz = p['pos'][2] + self.camera_z
            proj = project_to_screen(p['pos'][0], p['pos'][1], pz, self.fov, cx, cy)

            if not proj:
                continue

            sx, sy, scale = proj
            ratio = p['life'] / p['max_life']

            size = max(1, int(self.ship.engine_size * scale * ratio * 2))
            color = [int(c * ratio) for c in self.ship.engine_color]

            items.append(("particle", pz, sx, sy, size, color))

        return items

    def draw_queue(self, queue):
        for item in queue:
            if item[0] == "face":
                _, _, poly, color = item
                pygame.draw.polygon(self.screen, color, poly)
                pygame.draw.polygon(self.screen, (20, 20, 40), poly, 1)

            elif item[0] == "particle":
                _, _, sx, sy, size, color = item
                pygame.draw.circle(self.screen, color, (sx, sy), size)

    def draw_hud(self):
        font = custom_font(18)

        texts = [
            "3D SHIP VIEWER",
            f"Model: {self.ship.__class__.__name__}",
            "------------------",
            "Left Click + Drag: Rotate",
            "Mouse Wheel: Zoom",
            f"Zoom Dist: {self.camera_z:.1f}"
        ]
        for i, text in enumerate(texts):
            surface = font.render(text, True, HUD_RED)
            self.screen.blit(surface, (15, 15 + (i * 22)))

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0

            # --- EVENTS ---
            if not self.handle_input():
                break

            # --- LOGIC ---
            self.update_trails(dt)

            # --- RENDER ---
            self.screen.fill((0, 0, 0))  # Deep space black
            face_queue = self.build_render_queue()
            particle_queue = self.build_particle_queue()
            render_queue = face_queue + particle_queue
            render_queue.sort(key=lambda x: x[1], reverse=True)
            self.draw_queue(render_queue)
            self.draw_hud()
            pygame.display.flip()

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    app = Viewer()
    app.run()