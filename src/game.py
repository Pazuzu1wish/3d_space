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
from .enemy import SuicideDrone
from .laser import Laser

# ──────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────

MAX_ENEMIES       = 3
SPAWN_CHANCE      = 0.02            # probability per frame at 60 fps
SPAWN_DIST_MIN    = 2000
SPAWN_DIST_MAX    = 4000
SPAWN_HEIGHT_RANGE = 2000            # vertical spread around spawn point
SPAWN_YAW_SPREAD  = 10.55            # radians either side of yaw-forward (≈ ±31°)

PLAYER_COLLISION_RADIUS = 80        # world units — drone kills at this range
PLAYER_MAX_HP     = 100

HIT_FLASH_DURATION = 0.25          # seconds screen flashes red on hit


# ──────────────────────────────────────────────
# SPAWN HELPER
# ──────────────────────────────────────────────

def _spawn_drone(player_pos, orientation):
    """
    Spawn a SuicideDrone ahead of the player in the yaw plane.

    Strategy:
      1.  Take the ship's forward vector and flatten it onto the world XZ plane
          (ignore pitch) so spawns always appear on the horizontal horizon,
          not straight up when the player is nosing skyward.
      2.  Rotate that flat forward by a random yaw offset within SPAWN_YAW_SPREAD.
      3.  Choose a random height offset independently so they come from
          different elevations without affecting the heading distribution.
    """
    fx, _, fz = get_forward_from_quat(orientation)

    # Flatten to XZ and normalise
    flat_len = math.sqrt(fx*fx + fz*fz) or 1.0
    fx /= flat_len
    fz /= flat_len

    # Random yaw offset
    yaw_offset = random.uniform(-SPAWN_YAW_SPREAD, SPAWN_YAW_SPREAD)
    cos_y, sin_y = math.cos(yaw_offset), math.sin(yaw_offset)
    sfx = fx * cos_y - fz * sin_y
    sfz = fx * sin_y + fz * cos_y

    dist = random.uniform(SPAWN_DIST_MIN, SPAWN_DIST_MAX)
    height_offset = random.uniform(-SPAWN_HEIGHT_RANGE, SPAWN_HEIGHT_RANGE)

    return SuicideDrone(
        player_pos[0] + sfx * dist,
        player_pos[1] + height_offset,
        player_pos[2] + sfz * dist,
    )


# ──────────────────────────────────────────────
# SCREEN-SPACE DAMAGE OVERLAY
# ──────────────────────────────────────────────

def _draw_damage_overlay(screen, W, H, intensity):
    """Red vignette that fades in when the player is hit."""
    if intensity <= 0:
        return
    alpha = int(min(200, intensity * 200))
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    pygame.draw.rect(overlay, (220, 20, 20, alpha), (0, 0, W, H))
    screen.blit(overlay, (0, 0))


