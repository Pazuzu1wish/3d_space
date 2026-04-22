import pygame, math, random

try:
    from src.controller import DS4Input
except ImportError:
    print("DS4Input module not found. Keyboard controls active (W/A/S/D, Up/Down, Space).")


    class DS4Input:
        def init(self): pass

        def process_event(self, event): pass

        def stick_right(self): return 0.0, 0.0

        def axis(self, a): return 0.0

        def trigger_left(self): return 0.0

        def trigger_right(self): return 0.0

        def just_pressed(self, btn): return False

        def update(self): pass


# ──────────────────────────────────────────────
#  3D MATH ENGINE (FIXED)
# ──────────────────────────────────────────────
def get_forward_vector(pitch, yaw):
    """Returns a normalized 3D forward vector based on camera pitch/yaw."""
    fx = math.sin(yaw) * math.cos(pitch)
    fy = -math.sin(pitch)
    fz = math.cos(yaw) * math.cos(pitch)
    return fx, fy, fz


def world_to_camera(x, y, z, px, py, pz, pitch, yaw, roll):
    """Accurately transforms a World coordinate into a Camera-relative coordinate."""
    # 1. Translate point relative to camera position
    dx = x - px
    dy = y - py
    dz = z - pz

    # 2. Inverse Yaw (Y-axis rotation)
    x1 = dx * math.cos(yaw) - dz * math.sin(yaw)
    z1 = dx * math.sin(yaw) + dz * math.cos(yaw)

    # 3. Inverse Pitch (X-axis rotation)
    y2 = dy * math.cos(pitch) + z1 * math.sin(pitch)
    z2 = -dy * math.sin(pitch) + z1 * math.cos(pitch)

    # 4. Inverse Roll (Z-axis rotation)
    cx = x1 * math.cos(roll) + y2 * math.sin(roll)
    cy = -x1 * math.sin(roll) + y2 * math.cos(roll)
    cz = z2

    return cx, cy, cz


def project_to_screen(x, y, z, fov=400, cx=450, cy=310):
    if z <= 0.1:  # Behind camera
        return None
    scale = fov / z
    sx, sy = int(x * scale + cx), int(y * scale + cy)
    return sx, sy, scale


# ──────────────────────────────────────────────
#  GAME ENTITIES
# ──────────────────────────────────────────────
class Star:
    def __init__(self, ppos=(0, 0, 0)):
        self.spawn_around(ppos)

    def spawn_around(self, ppos):
        spread = 3000
        self.x = ppos[0] + random.uniform(-spread, spread)
        self.y = ppos[1] + random.uniform(-spread, spread)
        self.z = ppos[2] + random.uniform(-spread, spread)
        self.brightness = random.uniform(0.3, 1.0)

    def draw(self, surf, ppos, prot):
        cx, cy, cz = world_to_camera(self.x, self.y, self.z, *ppos, *prot)

        if cz < -100:
            fx, fy, fz = get_forward_vector(prot[0], prot[1])
            dist = random.uniform(2000, 4000)
            self.x = ppos[0] + fx * dist + random.uniform(-1500, 1500)
            self.y = ppos[1] + fy * dist + random.uniform(-1500, 1500)
            self.z = ppos[2] + fz * dist + random.uniform(-1500, 1500)
            return

        proj = project_to_screen(cx, cy, cz)
        if proj:
            sx, sy, scale = proj
            size = max(1, int(2 * scale))
            b = min(255, int(255 * self.brightness * min(1.0, 500 / (cz or 1))))
            pygame.draw.circle(surf, (b, b, b), (sx, sy), size)


