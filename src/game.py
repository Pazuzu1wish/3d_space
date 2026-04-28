import pygame
import math
from .math_engine import (
    world_to_camera, project_to_screen, quat_identity
)
from .cockpit import draw_cockpit_hud
from .controller import DS4Input
from .star import Star
from .particle import Particle
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
        e.update(dt, player.pos, player.orientation, enemy_projectiles, enemies)

        # Laser hits
        for l in lasers[:]:
            dx, dy, dz = l.x - e.x, l.y - e.y, l.z - e.z
            if (dx*dx + dy*dy + dz*dz) < 6400:  # 80^2
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

        # Collision with player
        if e.dist_to_player(player.pos) < PLAYER_COLLISION_RADIUS:
            player.take_damage(20)
            for _ in range(30):
                particles.append(Particle(e.x, e.y, e.z))
            enemies.remove(e)
            continue

        # Cull enemies far behind the camera
        _, _, cz = world_to_camera(
            e.x, e.y, e.z,
            player.pos[0], player.pos[1], player.pos[2],
            player.orientation,
        )
        if cz < -8000:
            enemies.remove(e)

    # ── UPDATE PROJECTILES ────────────────────────
    for bolt in enemy_projectiles[:]:
        if bolt.get('homing', False):
            dx = player.pos[0] - bolt['x']
            dy = player.pos[1] - bolt['y']
            dz = player.pos[2] - bolt['z']
            dist = math.sqrt(dx*dx + dy*dy + dz*dz) or 1

            turn_rate = 2.0 * dt

            spd = math.sqrt(bolt['vx']**2 + bolt['vy']**2 + bolt['vz']**2) or 1

            new_nx = (bolt['vx'] / spd) + (dx / dist) * turn_rate
            new_ny = (bolt['vy'] / spd) + (dy / dist) * turn_rate
            new_nz = (bolt['vz'] / spd) + (dz / dist) * turn_rate

            new_norm = math.sqrt(new_nx**2 + new_ny**2 + new_nz**2) or 1
            bolt['vx'] = (new_nx / new_norm) * spd
            bolt['vy'] = (new_ny / new_norm) * spd
            bolt['vz'] = (new_nz / new_norm) * spd

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

def draw_game(screen, W, H, player, stars, enemies, lasers, enemy_projectiles, particles):
    screen.fill((5, 5, 15))

    draw_args = (player.pos, player.orientation)
    for star in stars:  star.draw(screen, *draw_args)

    # ── DRAW ENEMIES & SNIPER LASERS ────────────────
    for e in enemies:
        e.draw(screen, *draw_args)

        # If this is a Sniper in the charging state, draw the targeting beam!
        if getattr(e, 'state', '') == 'charging':
            # 1. Figure out where the sniper is on the screen
            cx, cy, cz = world_to_camera(e.x, e.y, e.z, *draw_args[0], draw_args[1])

            if cz > 0.1:  # Only draw if the sniper is in front of the camera
                proj = project_to_screen(cx, cy, cz)
                if proj:
                    sx, sy, scale = proj

                    # 2. Calculate intensity (Charge timer goes 1.5 down to 0)
                    intensity = 1.0 - max(0.0, min(1.0, getattr(e, 'timer', 1.5) / 1.5))

                    # 3. Add an unstable jitter effect that gets worse as it charges
                    jitter = math.sin(pygame.time.get_ticks() * 0.05) * (5 * intensity)
                    jx, jy = sx + jitter, sy - jitter

                    # 4. Draw outer red glow (gets thicker)
                    thickness = max(1, int(8 * intensity))
                    pygame.draw.line(screen, (255, 0, 0), (jx, jy), (W//2, H//2), thickness)

                    # 5. Draw inner white-hot core right before firing
                    if intensity > 0.4:
                        pygame.draw.line(screen, (255, 255, 255), (jx, jy), (W//2, H//2), max(1, thickness - 3))

                    # 6. Draw a bright glare on the front of the sniper's ship
                    glare = int(35 * intensity * scale)
                    if glare > 0:
                        pygame.draw.circle(screen, (255, 50, 50), (jx, jy), glare)

    for p in particles: p.draw(screen, *draw_args)
    for l in lasers:    l.draw(screen, *draw_args)

    # Draw projectiles
    for bolt in enemy_projectiles:
        cx, cy, cz = world_to_camera(bolt['x'], bolt['y'], bolt['z'], *draw_args[0], draw_args[1])
        proj = project_to_screen(cx, cy, cz)
        if proj:
            sx, sy, scale = proj
            # Grab customized traits, or fallback to defaults
            color = bolt.get('color', (255, 100, 100))
            size_mult = bolt.get('size_mult', 1.0)

            size = max(2, int(scale * 2 * size_mult))
            pygame.draw.circle(screen, color, (sx, sy), size)

            # If it's a homing bolt, draw an inner white core to make it look intense
            if bolt.get('homing', False) and size > 2:
                pygame.draw.circle(screen, (255, 255, 255), (sx, sy), int(size / 2))

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