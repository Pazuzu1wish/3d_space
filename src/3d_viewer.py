import pygame
import math
import random
import sys


# ==========================================
# 1. YOUR MATH ENGINE (Pasted directly)
# ==========================================

def quat_identity(): return (1.0, 0.0, 0.0, 0.0)


def quat_from_axis_angle(ax, ay, az, angle):
    half = angle * 0.5
    s = math.sin(half)
    return (math.cos(half), ax * s, ay * s, az * s)


def quat_mul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def quat_normalise(q):
    w, x, y, z = q
    mag = math.sqrt(w * w + x * x + y * y + z * z) or 1.0
    return (w / mag, x / mag, y / mag, z / mag)


def quat_conjugate(q):
    w, x, y, z = q
    return (w, -x, -y, -z)


def quat_rotate_vec(q, v):
    vx, vy, vz = v
    p = (0.0, vx, vy, vz)
    r = quat_mul(quat_mul(q, p), quat_conjugate(q))
    return r[1], r[2], r[3]


def rotate_pitch(q, delta):
    local_right = quat_rotate_vec(q, (1.0, 0.0, 0.0))
    dq = quat_from_axis_angle(*local_right, delta)
    return quat_normalise(quat_mul(dq, q))


def rotate_yaw(q, delta):
    local_up = quat_rotate_vec(q, (0.0, 1.0, 0.0))
    dq = quat_from_axis_angle(*local_up, delta)
    return quat_normalise(quat_mul(dq, q))


def rotate_roll(q, delta):
    local_fwd = quat_rotate_vec(q, (0.0, 0.0, 1.0))
    dq = quat_from_axis_angle(*local_fwd, delta)
    return quat_normalise(quat_mul(dq, q))


def get_forward_from_quat(q):
    return quat_rotate_vec(q, (0.0, 0.0, 1.0))


def project_to_screen(x, y, z, fov=400, cx=640, cy=370):
    if z <= 0.1: return None
    scale = fov / z
    sx = int(x * scale + cx)
    sy = int(y * scale + cy)
    return sx, sy, scale


# ==========================================
# 2. MOCK CLASSES (To make your ship run)
# ==========================================
MG_COOLDOWN = 0.1


class Enemy:
    """Mock base class so Dogfighter doesn't crash"""

    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z
        self.vx = self.vy = self.vz = 0
        self.forward = (0, 0, 1)

    def _apply_banking(self, target_v, dt): pass

    def _update_orientation(self): pass

    def _spawn_engine_trail(self): pass

    def _update_engine_trail(self, dt): pass


# ==========================================
# 3. YOUR SHIP CLASS (Pasted directly)
# ==========================================

class Dogfighter(Enemy):
    SPEED = 1400
    FIRE_RANGE = 4500
    IDEAL_RANGE = 1000
    CIRCLE_RADIUS = 1500

    def __init__(self, x, y, z):
        super().__init__(x, y, z)

        self.hp = 5
        self.max_hp = 5
        self.t = 0
        self.base_color = (30, 200, 255)

        # Twin Blue Thrusters
        self.engine_offsets = [(-15, 0, -40), (15, 0, -40)]
        self.engine_color = (100, 200, 255)
        self.engine_size = 4.5
        self.trail_life = 0.6

        self.mg_timer = 0.0
        self.bolt_timer = random.uniform(2.0, 5.0)

        self.mode = 'positioning'
        self.mode_timer = random.uniform(2.0, 4.0)
        self.phase = random.uniform(0, math.pi * 2)
        self._flicker = 0

        # 3D MODEL GEOMETRY
        # ----------------------------------------------------
        self.verts = [
            # CENTERLINE (x=0)
            (0, 0, 70),  # 0: Nose
            (0, 15, -10),  # 1: Cockpit Roof
            (0, -12, 10),  # 2: Belly Bottom
            (0, -10, -40),  # 3: Engine Backplate Bottom Center
            (0, 10, -40),  # 4: Engine Backplate Top Center

            # LEFT SIDE (x < 0)
            (-20, 0, -10),  # 5: Left Body Flare
            (-15, 0, -40),  # 6: Left Engine Exhaust (Rear)
            (-50, 2, 30),  # 7: Left Wingtip TOP
            (-50, -2, 30),  # 8: Left Wingtip BOTTOM

            # RIGHT SIDE (x > 0)
            (20, 0, -10),  # 9: Right Body Flare
            (15, 0, -40),  # 10: Right Engine Exhaust (Rear)
            (50, 2, 30),  # 11: Right Wingtip TOP
            (50, -2, 30),  # 12: Right Wingtip BOTTOM
        ]

        self.faces = [
            # --- NOSE CONE ---
            (0, 5, 1),  # Top Left Front
            (0, 1, 9),  # Top Right Front
            (0, 2, 5),  # Bottom Left Front
            (0, 9, 2),  # Bottom Right Front

            # --- MAIN FUSELAGE ---
            (1, 5, 6), (1, 6, 4),  # Top Left Body
            (1, 4, 10), (1, 10, 9),  # Top Right Body
            (2, 3, 6), (2, 6, 5),  # Bottom Left Body
            (2, 9, 10), (2, 10, 3),  # Bottom Right Body

            # --- ENGINE BACKPLATE (Closes the hole!) ---
            (4, 3, 6),  # Left half of rear wall
            (4, 10, 3),  # Right half of rear wall

            # --- THICK LEFT WING (Swept Forward) ---
            (5, 7, 6),  # Wing Top
            (5, 6, 8),  # Wing Bottom
            (5, 8, 7),  # Wing Leading Edge (Front flat side)
            (6, 7, 8),  # Wing Trailing Edge (Rear flat side)

            # --- THICK RIGHT WING (Swept Forward) ---
            (9, 10, 11),  # Wing Top
            (9, 12, 10),  # Wing Bottom
            (9, 11, 12),  # Wing Leading Edge (Front flat side)
            (10, 12, 11)  # Wing Trailing Edge (Rear flat side)
        ]


# ==========================================
# 4. 3D VIEWER APP
# ==========================================

class Viewer:
    def __init__(self):
        pygame.init()
        self.W, self.H = 1024, 768
        self.screen = pygame.display.set_mode((self.W, self.H))
        pygame.display.set_caption("3D Entity Viewer - Ship Modeler")
        self.clock = pygame.time.Clock()

        # Instantiate the ship to view
        self.ship = Dogfighter(0, 0, 0)

        # Viewer Camera & State
        self.camera_z = 250.0  # Distance from object (Zoom)
        self.fov = 400
        self.obj_quat = quat_identity()  # The rotation of the ship in the viewer

        # Interaction state
        self.is_dragging = False
        self.last_mouse_pos = (0, 0)

        # Particles to simulate trails sitting still in 3D
        self.particles = []

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
        font = pygame.font.SysFont("Consolas", 16)

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
            self.screen.fill((0, 0, 0))  # Deep space blue

            cx, cy = self.W // 2, self.H // 2

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
                # if nz > 0:
                #     continue

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
                surface = font.render(text, True, (0, 255, 100))
                self.screen.blit(surface, (15, 15 + (i * 22)))

            pygame.display.flip()

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    app = Viewer()
    app.run()