class Laser:
    def __init__(self, ppos, prot):
        fx, fy, fz = get_forward_vector(prot[0], prot[1])
        # Start laser slightly ahead of the ship so it doesn't clip the camera
        self.x = ppos[0] + fx * 50
        self.y = ppos[1] + fy * 50
        self.z = ppos[2] + fz * 50

        # Track previous position to draw as a line (blaster bolt)
        self.px, self.py, self.pz = self.x, self.y, self.z

        speed = 5000
        self.vx, self.vy, self.vz = fx * speed, fy * speed, fz * speed
        self.life = 1.0

    def update(self, dt):
        self.px, self.py, self.pz = self.x, self.y, self.z
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self.life -= dt

    def draw(self, surf, ppos, prot):
        # Project both the head and the tail of the laser
        cx1, cy1, cz1 = world_to_camera(self.px, self.py, self.pz, *ppos, *prot)
        cx2, cy2, cz2 = world_to_camera(self.x, self.y, self.z, *ppos, *prot)

        proj1 = project_to_screen(cx1, cy1, cz1)
        proj2 = project_to_screen(cx2, cy2, cz2)

        if proj1 and proj2:
            pygame.draw.line(surf, (100, 255, 100), (proj1[0], proj1[1]), (proj2[0], proj2[1]), 4)


class Enemy:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z
        self.hp = 3
        self.verts = [
            (0, 0, 40),  # Nose
            (-20, 0, -20),  # Left Wing
            (20, 0, -20),  # Right Wing
            (0, -15, -20),  # Top Fin
            (0, 10, -15)  # Bottom Belly
        ]
        self.edges = [(0, 1), (0, 2), (0, 3), (0, 4), (1, 2), (1, 3), (2, 3), (1, 4), (2, 4)]

    def draw(self, surf, ppos, prot):
        projected = {}
        for i, (vx, vy, vz) in enumerate(self.verts):
            cx, cy, cz = world_to_camera(self.x + vx, self.y + vy, self.z + vz, *ppos, *prot)
            proj = project_to_screen(cx, cy, cz)
            if proj: projected[i] = proj

        if len(projected) == len(self.verts):
            color = (255, 80, 80) if self.hp > 1 else (255, 200, 80)
            for p1, p2 in self.edges:
                sx1, sy1, _ = projected[p1]
                sx2, sy2, _ = projected[p2]
                pygame.draw.line(surf, color, (sx1, sy1), (sx2, sy2), 2)


class Particle:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z
        self.vx = random.uniform(-300, 300)
        self.vy = random.uniform(-300, 300)
        self.vz = random.uniform(-300, 300)
        self.life = 1.0
        self.color = random.choice([(255, 100, 50), (255, 200, 50), (100, 100, 100)])

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self.life -= dt

    def draw(self, surf, ppos, prot):
        cx, cy, cz = world_to_camera(self.x, self.y, self.z, *ppos, *prot)
        proj = project_to_screen(cx, cy, cz)
        if proj:
            sx, sy, scale = proj
            size = max(1, int(15 * scale * self.life))
            pygame.draw.circle(surf, self.color, (sx, sy), size)


