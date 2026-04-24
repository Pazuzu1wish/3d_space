import math
import random
import pygame
from .math_engine import get_forward_from_quat
from .enemy import SuicideDrone, Dogfighter
from .constants import (
    SPAWN_YAW_SPREAD,
    SPAWN_DIST_MIN,
    SPAWN_DIST_MAX,
    SPAWN_HEIGHT_RANGE,
    PLAYER_MAX_HP
)

def spawn_drone(player_pos, orientation):
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

def spawn_dogfighter(player_pos, orientation):
    """
    Spawn a Dogfighter ahead of the player in the yaw plane.
    Uses the same spawning strategy as SuicideDrone for consistency.
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

    return Dogfighter(
        player_pos[0] + sfx * dist,
        player_pos[1] + height_offset,
        player_pos[2] + sfz * dist,
    )

def draw_damage_overlay(screen, W, H, intensity):
    """Red vignette that fades in when the player is hit."""
    if intensity <= 0:
        return
    alpha = int(min(200, intensity * 200))
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    pygame.draw.rect(overlay, (220, 20, 20, alpha), (0, 0, W, H))
    screen.blit(overlay, (0, 0))

def draw_hp_bar(screen, W, H, hp, max_hp=PLAYER_MAX_HP):
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