def _draw_hp_bar(screen, W, H, hp, max_hp=PLAYER_MAX_HP):
    bar_w = 200
    bar_h = 10
    x = 20
    y = H - 30
    ratio = max(0.0, hp / max_hp)
    col = (60, 220, 60) if ratio > 0.5 else (255, 200, 30) if ratio > 0.25 else (255, 50, 50)
    pygame.draw.rect(screen, (40, 40, 40), (x, y, bar_w, bar_h), border_radius=4)
    pygame.draw.rect(screen, col,          (x, y, int(bar_w * ratio), bar_h), border_radius=4)
    pygame.draw.rect(screen, (100, 100, 100), (x, y, bar_w, bar_h), 1, border_radius=4)
    try:
        font = pygame.font.SysFont("Courier New", 11)
    except Exception:
        font = pygame.font.SysFont(None, 12)
    lbl = font.render(f"HULL  {hp:3d}%", True, col)
    screen.blit(lbl, (x, y - 14))


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

    player_pos  = [0.0, 0.0, 0.0]
    orientation = quat_identity()

    throttle        = 0.0
    weapons_cooldown = 0.0

    player_hp      = PLAYER_MAX_HP
    hit_flash      = 0.0          # countdown timer for damage overlay

    stars     = [Star(player_pos) for _ in range(250)]
    enemies   = []
    lasers    = []
    particles = []

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

        # ── INPUT ─────────────────────────────────
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
        if keys[pygame.K_LEFT]:  rx = -1.0
        if keys[pygame.K_RIGHT]: rx =  1.0
        if keys[pygame.K_UP]:    throttle = min(1.0, throttle + dt)
        if keys[pygame.K_DOWN]:  throttle = max(0.0, throttle - dt)
        if keys[pygame.K_SPACE]: fire_pressed = True

        if handler.held('R1'): throttle = min(1.0, throttle + dt * 0.8)
        if handler.held('L1'): throttle = max(0.0, throttle - dt * 0.8)

        # ── ROTATION ──────────────────────────────
        PITCH_RATE = 2.0
        YAW_RATE   = 1.5
        ROLL_RATE  = 3.0

        if abs(ly) > 0.01:
            orientation = rotate_pitch(orientation,  ly * PITCH_RATE * dt)
        if abs(rx) > 0.01:
            orientation = rotate_yaw  (orientation,  rx * YAW_RATE   * dt)
        if abs(lx) > 0.01:
            orientation = rotate_roll (orientation,  lx * ROLL_RATE  * dt)

        weapons_cooldown = max(0.0, weapons_cooldown - dt)
        hit_flash        = max(0.0, hit_flash - dt)

        # ── MOVEMENT ──────────────────────────────
        fx, fy, fz = get_forward_from_quat(orientation)
        speed = throttle * 1500
        player_pos[0] += fx * speed * dt
        player_pos[1] += fy * speed * dt
        player_pos[2] += fz * speed * dt

        # ── WEAPONS ───────────────────────────────
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
                lasers.append(Laser(wing_pos, orientation))
            weapons_cooldown = 0.25

        # ── UPDATE LASERS ─────────────────────────
        for l in lasers[:]:
            l.update(dt)
            if l.life <= 0:
                lasers.remove(l)

        # ── UPDATE ENEMIES ────────────────────────
        for e in enemies[:]:
            e.update(dt, player_pos, orientation)

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
            if e.dist_to_player(player_pos) < PLAYER_COLLISION_RADIUS:
                dmg = 20
                player_hp = max(0, player_hp - dmg)
                hit_flash = HIT_FLASH_DURATION
                # Big explosion
                for _ in range(30):
                    particles.append(Particle(e.x, e.y, e.z))
                enemies.remove(e)
                continue

            # Cull enemies that are very far away AND well behind the camera
            # (drones that are behind the player and failed to turn around)
            _, _, cz = world_to_camera(
                e.x, e.y, e.z,
                player_pos[0], player_pos[1], player_pos[2],
                orientation,
            )
            if cz < -8000:
                enemies.remove(e)

        # ── UPDATE PARTICLES ──────────────────────
        for p in particles[:]:
            p.update(dt)
            if p.life <= 0:
                particles.remove(p)

        # ── SPAWN NEW ENEMIES ─────────────────────
        if len(enemies) < MAX_ENEMIES and random.random() < SPAWN_CHANCE:
            enemies.append(_spawn_drone(player_pos, orientation))

        # ── DRAW ──────────────────────────────────
        screen.fill((5, 5, 15))

        draw_args = (player_pos, orientation)
        for star in stars:  star.draw(screen, *draw_args)
        for e in enemies:   e.draw(screen, *draw_args)
        for p in particles: p.draw(screen, *draw_args)
        for l in lasers:    l.draw(screen, *draw_args)

        draw_cockpit_hud(
            screen, W, H, throttle, weapons_cooldown <= 0,
            orientation=orientation,
            player_pos=player_pos,
            enemies=enemies,
            player_hp=player_hp
        )

        # Damage overlay
        _draw_damage_overlay(screen, W, H, hit_flash / HIT_FLASH_DURATION)


        pygame.display.flip()
        handler.update()

    pygame.quit()


if __name__ == "__main__":
    main()