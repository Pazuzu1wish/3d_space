import pygame
import math
from .math_engine import (
    world_to_camera, project_to_screen, quat_identity
)
from .cockpit import draw_cockpit_hud
from .controller import DS4Input
from .star import Star
from .particle import Particle
from .enemy import SuicideDrone, Dogfighter
from .laser import Laser
from .player import Player
from .constants import HIT_FLASH_DURATION, PLAYER_COLLISION_RADIUS
from .utils import draw_damage_overlay
from .director import WaveDirector
from .encounters import ENCOUNTER_SCRIPT

# ──────────────────────────────────────────────
# MAIN LOOP
# ──────────────────────────────────────────────

def update_entities(dt, player, enemies, lasers, enemy_projectiles, particles):
    # ── UPDATE LASERS ─────────────────────────
    for l in lasers[:]:
        l.update(dt)
        if l.life <= 0:
            lasers.remove(l)

    # ── UPDATE ENEMIES ────────────────────────
    for e in enemies[:]:
        e.update(dt, player.pos, player.orientation, enemy_projectiles)

        # Laser hits
        for l in lasers[:]:
            if math.dist((l.x, l.y, l.z), (e.x, e.y, e.z)) < 80:
                e.on_hit()
                lasers.remove(l)
                for _ in range(8):
                    particles.append(Particle(e.x, e.y, e.z))
                break

        # Drone destroyed
        if e.hp <= 0:
            for _ in range(25):
                particles.append(Particle(e.x, e.y, e.z))
            enemies.remove(e)
            continue

        # Collision with player — drone is a kamikaze
        if e.dist_to_player(player.pos) < PLAYER_COLLISION_RADIUS:
            player.take_damage(20)
            for _ in range(30):
                particles.append(Particle(e.x, e.y, e.z))
            enemies.remove(e)
            continue

        # Cull enemies that are very far away AND well behind the camera
        _, _, cz = world_to_camera(
            e.x, e.y, e.z,
            player.pos[0], player.pos[1], player.pos[2],
            player.orientation,
        )
        if cz < -8000:
            enemies.remove(e)

    # ── UPDATE PROJECTILES ────────────────────────
    for bolt in enemy_projectiles[:]:
        bolt['x'] += bolt['vx'] * dt
        bolt['y'] += bolt['vy'] * dt
        bolt['z'] += bolt['vz'] * dt
        bolt['life'] -= dt
        if bolt['life'] <= 0:
            enemy_projectiles.remove(bolt)

    # ── UPDATE PARTICLES ──────────────────────
    for p in particles[:]:
        p.update(dt)
        if p.life <= 0:
            particles.remove(p)
    # NOTE: Enemy spawning is now handled by WaveDirector.update() in main()

def draw_game(screen, W, H, player, stars, enemies, lasers, enemy_projectiles, particles):
    screen.fill((5, 5, 15))

    draw_args = (player.pos, player.orientation)
    for star in stars:  star.draw(screen, *draw_args)
    for e in enemies:   e.draw(screen, *draw_args)
    for p in particles: p.draw(screen, *draw_args)
    for l in lasers:    l.draw(screen, *draw_args)

    # Draw projectiles
    for bolt in enemy_projectiles:
        cx, cy, cz = world_to_camera(bolt['x'], bolt['y'], bolt['z'], *draw_args[0], draw_args[1])
        proj = project_to_screen(cx, cy, cz)
        if proj:
            sx, sy, scale = proj
            size = max(2, int(scale * 2))
            pygame.draw.circle(screen, (255, 100, 100), (sx, sy), size)

    draw_cockpit_hud(
        screen, W, H, player.throttle, player.current_speed, player.weapons_cooldown <= 0,
        orientation=player.orientation,
        player_pos=player.pos,
        player_vel=tuple(player.vel),
        enemies=enemies,
        player_hp=player.hp,
        active_target=player.active_target
    )

    # Damage overlay
    draw_damage_overlay(screen, W, H, player.hit_flash / HIT_FLASH_DURATION)

def main():
    pygame.init()
    W, H = 900, 620
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("🚀 3D Cockpit Dogfighter")
    clock = pygame.time.Clock()

    handler = DS4Input()
    handler.init()

    player  = Player()
    director = WaveDirector(ENCOUNTER_SCRIPT)

    stars     = [Star(player.pos) for _ in range(250)]
    enemies   = []
    lasers    = []
    particles = []
    enemy_projectiles = []

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        # ── EVENTS ───────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
            ):
                running = False
            handler.process_event(event)

        keys = pygame.key.get_pressed()

        # ── UPDATE ────────────────────────────────
        player.update(dt, handler, keys, lasers, particles, enemy_projectiles)
        update_entities(dt, player, enemies, lasers, enemy_projectiles, particles)
        director.update(dt, player.pos, player.orientation, enemies)

        # ── TARGETING ──────────────────────────────────────
        # Keep target valid after kills/culls
        player.clear_dead_target(enemies)
        if player._key_target_closest:
            player.target_closest(enemies)
        elif player._key_cycle_target:
            player.cycle_targets(enemies)

        # ── DRAW ──────────────────────────────────
        draw_game(screen, W, H, player, stars, enemies, lasers, enemy_projectiles, particles)

        pygame.display.flip()
        handler.update()

    pygame.quit()

if __name__ == "__main__":
    main()