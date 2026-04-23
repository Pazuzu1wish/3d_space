import pygame
import random
import math
from .math_engine import (
    quat_identity,
    rotate_pitch, rotate_yaw, rotate_roll,
    get_basis_from_quat, get_forward_from_quat,
    world_to_camera, project_to_screen,
)
from .cockpit import draw_cockpit_hud
from .controller import DS4Input
from .star import Star
from .particle import Particle
from .enemy import Enemy
from .laser import Laser

# ──────────────────────────────────────────────
# MAIN LOOP
# ──────────────────────────────────────────────

def main():
    pygame.init()
    W, H = 900, 620
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("🚀 3D Cockpit Dogfighter")
    clock = pygame.time.Clock()

    handler = DS4Input()
    handler.init()

    player_pos = [0.0, 0.0, 0.0]

    # ── Orientation is now a single unit quaternion ──
    # All pitch / yaw / roll inputs are applied in body-local space,
    # so controls always feel relative to the cockpit.
    orientation = quat_identity()

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
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
            ):
                running = False
            handler.process_event(event)

        # ── INPUT HANDLING ──────────────────────────
        lx, ly = handler.stick_left()
        rx, _  = handler.stick_right()
        fire_l = handler.trigger_left()  > 0.5
        fire_r = handler.trigger_right() > 0.5
        fire_pressed = fire_l or fire_r

        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]:     ly = -1.0
        if keys[pygame.K_s]:     ly =  1.0
        if keys[pygame.K_a]:     lx = -1.0
        if keys[pygame.K_d]:     lx =  1.0
        if keys[pygame.K_UP]:    throttle = min(1.0, throttle + dt)
        if keys[pygame.K_DOWN]:  throttle = max(0.0, throttle - dt)
        if keys[pygame.K_SPACE]: fire_pressed = True

        if handler.held('R1'): throttle = min(1.0, throttle + dt * 0.8)
        if handler.held('L1'): throttle = max(0.0, throttle - dt * 0.8)

        # ── ROTATION — body-local quaternion updates ─
        # ly (stick up/down) → pitch around ship's own right axis
        # rx (right stick X) → yaw around ship's own up axis
        # lx (stick left/right) → roll around ship's own forward axis
        PITCH_RATE = 1.5
        YAW_RATE   = 1.5
        ROLL_RATE  = 1.0

        if abs(ly) > 0.01:
            orientation = rotate_pitch(orientation,  ly * PITCH_RATE * dt)
        if abs(rx) > 0.01:
            orientation = rotate_yaw  (orientation,  rx * YAW_RATE   * dt)
        if abs(lx) > 0.01:
            orientation = rotate_roll (orientation,  lx * ROLL_RATE  * dt)

        weapons_cooldown = max(0, weapons_cooldown - dt)

        # ── PHYSICS / MOVEMENT ───────────────────────
        fx, fy, fz = get_forward_from_quat(orientation)
        speed = throttle * 1500
        player_pos[0] += fx * speed * dt
        player_pos[1] += fy * speed * dt
        player_pos[2] += fz * speed * dt

        # ── WEAPONS ──────────────────────────────────
        if fire_pressed and weapons_cooldown <= 0:
            forward, right, _ = get_basis_from_quat(orientation)
            rfx, rfy, rfz = forward
            rrx, rry, rrz = right
            offset = 40
            for side in (-1, 1):
                wing_pos = [
                    player_pos[0] + rrx * offset * side + rfx * 20,
                    player_pos[1] + rry * offset * side + rfy * 20,
                    player_pos[2] + rrz * offset * side + rfz * 20,
                ]
                # Pass the quaternion; Laser.__init__ must accept it.
                # If your Laser still uses Euler angles internally, pass
                # orientation and let it call get_forward_from_quat itself.
                lasers.append(Laser(wing_pos, orientation))
            weapons_cooldown = 0.25

        # ── UPDATE ENTITIES & COLLISIONS ─────────────
        for l in lasers[:]:
            l.update(dt)
            if l.life <= 0:
                lasers.remove(l)

        for e in enemies[:]:
            for l in lasers[:]:
                if math.dist((l.x, l.y, l.z), (e.x, e.y, e.z)) < 80:
                    e.hp -= 1
                    lasers.remove(l)
                    for _ in range(8):
                        particles.append(Particle(e.x, e.y, e.z))
                    break

            if e.hp <= 0:
                for _ in range(25):
                    particles.append(Particle(e.x, e.y, e.z))
                enemies.remove(e)
                continue

            # Cull enemies that have drifted far behind the camera
            cx, cy, cz = world_to_camera(
                e.x, e.y, e.z,
                player_pos[0], player_pos[1], player_pos[2],
                orientation,
            )
            if cz < -500:
                enemies.remove(e)

        for p in particles[:]:
            p.update(dt)
            if p.life <= 0:
                particles.remove(p)

        # Spawn new enemies ahead of the player
        if len(enemies) < 6 and random.random() < 0.02:
            dist = random.uniform(2000, 4000)
            enemies.append(Enemy(
                player_pos[0] + fx * dist + random.uniform(-1000, 1000),
                player_pos[1] + fy * dist + random.uniform(-1000, 1000),
                player_pos[2] + fz * dist + random.uniform(-1000, 1000),
            ))

        # ── DRAWING ───────────────────────────────────
        screen.fill((5, 5, 15))

        draw_args = (player_pos, orientation)   # pass to every drawable
        for star in stars:     star.draw(screen, *draw_args)
        for e in enemies:      e.draw(screen, *draw_args)
        for p in particles:    p.draw(screen, *draw_args)
        for l in lasers:       l.draw(screen, *draw_args)

        draw_cockpit_hud(screen, W, H, throttle, weapons_cooldown <= 0)

        pygame.display.flip()
        handler.update()

    pygame.quit()


if __name__ == "__main__":
    main()