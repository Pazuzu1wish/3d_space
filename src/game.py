import pygame
import random
from .math_engine import *
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
        lx, ly = handler.stick_left()
        rx, _ = handler.stick_right()
        fire_l = handler.trigger_left() > 0.5
        fire_r = handler.trigger_right() > 0.5
        fire_pressed = fire_l or fire_r

        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]:     ly = -1.0
        if keys[pygame.K_s]:     ly = 1.0
        if keys[pygame.K_a]:     lx = -1.0
        if keys[pygame.K_d]:     lx = 1.0
        if keys[pygame.K_UP]:    throttle = min(1.0, throttle + dt)
        if keys[pygame.K_DOWN]:  throttle = max(0.0, throttle - dt)
        if keys[pygame.K_SPACE]: fire_pressed = True

        player_rot[0] += ly * dt * 1.5  # pitch  — left stick Y
        player_rot[1] += rx * dt * 1.5  # yaw    — right stick X
        player_rot[2] += lx * dt * 1.0  # roll   — left stick X

        if handler.held('R1'): throttle = min(1.0, throttle + dt * 0.8)
        if handler.held('L1'): throttle = max(0.0, throttle - dt * 0.8)

        weapons_cooldown = max(0, weapons_cooldown - dt)

        # ── PHYSICS / MOVEMENT ──
        fx, fy, fz = get_forward_vector(player_rot[0], player_rot[1])
        speed = throttle * 1500
        player_pos[0] += fx * speed * dt
        player_pos[1] += fy * speed * dt
        player_pos[2] += fz * speed * dt

        if fire_pressed and weapons_cooldown <= 0:
            (_, _, _), (rx, ry, rz), _ = get_basis_vectors(
                player_rot[0],
                player_rot[1],
                player_rot[2]
            )
            offset = 40
            for side in (-1, 1):
                wing_pos = [
                    player_pos[0] + rx * offset * side + fx * 20,
                    player_pos[1] + ry * offset * side + fy * 20,
                    player_pos[2] + rz * offset * side + fz * 20,
                ]
                lasers.append(Laser(wing_pos, player_rot))
            weapons_cooldown = 0.25

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