# ──────────────────────────────────────────────
#  HUD & MAIN LOOP
# ──────────────────────────────────────────────
def draw_cockpit_hud(surf, W, H, throttle, weapons_ready):
    pygame.draw.rect(surf, (30, 40, 80), (0, 0, W, H), 8)
    pygame.draw.rect(surf, (80, 140, 255), (4, 4, W - 8, H - 8), 2)

    cx, cy = W // 2, H // 2
    pygame.draw.circle(surf, (80, 255, 140), (cx, cy), 3)
    pygame.draw.line(surf, (80, 255, 140), (cx - 20, cy), (cx - 8, cy), 2)
    pygame.draw.line(surf, (80, 255, 140), (cx + 8, cy), (cx + 20, cy), 2)
    pygame.draw.line(surf, (80, 255, 140), (cx, cy - 20), (cx, cy - 8), 2)
    pygame.draw.line(surf, (80, 255, 140), (cx, cy + 8), (cx, cy + 20), 2)

    bar_h = 200
    pygame.draw.rect(surf, (40, 40, 60), (W - 40, H // 2 - bar_h // 2, 20, bar_h))
    fill_h = int(bar_h * throttle)
    pygame.draw.rect(surf, (60, 220, 120), (W - 40, H // 2 + bar_h // 2 - fill_h, 20, fill_h))
    pygame.draw.rect(surf, (80, 140, 255), (W - 40, H // 2 - bar_h // 2, 20, bar_h), 1)

    status = "ARMED" if weapons_ready else "COOLING"
    color = (60, 220, 120) if weapons_ready else (255, 100, 100)
    font = pygame.font.SysFont("Courier", 14, bold=True)
    surf.blit(font.render(status, True, color), (W - 120, 20))

    speed = f"{int(throttle * 2500):04d} KM/H"
    surf.blit(pygame.font.SysFont("Courier", 24, bold=True).render(speed, True, (200, 220, 255)), (20, 20))


def main():
    pygame.init()
    W, H = 900, 620
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("🚀 3D Cockpit Dogfighter")
    clock = pygame.time.Clock()

    handler = DS4Input()
    handler.init()

    player_pos = [0.0, 0.0, 0.0]
    player_rot = [0.0, 0.0, 0.0]
    throttle = 0.0
    weapons_cooldown = 0

    stars = [Star(player_pos) for _ in range(250)]
    enemies = []
    lasers = []
    particles = []

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False
            handler.process_event(event)

        # ── INPUT HANDLING ──
        rx, ry = handler.stick_left()
        r_roll = handler.axis(3)
        l2, r2 = handler.trigger_left(), handler.trigger_right()
        fire_pressed = handler.just_pressed('X')

        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]: ry = -1.0
        if keys[pygame.K_s]: ry = 1.0
        if keys[pygame.K_a]: rx = -1.0
        if keys[pygame.K_d]: rx = 1.0
        if keys[pygame.K_UP]: throttle = min(1.0, throttle + dt)
        if keys[pygame.K_DOWN]: throttle = max(0.0, throttle - dt)
        if keys[pygame.K_SPACE]: fire_pressed = True

        player_rot[0] += ry * dt * 1.5  # Pitch
        player_rot[1] += rx * dt * 1.5  # Yaw
        player_rot[2] += r_roll * dt * 1.0  # Roll

        throttle = max(0.0, min(1.0, throttle + (r2 - l2) * dt * 0.8))

        # ── PHYSICS / MOVEMENT ──
        fx, fy, fz = get_forward_vector(player_rot[0], player_rot[1])
        speed = throttle * 1500
        player_pos[0] += fx * speed * dt
        player_pos[1] += fy * speed * dt
        player_pos[2] += fz * speed * dt

        if fire_pressed and weapons_cooldown <= 0:
            lasers.append(Laser(player_pos, player_rot))
            weapons_cooldown = 0.25
        weapons_cooldown = max(0, weapons_cooldown - dt)

        # ── UPDATE ENTITIES & COLLISIONS ──
        for l in lasers[:]:
            l.update(dt)
            if l.life <= 0: lasers.remove(l)

        for e in enemies[:]:
            for l in lasers[:]:
                # We check the distance between the laser's head and the enemy's center
                if math.dist((l.x, l.y, l.z), (e.x, e.y, e.z)) < 80:
                    e.hp -= 1
                    lasers.remove(l)
                    for _ in range(8): particles.append(Particle(e.x, e.y, e.z))
                    break

            if e.hp <= 0:
                for _ in range(25): particles.append(Particle(e.x, e.y, e.z))
                enemies.remove(e)

            cx, cy, cz = world_to_camera(e.x, e.y, e.z, *player_pos, *player_rot)
            if cz < -500:
                enemies.remove(e)

        for p in particles[:]:
            p.update(dt)
            if p.life <= 0: particles.remove(p)

        if len(enemies) < 6 and random.random() < 0.02:
            dist = random.uniform(2000, 4000)
            enemies.append(Enemy(
                player_pos[0] + fx * dist + random.uniform(-1000, 1000),
                player_pos[1] + fy * dist + random.uniform(-1000, 1000),
                player_pos[2] + fz * dist + random.uniform(-1000, 1000)
            ))

        # ── DRAWING ──
        screen.fill((5, 5, 15))

        for star in stars: star.draw(screen, player_pos, player_rot)
        for e in enemies: e.draw(screen, player_pos, player_rot)
        for p in particles: p.draw(screen, player_pos, player_rot)
        # Draw lasers last so they are visible over the stars
        for l in lasers: l.draw(screen, player_pos, player_rot)

        draw_cockpit_hud(screen, W, H, throttle, weapons_cooldown <= 0)

        pygame.display.flip()
        handler.update()

    pygame.quit()


if __name__ == "__main__":
    main()