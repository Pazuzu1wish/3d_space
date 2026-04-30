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

    def run(self):
        running = True
        font = custom_font(18)

        while running:
            dt = self.clock.tick(60) / 1000.0

            # --- EVENTS ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # Left click
                        self.is_dragging = True
                        self.last_mouse_pos = event.pos
                    elif event.button == 4:  # Scroll Up (Zoom In)
                        self.camera_z = max(50, self.camera_z - 20)
                    elif event.button == 5:  # Scroll Down (Zoom Out)
                        self.camera_z += 20

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        self.is_dragging = False

                elif event.type == pygame.MOUSEMOTION:
                    if self.is_dragging:
                        dx = event.pos[0] - self.last_mouse_pos[0]
                        dy = event.pos[1] - self.last_mouse_pos[1]
                        self.last_mouse_pos = event.pos

                        # Apply rotations based on mouse delta
                        self.obj_quat = rotate_yaw(self.obj_quat, dx * 0.01)
                        self.obj_quat = rotate_pitch(self.obj_quat, dy * 0.01)

            # --- LOGIC ---
            self.update_trails(dt)

            # --- RENDER ---
            self.screen.fill((0, 0, 0))  # Deep space black

            cx, cy = self.W // 2, self.H // 2 # Set center screen

            # 1. Rotate & Translate Vertices
            rotated_verts = []
            for vx, vy, vz in self.ship.verts:
                rx, ry, rz = quat_rotate_vec(self.obj_quat, (vx, vy, vz))
                # Push into the screen away from camera
                rz += self.camera_z
                rotated_verts.append((rx, ry, rz))

            # 2. Backface Culling & Flat Shading
            drawn_faces = []
            for face in self.ship.faces:
                v0, v1, v2 = rotated_verts[face[0]], rotated_verts[face[1]], rotated_verts[face[2]]

                # Calculate normal
                dx1, dy1, dz1 = v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2]
                dx2, dy2, dz2 = v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2]
                nx = dy1 * dz2 - dz1 * dy2
                ny = dz1 * dx2 - dx1 * dz2
                nz = dx1 * dy2 - dy1 * dx2

                # If pointing away from camera, don't draw (Backface cull)
                # Vector from face to camera (camera is at 0,0,0 in view space)
                vx, vy, vz = -v0[0], -v0[1], -v0[2]

                # Dot product
                dot = nx * vx + ny * vy + nz * vz

                if dot <= 0:
                    continue

                # Calculate simple lighting (Light coming from top-left)
                mag = math.sqrt(nx * nx + ny * ny + nz * nz) or 1
                light_dot = max(0.2, (nx * 0.5 + ny * 0.5 - nz * 0.7) / mag)

                # Average Z for sorting
                avg_z = sum(rotated_verts[idx][2] for idx in face) / len(face)

                # Project points
                pts = [
                    project_to_screen(rotated_verts[idx][0], rotated_verts[idx][1], rotated_verts[idx][2], self.fov, cx,
                                      cy) for idx in face]

                if None not in pts:
                    color = (
                        min(255, int(self.ship.base_color[0] * light_dot)),
                        min(255, int(self.ship.base_color[1] * light_dot)),
                        min(255, int(self.ship.base_color[2] * light_dot))
                    )
                    drawn_faces.append((avg_z, [p[:2] for p in pts], color))

            # 3. Sort faces back-to-front (Painter's algorithm)
            drawn_faces.sort(key=lambda f: f[0], reverse=True)

            # 4. Draw Trails (Render behind ship if Z is deeper, otherwise top)
            # Standard particle drawing loop with Z integration
            drawn_particles = []
            for p in self.particles:
                pz = p['pos'][2] + self.camera_z
                proj = project_to_screen(p['pos'][0], p['pos'][1], pz, self.fov, cx, cy)
                if proj:
                    sx, sy, scale = proj
                    ratio = p['life'] / p['max_life']
                    size = max(1, int(self.ship.engine_size * scale * ratio * 2))
                    color = [int(c * ratio) for c in self.ship.engine_color]
                    drawn_particles.append((pz, sx, sy, size, color))

            # Combine faces and particles to sort them together by depth
            render_queue = [("face", *f) for f in drawn_faces] + [("particle", *p) for p in drawn_particles]
            render_queue.sort(key=lambda x: x[1], reverse=True)

            # 5. Draw Everything
            for item in render_queue:
                if item[0] == "face":
                    _, avg_z, poly, color = item
                    pygame.draw.polygon(self.screen, color, poly)
                    pygame.draw.polygon(self.screen, (20, 20, 40), poly, 1)  # Wireframe edges
                elif item[0] == "particle":
                    _, pz, sx, sy, size, color = item
                    pygame.draw.circle(self.screen, color, (sx, sy), size)

            # --- HUD ---
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

            pygame.display.flip()

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    app = Viewer()
    app.run()